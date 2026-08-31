"""
Chat Service — sits between the API views and the Navigator Agent.

Views call into this module only; they never construct Message objects
or talk to the agent layer directly. This delegates to
`agents.navigator.service`, which runs the LLM-backed Navigator Agent,
safety validation, and — as of Phase 3 — routing to the Information and
Triage agents. `urgency`/`sources` from the resulting turn are persisted
onto the assistant Message so the frontend can render them (e.g. a
sources list or an emergency banner) without knowing anything about the
agent layer itself.
"""

from django.db import transaction

from agents.navigator import service as navigator_service

from ..models import Conversation, Message


def send_message(*, conversation: Conversation, content: str) -> Message:
    """Persist the patient's message, get a reply, persist that too.

    Returns the assistant's Message (the caller already has the user
    Message's data from the request, so only the reply needs returning).

    The Navigator call intentionally happens outside any DB transaction
    (it's a network call to the LLM provider) so a slow or failed
    request never holds a database lock open.
    """
    with transaction.atomic():
        Message.objects.create(conversation=conversation, role=Message.Role.USER, content=content)

    turn_result = navigator_service.handle_patient_message(conversation=conversation, patient_message=content)

    with transaction.atomic():
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=turn_result.response_text,
            urgency=turn_result.display_urgency,
            sources=turn_result.sources,
            appointment_data=turn_result.appointment_data,
            pending_action=turn_result.pending_action,
        )

        # Touch conversation.updated_at and give untitled conversations a
        # readable title based on the patient's first message.
        if conversation.title in ("", "New conversation"):
            conversation.title = content[:60] + ("…" if len(content) > 60 else "")
        conversation.save(update_fields=["title", "updated_at"])

    return assistant_message
