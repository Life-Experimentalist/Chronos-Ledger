from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.verification_metric import VerificationMetric
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttendanceResponse")


@_attrs_define
class AttendanceResponse:
    """
    Attributes:
        id (int | Unset):
        ledger_instance_id (int | Unset):
        member_id (str | Unset):
        marking_status (VerificationMetric | Unset): Attendance marking status for a member.
        authorizing_agent_id (None | str | Unset): User ID of the person who marked attendance (may be staff for batch).
        modification_timestamp (datetime.datetime | Unset):
    """

    id: int | Unset = UNSET
    ledger_instance_id: int | Unset = UNSET
    member_id: str | Unset = UNSET
    marking_status: VerificationMetric | Unset = UNSET
    authorizing_agent_id: None | str | Unset = UNSET
    modification_timestamp: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        ledger_instance_id = self.ledger_instance_id

        member_id = self.member_id

        marking_status: str | Unset = UNSET
        if not isinstance(self.marking_status, Unset):
            marking_status = self.marking_status.value

        authorizing_agent_id: None | str | Unset
        if isinstance(self.authorizing_agent_id, Unset):
            authorizing_agent_id = UNSET
        else:
            authorizing_agent_id = self.authorizing_agent_id

        modification_timestamp: str | Unset = UNSET
        if not isinstance(self.modification_timestamp, Unset):
            modification_timestamp = self.modification_timestamp.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if ledger_instance_id is not UNSET:
            field_dict["ledger_instance_id"] = ledger_instance_id
        if member_id is not UNSET:
            field_dict["member_id"] = member_id
        if marking_status is not UNSET:
            field_dict["marking_status"] = marking_status
        if authorizing_agent_id is not UNSET:
            field_dict["authorizing_agent_id"] = authorizing_agent_id
        if modification_timestamp is not UNSET:
            field_dict["modification_timestamp"] = modification_timestamp

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        ledger_instance_id = d.pop("ledger_instance_id", UNSET)

        member_id = d.pop("member_id", UNSET)

        _marking_status = d.pop("marking_status", UNSET)
        marking_status: VerificationMetric | Unset
        if isinstance(_marking_status, Unset):
            marking_status = UNSET
        else:
            marking_status = VerificationMetric(_marking_status)

        def _parse_authorizing_agent_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        authorizing_agent_id = _parse_authorizing_agent_id(d.pop("authorizing_agent_id", UNSET))

        _modification_timestamp = d.pop("modification_timestamp", UNSET)
        modification_timestamp: datetime.datetime | Unset
        if isinstance(_modification_timestamp, Unset):
            modification_timestamp = UNSET
        else:
            modification_timestamp = datetime.datetime.fromisoformat(_modification_timestamp)

        attendance_response = cls(
            id=id,
            ledger_instance_id=ledger_instance_id,
            member_id=member_id,
            marking_status=marking_status,
            authorizing_agent_id=authorizing_agent_id,
            modification_timestamp=modification_timestamp,
        )

        attendance_response.additional_properties = d
        return attendance_response

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
