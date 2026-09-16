from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

if TYPE_CHECKING:
    from ..models.attendance_mark_request import AttendanceMarkRequest


T = TypeVar("T", bound="AttendanceBatchRequest")


@_attrs_define
class AttendanceBatchRequest:
    """
    Attributes:
        ledger_instance_id (int):
        records (list[AttendanceMarkRequest]):
    """

    ledger_instance_id: int
    records: list[AttendanceMarkRequest]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ledger_instance_id = self.ledger_instance_id

        records = []
        for records_item_data in self.records:
            records_item = records_item_data.to_dict()
            records.append(records_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ledger_instance_id": ledger_instance_id,
                "records": records,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.attendance_mark_request import (
            AttendanceMarkRequest,
        )

        d = dict(src_dict)
        ledger_instance_id = d.pop("ledger_instance_id")

        records = []
        _records = d.pop("records")
        for records_item_data in _records:
            records_item = AttendanceMarkRequest.from_dict(records_item_data)

            records.append(records_item)

        attendance_batch_request = cls(
            ledger_instance_id=ledger_instance_id,
            records=records,
        )

        attendance_batch_request.additional_properties = d
        return attendance_batch_request

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
