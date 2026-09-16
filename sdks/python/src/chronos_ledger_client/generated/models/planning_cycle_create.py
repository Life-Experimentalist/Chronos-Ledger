from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="PlanningCycleCreate")


@_attrs_define
class PlanningCycleCreate:
    """
    Attributes:
        cycle_label (str):  Example: 2026-Fall-Trimester.
        date_bounds_start (datetime.date):  Example: 2026-09-01.
        date_bounds_end (datetime.date):  Example: 2026-12-20.
        operational_status (bool | Unset):  Default: False.
    """

    cycle_label: str
    date_bounds_start: datetime.date
    date_bounds_end: datetime.date
    operational_status: bool | Unset = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cycle_label = self.cycle_label

        date_bounds_start = self.date_bounds_start.isoformat()

        date_bounds_end = self.date_bounds_end.isoformat()

        operational_status = self.operational_status

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "cycle_label": cycle_label,
                "date_bounds_start": date_bounds_start,
                "date_bounds_end": date_bounds_end,
            }
        )
        if operational_status is not UNSET:
            field_dict["operational_status"] = operational_status

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        cycle_label = d.pop("cycle_label")

        date_bounds_start = datetime.date.fromisoformat(d.pop("date_bounds_start"))

        date_bounds_end = datetime.date.fromisoformat(d.pop("date_bounds_end"))

        operational_status = d.pop("operational_status", UNSET)

        planning_cycle_create = cls(
            cycle_label=cycle_label,
            date_bounds_start=date_bounds_start,
            date_bounds_end=date_bounds_end,
            operational_status=operational_status,
        )

        planning_cycle_create.additional_properties = d
        return planning_cycle_create

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
