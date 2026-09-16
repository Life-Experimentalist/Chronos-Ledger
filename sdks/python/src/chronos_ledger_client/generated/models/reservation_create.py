from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

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
    """

    date: datetime.date
    start: str
    end: str
    purpose: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        date = self.date.isoformat()

        start = self.start

        end = self.end

        purpose = self.purpose

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

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        date = datetime.date.fromisoformat(d.pop("date"))

        start = d.pop("start")

        end = d.pop("end")

        purpose = d.pop("purpose")

        reservation_create = cls(
            date=date,
            start=start,
            end=end,
            purpose=purpose,
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
