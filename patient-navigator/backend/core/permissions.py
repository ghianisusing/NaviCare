"""
Shared object-level permissions.

Phase 1's core privacy rule lives here: a patient may only ever act on
records that belong to them. Every view that touches Patient,
Conversation, or Message data should use one of these (directly or via
get_queryset filtering) rather than trusting a URL-supplied id alone.

Phase 6 adds a minimal role model on top of Django's built-in flags
rather than inventing a new roles table:

    PATIENT           — has a Patient profile; not is_staff
    CARE_COORDINATOR  — request.user.is_staff (handles escalations)
    ADMIN             — request.user.is_superuser (system-wide
                         monitoring: agent traces, metrics, and
                         everything a care coordinator can also do)

This means every admin is also treated as a care coordinator for
escalation purposes, but not every care coordinator is an admin —
system-level observability (traces/metrics) is superuser-only.
"""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object must have a `.patient` (or be a Patient itself) tied to request.user."""

    message = "You do not have permission to access this record."

    def has_object_permission(self, request, view, obj):
        patient = getattr(obj, "patient", obj)
        owner_user = getattr(patient, "user", None)
        return owner_user is not None and owner_user == request.user


class IsCareCoordinator(BasePermission):
    """request.user.is_staff — covers both care coordinators and admins
    (admins are supersets of coordinator access here)."""

    message = "This action requires care coordinator or admin access."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsSystemAdmin(BasePermission):
    """request.user.is_superuser — for system-level observability
    (agent traces, metrics) that even a care coordinator should not see."""

    message = "This action requires admin access."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
