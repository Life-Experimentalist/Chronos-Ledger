from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ReverseRsvpCreate")


@_attrs_define
class ReverseRsvpCreate:
    """
    Attributes:
        target_absence_date (datetime.date):  Example: 2026-06-15.
        context_justification (str):  Example: Attending national staff development seminar..
        end_date (datetime.date | Unset): Last day of the absence, inclusive. Omit for a single day. Must not be before
            target_absence_date, or the request gets 422.
             Example: 2026-06-19.
    """

    target_absence_date: datetime.date
    context_justification: str
    end_date: datetime.date | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        target_absence_date = self.target_absence_date.isoformat()

        context_justification = self.context_justification

        end_date: str | Unset = UNSET
        if not isinstance(self.end_date, Unset):
            end_date = self.end_date.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "target_absence_date": target_absence_date,
                "context_justification": context_justification,
            }
        )
        if end_date is not UNSET:
            field_dict["end_date"] = end_date

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        target_absence_date = datetime.date.fromisoformat(d.pop("target_absence_date"))

        context_justification = d.pop("context_justification")

        _end_date = d.pop("end_date", UNSET)
        end_date: datetime.date | Unset
        if isinstance(_end_date, Unset):
            end_date = UNSET
        else:
            end_date = datetime.date.fromisoformat(_end_date)

        reverse_rsvp_create = cls(
            target_absence_date=target_absence_date,
            context_justification=context_justification,
            end_date=end_date,
        )

        reverse_rsvp_create.additional_properties = d
        return reverse_rsvp_create

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
