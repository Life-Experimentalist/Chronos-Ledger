from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.reservation_create_assignments_type_0 import ReservationCreateAssignmentsType0


T = TypeVar("T", bound="ReservationCreate")


@_attrs_define
class ReservationCreate:
    """
    Attributes:
        date (datetime.date): The day the window opens on. A window that runs past midnight finishes on the day after
            this one.
             Example: 2026-01-06.
        start (str):  Example: 14:00.
        end (str): Earlier than the start means the window runs past midnight and finishes on the day after `date`:
            22:00 to 06:00 is an eight hour night shift. Equal to the start is refused, because 09:00 to 09:00 is either
            nothing at all or a full day and there is no way to tell which was meant.
             Example: 15:00.
        purpose (str):  Example: Ward round.
        external_ref (None | str | Unset): The caller's own identifier for the booking, kept exactly as sent. Unique per
            caller: a second booking under a reference the caller already used, cancelled or not, is a 409 with
            `RESERVATION_EXTERNAL_REF_TAKEN`. Find the booking again with `GET
            /api/v1/resources/reservations?external_ref=`. Optional, and any number of bookings may leave it unset.
             Example: visit-42.
        quantity (int | Unset): How many units of a POOLED resource to take, 1 when left out. Above 1 on any other
            resource is a 422. Part of what a retry is compared on only when it is sent, so a retry that leaves it out still
            matches a booking made before the field existed.
             Example: 2.
        assignments (None | ReservationCreateAssignmentsType0 | Unset): Which resources to hold for the requirements
            that name a kind of resource: a resource class code (`ROOM`, `PERSON` or one the organization made) mapped to
            resource ids, used in order. Where it says nothing, or runs out, the engine picks the first free resources of
            the kind by code. An id that is not an active resource of that kind in this organization, or that no requirement
            asks for, is a 422. A named resource that is not free is a gap and is not swapped for another. Part of what a
            retry is compared on only when it is sent.
             Example: {'PERSON': [12, 15]}.
    """

    date: datetime.date
    start: str
    end: str
    purpose: str
    external_ref: None | str | Unset = UNSET
    quantity: int | Unset = UNSET
    assignments: None | ReservationCreateAssignmentsType0 | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.reservation_create_assignments_type_0 import (
            ReservationCreateAssignmentsType0,  # noqa: PLC0415
        )

        date = self.date.isoformat()

        start = self.start

        end = self.end

        purpose = self.purpose

        external_ref: None | str | Unset
        if isinstance(self.external_ref, Unset):
            external_ref = UNSET
        else:
            external_ref = self.external_ref

        quantity = self.quantity

        assignments: dict[str, Any] | None | Unset
        if isinstance(self.assignments, Unset):
            assignments = UNSET
        elif isinstance(self.assignments, ReservationCreateAssignmentsType0):
            assignments = self.assignments.to_dict()
        else:
            assignments = self.assignments

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "date": date,
                "start": start,
                "end": end,
                "purpose": purpose,
            }
        )
        if external_ref is not UNSET:
            field_dict["external_ref"] = external_ref
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if assignments is not UNSET:
            field_dict["assignments"] = assignments

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reservation_create_assignments_type_0 import (
            ReservationCreateAssignmentsType0,  # noqa: PLC0415
        )

        d = dict(src_dict)
        date = datetime.date.fromisoformat(d.pop("date"))

        start = d.pop("start")

        end = d.pop("end")

        purpose = d.pop("purpose")

        def _parse_external_ref(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        external_ref = _parse_external_ref(d.pop("external_ref", UNSET))

        quantity = d.pop("quantity", UNSET)

        def _parse_assignments(data: object) -> None | ReservationCreateAssignmentsType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                assignments_type_0 = ReservationCreateAssignmentsType0.from_dict(data)

                return assignments_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ReservationCreateAssignmentsType0 | Unset, data)

        assignments = _parse_assignments(d.pop("assignments", UNSET))

        reservation_create = cls(
            date=date,
            start=start,
            end=end,
            purpose=purpose,
            external_ref=external_ref,
            quantity=quantity,
            assignments=assignments,
        )

        reservation_create.additional_properties = d
        return reservation_create

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
