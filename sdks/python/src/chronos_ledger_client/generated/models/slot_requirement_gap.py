from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SlotRequirementGap")


@_attrs_define
class SlotRequirementGap:
    """A requirement of a slot's activity or resource that the slot's next run on the date given cannot have. A report;
    nothing is refused. The CSV import adds slot_id.

        Attributes:
            requirement_id (int | Unset):
            date (datetime.date | Unset):
            message (str | Unset):
            slot_id (int | Unset):
    """

    requirement_id: int | Unset = UNSET
    date: datetime.date | Unset = UNSET
    message: str | Unset = UNSET
    slot_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        requirement_id = self.requirement_id

        date: str | Unset = UNSET
        if not isinstance(self.date, Unset):
            date = self.date.isoformat()

        message = self.message

        slot_id = self.slot_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if requirement_id is not UNSET:
            field_dict["requirement_id"] = requirement_id
        if date is not UNSET:
            field_dict["date"] = date
        if message is not UNSET:
            field_dict["message"] = message
        if slot_id is not UNSET:
            field_dict["slot_id"] = slot_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        requirement_id = d.pop("requirement_id", UNSET)

        _date = d.pop("date", UNSET)
        date: datetime.date | Unset
        if isinstance(_date, Unset):
            date = UNSET
        else:
            date = datetime.date.fromisoformat(_date)

        message = d.pop("message", UNSET)

        slot_id = d.pop("slot_id", UNSET)

        slot_requirement_gap = cls(
            requirement_id=requirement_id,
            date=date,
            message=message,
            slot_id=slot_id,
        )

        slot_requirement_gap.additional_properties = d
        return slot_requirement_gap

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
