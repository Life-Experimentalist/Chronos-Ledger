from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

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
    """

    date: datetime.date
    start: str
    end: str
    purpose: str
    external_ref: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        date = self.date.isoformat()

        start = self.start

        end = self.end

        purpose = self.purpose

        external_ref: None | str | Unset
        if isinstance(self.external_ref, Unset):
            external_ref = UNSET
        else:
            external_ref = self.external_ref

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

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
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

        reservation_create = cls(
            date=date,
            start=start,
            end=end,
            purpose=purpose,
            external_ref=external_ref,
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
