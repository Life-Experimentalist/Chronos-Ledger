from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PlanningCycleResponse")


@_attrs_define
class PlanningCycleResponse:
    """
    Attributes:
        id (int | Unset):
        cycle_label (str | Unset):
        date_bounds_start (datetime.date | Unset):
        date_bounds_end (datetime.date | Unset):
        operational_status (bool | Unset):
    """

    id: int | Unset = UNSET
    cycle_label: str | Unset = UNSET
    date_bounds_start: datetime.date | Unset = UNSET
    date_bounds_end: datetime.date | Unset = UNSET
    operational_status: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        cycle_label = self.cycle_label

        date_bounds_start: str | Unset = UNSET
        if not isinstance(self.date_bounds_start, Unset):
            date_bounds_start = self.date_bounds_start.isoformat()

        date_bounds_end: str | Unset = UNSET
        if not isinstance(self.date_bounds_end, Unset):
            date_bounds_end = self.date_bounds_end.isoformat()

        operational_status = self.operational_status

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if cycle_label is not UNSET:
            field_dict["cycle_label"] = cycle_label
        if date_bounds_start is not UNSET:
            field_dict["date_bounds_start"] = date_bounds_start
        if date_bounds_end is not UNSET:
            field_dict["date_bounds_end"] = date_bounds_end
        if operational_status is not UNSET:
            field_dict["operational_status"] = operational_status

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        cycle_label = d.pop("cycle_label", UNSET)

        _date_bounds_start = d.pop("date_bounds_start", UNSET)
        date_bounds_start: datetime.date | Unset
        if isinstance(_date_bounds_start, Unset):
            date_bounds_start = UNSET
        else:
            date_bounds_start = datetime.date.fromisoformat(_date_bounds_start)

        _date_bounds_end = d.pop("date_bounds_end", UNSET)
        date_bounds_end: datetime.date | Unset
        if isinstance(_date_bounds_end, Unset):
            date_bounds_end = UNSET
        else:
            date_bounds_end = datetime.date.fromisoformat(_date_bounds_end)

        operational_status = d.pop("operational_status", UNSET)

        planning_cycle_response = cls(
            id=id,
            cycle_label=cycle_label,
            date_bounds_start=date_bounds_start,
            date_bounds_end=date_bounds_end,
            operational_status=operational_status,
        )

        planning_cycle_response.additional_properties = d
        return planning_cycle_response

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
