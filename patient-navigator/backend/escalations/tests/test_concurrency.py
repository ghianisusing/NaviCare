"""
Race-condition regression tests for the escalation service.

Each race gets two tests:
- a deterministic one that replays the losing interleaving with a stale
  read (runs on any database), and
- a threaded one against real concurrent transactions (Postgres only).
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase

from conversations.models import Conversation
from core.tests.concurrency import requires_postgres, run_concurrently
from escalations.models import Escalation, EscalationEvent
from escalations.services import escalation_service
from escalations.services.exceptions import AlreadyAssignedError
from patients.models import Patient


def _make_world(test):
    user = User.objects.create_user(username="race_patient", password="S0meStrongPass!")
    test.patient = Patient.objects.create(user=user, first_name="Race", last_name="Patient")
    test.conversation = Conversation.objects.create(patient=test.patient)
    test.staff_a = User.objects.create_user(username="race_staff_a", password="S0meStrongPass!", is_staff=True)
    test.staff_b = User.objects.create_user(username="race_staff_b", password="S0meStrongPass!", is_staff=True)
    test.escalation = escalation_service.create_escalation(
        patient=test.patient, conversation=test.conversation, reason=Escalation.Reason.PATIENT_REQUEST
    )


class AssignEscalationStaleReadTests(TestCase):
    def setUp(self):
        _make_world(self)

    def test_claim_based_on_stale_read_does_not_overwrite_other_staff(self):
        # Staff B loaded the escalation while it was still unassigned...
        stale = Escalation.objects.get(pk=self.escalation.pk)
        # ...then staff A claimed it first.
        escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.pk)

        with mock.patch.object(escalation_service, "_get_escalation", return_value=stale):
            with self.assertRaises(AlreadyAssignedError):
                escalation_service.assign_escalation(staff_user=self.staff_b, escalation_id=self.escalation.pk)

        self.escalation.refresh_from_db()
        self.assertEqual(self.escalation.assigned_to, self.staff_a)
        self.assertEqual(
            EscalationEvent.objects.filter(escalation=self.escalation, action=EscalationEvent.Action.ASSIGNED).count(),
            1,
        )


@requires_postgres
class AssignEscalationRaceTests(TransactionTestCase):
    def setUp(self):
        _make_world(self)

    def test_only_one_of_two_concurrent_claims_wins(self):
        def claim(staff):
            return lambda: escalation_service.assign_escalation(staff_user=staff, escalation_id=self.escalation.pk)

        outcomes = run_concurrently(claim(self.staff_a), claim(self.staff_b))

        winners = [o for o in outcomes if isinstance(o, Escalation)]
        losers = [o for o in outcomes if isinstance(o, AlreadyAssignedError)]
        self.assertEqual((len(winners), len(losers)), (1, 1), outcomes)
        self.escalation.refresh_from_db()
        self.assertEqual(self.escalation.assigned_to_id, winners[0].assigned_to_id)
        self.assertEqual(
            EscalationEvent.objects.filter(escalation=self.escalation, action=EscalationEvent.Action.ASSIGNED).count(),
            1,
        )


class DuplicateOpenEscalationTests(TestCase):
    def setUp(self):
        _make_world(self)

    def test_database_rejects_second_open_escalation_for_conversation(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Escalation.objects.create(
                    patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.OUT_OF_SCOPE
                )

    def test_closed_escalation_does_not_block_a_new_one(self):
        escalation_service.resolve_escalation(staff_user=self.staff_a, escalation_id=self.escalation.pk)
        new = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.OUT_OF_SCOPE
        )
        self.assertNotEqual(new.pk, self.escalation.pk)

    def test_create_that_loses_the_race_returns_the_existing_escalation(self):
        # Replay the race: our existence check ran before the other
        # request's insert, so it saw nothing.
        real_find = escalation_service._find_open_escalation
        with mock.patch.object(escalation_service, "_find_open_escalation", side_effect=[None, real_find(self.conversation)]):
            result = escalation_service.create_escalation(
                patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.OUT_OF_SCOPE
            )

        self.assertEqual(result.pk, self.escalation.pk)
        self.assertEqual(Escalation.objects.filter(conversation=self.conversation).count(), 1)

    def test_constraint_statuses_match_service_open_statuses(self):
        constraint = next(
            c for c in Escalation._meta.constraints if c.name == "unique_open_escalation_per_conversation"
        )
        self.assertEqual(sorted(dict(constraint.condition.children)["status__in"]), sorted(escalation_service.OPEN_STATUSES))


@requires_postgres
class CreateEscalationRaceTests(TransactionTestCase):
    def setUp(self):
        _make_world(self)
        escalation_service.cancel_escalation(escalation_id=self.escalation.pk)

    def test_concurrent_creates_yield_one_open_escalation(self):
        def create():
            return escalation_service.create_escalation(
                patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
            )

        outcomes = run_concurrently(create, create, create)

        self.assertTrue(all(isinstance(o, Escalation) for o in outcomes), outcomes)
        self.assertEqual(len({o.pk for o in outcomes}), 1)
        self.assertEqual(
            Escalation.objects.filter(conversation=self.conversation, status__in=escalation_service.OPEN_STATUSES).count(),
            1,
        )
