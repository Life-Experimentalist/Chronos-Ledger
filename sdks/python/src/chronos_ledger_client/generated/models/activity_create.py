from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ActivityCreate")


@_attrs_define
class ActivityCreate:
    """An activity, the same one a CSV row names by code, title and unit. It starts with no slots and no members; those are
    added with POST /schedule/slots and POST /schedule/activities/{activity_id}/enrollments.

        Attributes:
            activity_code (str): Unique within the cycle, retired activities included. Example: CS201.
            activity_title (str):
            unit_code (str): A UNIT_ADMIN may only name their own unit.
            cycle_id (int):
    """

    activity_code: str
    activity_title: str
    unit_code: str
    cycle_id: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        activity_code = self.activity_code

        activity_title = self.activity_title

        unit_code = self.unit_code

        cycle_id = self.cycle_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "activity_code": activity_code,
                "activity_title": activity_title,
                "unit_code": unit_code,
                "cycle_id": cycle_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        activity_code = d.pop("activity_code")

        activity_title = d.pop("activity_title")

        unit_code = d.pop("unit_code")

        cycle_id = d.pop("cycle_id")

        activity_create = cls(
            activity_code=activity_code,
            activity_title=activity_title,
            unit_code=unit_code,
            cycle_id=cycle_id,
        )

        activity_create.additional_properties = d
        return activity_create

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
