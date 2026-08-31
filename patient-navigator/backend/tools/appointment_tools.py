"""
Appointment tool definitions — the concrete tools available to the
Appointment Agent, each backed by `appointments.services.appointment_service`
rather than any tool-layer-local business logic.

Every handler here takes `patient` plus already-validated keyword
arguments (see tools/schemas.py's validate_arguments) and returns a
plain, JSON-serializable dict — model instances and dates are never
returned directly to the agent layer.
"""

from __future__ import annotations

from appointments.services import appointment_service
from appointments.services.exceptions import AppointmentError

from .exceptions import ToolAuthorizationError, ToolError
from .schemas import ToolField, ToolSpec
from .registry import register_tool


def _serialize_slot(slot) -> dict:
    return {
        "provider_id": slot.provider_id,
        "provider_name": slot.provider_name,
        "department_name": slot.department_name,
        "start_time": slot.start_time.isoformat(),
        "end_time": slot.end_time.isoformat(),
    }


def _serialize_appointment(appointment) -> dict:
    return {
        "id": appointment.id,
        "provider_id": appointment.provider_id,
        "provider_name": appointment.provider.display_name,
        "department_name": appointment.provider.department.name,
        "start_time": appointment.start_time.isoformat(),
        "end_time": appointment.end_time.isoformat(),
        "status": appointment.status,
        "reason": appointment.reason,
    }


def _serialize_department(department) -> dict:
    return {"id": department.id, "name": department.name, "description": department.description}


def _serialize_provider(provider) -> dict:
    return {
        "id": provider.id,
        "name": provider.display_name,
        "department_id": provider.department_id,
        "department_name": provider.department.name,
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_search_departments(patient, *, query: str = "") -> dict:
    departments = appointment_service.search_departments(query=query)
    return {"departments": [_serialize_department(d) for d in departments]}


def _handle_search_providers(patient, *, department_name: str = "", query: str = "") -> dict:
    providers = appointment_service.search_providers(department_name=department_name, query=query)
    return {"providers": [_serialize_provider(p) for p in providers]}


def _handle_find_available_slots(patient, *, department_name: str = "", provider_id: int | None = None, date=None) -> dict:
    slots = appointment_service.find_available_slots(department_name=department_name, provider_id=provider_id, on_date=date)
    return {"slots": [_serialize_slot(s) for s in slots]}


def _handle_get_patient_appointments(patient, *, status: str = "") -> dict:
    appointments = appointment_service.get_patient_appointments(patient=patient, status=status or None)
    return {"appointments": [_serialize_appointment(a) for a in appointments]}


def _handle_book_appointment(patient, *, provider_id: int, start_time, end_time, reason: str = "") -> dict:
    try:
        appointment = appointment_service.book_appointment(
            patient=patient, provider_id=provider_id, start_time=start_time, end_time=end_time, reason=reason
        )
    except AppointmentError as exc:
        raise ToolError(str(exc)) from exc
    return {"appointment": _serialize_appointment(appointment)}


def _handle_cancel_appointment(patient, *, appointment_id: int) -> dict:
    from appointments.services.exceptions import NotOwnerError

    try:
        appointment = appointment_service.cancel_appointment(patient=patient, appointment_id=appointment_id)
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except AppointmentError as exc:
        raise ToolError(str(exc)) from exc
    return {"appointment": _serialize_appointment(appointment)}


def _handle_reschedule_appointment(patient, *, appointment_id: int, new_start_time, new_end_time) -> dict:
    from appointments.services.exceptions import NotOwnerError

    try:
        appointment = appointment_service.reschedule_appointment(
            patient=patient, appointment_id=appointment_id, new_start_time=new_start_time, new_end_time=new_end_time
        )
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except AppointmentError as exc:
        raise ToolError(str(exc)) from exc
    return {"appointment": _serialize_appointment(appointment)}


# ---------------------------------------------------------------------------
# Registration — this module's import is the only place tools are added
# to the registry (see agents/appointment/service.py's import of this
# module for the side effect).
# ---------------------------------------------------------------------------

register_tool(
    ToolSpec(
        name="search_departments",
        description="List healthcare departments, optionally filtered by name.",
        fields=[ToolField("query", "str", required=False)],
        requires_confirmation=False,
        handler=_handle_search_departments,
    )
)

register_tool(
    ToolSpec(
        name="search_providers",
        description="List active healthcare providers, optionally filtered by department or name.",
        fields=[
            ToolField("department_name", "str", required=False),
            ToolField("query", "str", required=False),
        ],
        requires_confirmation=False,
        handler=_handle_search_providers,
    )
)

register_tool(
    ToolSpec(
        name="find_available_slots",
        description="Find bookable appointment slots, optionally filtered by department, provider, or date.",
        fields=[
            ToolField("department_name", "str", required=False),
            ToolField("provider_id", "int", required=False),
            ToolField("date", "date", required=False),
        ],
        requires_confirmation=False,
        handler=_handle_find_available_slots,
    )
)

register_tool(
    ToolSpec(
        name="get_patient_appointments",
        description="List the requesting patient's own appointments, optionally filtered by status.",
        fields=[
            ToolField(
                "status", "str", required=False,
                allowed_values=("scheduled", "cancelled", "completed", "no_show"),
            )
        ],
        requires_confirmation=False,
        handler=_handle_get_patient_appointments,
    )
)

register_tool(
    ToolSpec(
        name="book_appointment",
        description="Book a specific appointment slot for the requesting patient.",
        fields=[
            ToolField("provider_id", "int"),
            ToolField("start_time", "datetime"),
            ToolField("end_time", "datetime"),
            ToolField("reason", "str", required=False),
        ],
        requires_confirmation=True,
        handler=_handle_book_appointment,
    )
)

register_tool(
    ToolSpec(
        name="cancel_appointment",
        description="Cancel one of the requesting patient's own scheduled appointments.",
        fields=[ToolField("appointment_id", "int")],
        requires_confirmation=True,
        handler=_handle_cancel_appointment,
    )
)

register_tool(
    ToolSpec(
        name="reschedule_appointment",
        description="Move one of the requesting patient's own scheduled appointments to a new time.",
        fields=[
            ToolField("appointment_id", "int"),
            ToolField("new_start_time", "datetime"),
            ToolField("new_end_time", "datetime"),
        ],
        requires_confirmation=True,
        handler=_handle_reschedule_appointment,
    )
)
