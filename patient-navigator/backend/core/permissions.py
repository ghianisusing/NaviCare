"""
Shared object-level permissions.

Phase 1's core privacy rule lives here: a patient may only ever act on
records that belong to them. Every view that touches Patient,
Conversation, or Message data should use one of these (directly or via
get_queryset filtering) rather than trusting a URL-supplied id alone.
"""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object must have a `.patient` (or be a Patient itself) tied to request.user."""

    message = "You do not have permission to access this record."

    def has_object_permission(self, request, view, obj):
        patient = getattr(obj, "patient", obj)
        owner_user = getattr(patient, "user", None)
        return owner_user is not None and owner_user == request.user
