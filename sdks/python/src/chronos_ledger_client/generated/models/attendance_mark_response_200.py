from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.verification_metric import VerificationMetric
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttendanceMarkResponse200")


@_attrs_define
class AttendanceMarkResponse200:
    """
    Attributes:
        status (str | Unset):  Example: marked.
        member_id (str | Unset):
        marking_status (VerificationMetric | Unset): Attendance marking status for a member.
    """

    status: str | Unset = UNSET
    member_id: str | Unset = UNSET
    marking_status: VerificationMetric | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        member_id = self.member_id

        marking_status: str | Unset = UNSET
        if not isinstance(self.marking_status, Unset):
            marking_status = self.marking_status.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if member_id is not UNSET:
            field_dict["member_id"] = member_id
        if marking_status is not UNSET:
            field_dict["marking_status"] = marking_status

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status", UNSET)

        member_id = d.pop("member_id", UNSET)

        _marking_status = d.pop("marking_status", UNSET)
        marking_status: VerificationMetric | Unset
        if isinstance(_marking_status, Unset):
            marking_status = UNSET
        else:
            marking_status = VerificationMetric(_marking_status)

        attendance_mark_response_200 = cls(
            status=status,
            member_id=member_id,
            marking_status=marking_status,
        )

        attendance_mark_response_200.additional_properties = d
        return attendance_mark_response_200

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
