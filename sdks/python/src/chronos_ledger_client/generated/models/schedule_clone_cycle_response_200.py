from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ScheduleCloneCycleResponse200")


@_attrs_define
class ScheduleCloneCycleResponse200:
    """
    Attributes:
        cloned (int | Unset): Activities copied.
        cloned_slots (int | Unset): Weekly slots copied.
    """

    cloned: int | Unset = UNSET
    cloned_slots: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cloned = self.cloned

        cloned_slots = self.cloned_slots

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if cloned is not UNSET:
            field_dict["cloned"] = cloned
        if cloned_slots is not UNSET:
            field_dict["cloned_slots"] = cloned_slots

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cloned = d.pop("cloned", UNSET)

        cloned_slots = d.pop("cloned_slots", UNSET)

        schedule_clone_cycle_response_200 = cls(
            cloned=cloned,
            cloned_slots=cloned_slots,
        )

        schedule_clone_cycle_response_200.additional_properties = d
        return schedule_clone_cycle_response_200

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
