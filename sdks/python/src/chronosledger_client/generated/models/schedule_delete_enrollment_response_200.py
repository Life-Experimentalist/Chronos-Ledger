from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ScheduleDeleteEnrollmentResponse200")


@_attrs_define
class ScheduleDeleteEnrollmentResponse200:
    """
    Attributes:
        activity_id (int | Unset):
        member_id (str | Unset):
        removed (bool | Unset):
    """

    activity_id: int | Unset = UNSET
    member_id: str | Unset = UNSET
    removed: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        activity_id = self.activity_id

        member_id = self.member_id

        removed = self.removed

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if activity_id is not UNSET:
            field_dict["activity_id"] = activity_id
        if member_id is not UNSET:
            field_dict["member_id"] = member_id
        if removed is not UNSET:
            field_dict["removed"] = removed

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        activity_id = d.pop("activity_id", UNSET)

        member_id = d.pop("member_id", UNSET)

        removed = d.pop("removed", UNSET)

        schedule_delete_enrollment_response_200 = cls(
            activity_id=activity_id,
            member_id=member_id,
            removed=removed,
        )

        schedule_delete_enrollment_response_200.additional_properties = d
        return schedule_delete_enrollment_response_200

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
