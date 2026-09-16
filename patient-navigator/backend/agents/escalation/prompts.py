"""
Fixed, non-LLM-generated response templates for escalation hand-offs.

Kept deterministic on purpose — unlike the other specialized agents,
there is no benefit to letting the model freely word the hand-off
message, and a fixed template guarantees the patient is never told
something inaccurate about what happens next.
"""

from escalations.models import Escalation

RESPONSES = {
    Escalation.Reason.PATIENT_REQUEST: (
        "Absolutely. I've sent this conversation to our care support team, and a "
        "care coordinator will follow up with you here."
    ),
    Escalation.Reason.OUT_OF_SCOPE: (
        "That's something I can't handle directly. I've connected you with our "
        "care support team, and a care coordinator will follow up with you here."
    ),
    Escalation.Reason.REPEATED_FAILURE: (
        "It seems like I'm having trouble helping with this. I've connected you "
        "with our care support team, and a care coordinator will follow up with you here."
    ),
    Escalation.Reason.SAFETY_REVIEW: (
        "I want to make sure you get the right support here. I've connected you "
        "with our care support team, and a care coordinator will follow up with you here."
    ),
    Escalation.Reason.ADMINISTRATIVE_ISSUE: (
        "I've connected you with our care support team for help with this, and a "
        "care coordinator will follow up with you here."
    ),
    Escalation.Reason.HUMAN_ASSISTANCE_REQUIRED: (
        "I've connected you with our care support team, and a care coordinator "
        "will follow up with you here."
    ),
}

DEFAULT_RESPONSE = (
    "I've connected you with our care support team, and a care coordinator will "
    "follow up with you here."
)


def build_escalation_response(reason: str) -> str:
    return RESPONSES.get(reason, DEFAULT_RESPONSE)
