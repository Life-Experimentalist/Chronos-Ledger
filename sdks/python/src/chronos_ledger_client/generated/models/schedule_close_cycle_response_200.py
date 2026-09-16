from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="ScheduleCloseCycleResponse200")


@_attrs_define
class ScheduleCloseCycleResponse200:
    """
    Attributes:
        message (str | Unset):  Example: Cycle 3 closed.
        ledger_rows_removed (int | Unset): Days from today onward that were withdrawn.
        ledger_rows_kept (int | Unset): Days from today onward kept because they carry attendance or a note.
    """

    message: str | Unset = UNSET
    ledger_rows_removed: int | Unset = UNSET
    ledger_rows_kept: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        message = self.message

        ledger_rows_removed = self.ledger_rows_removed

        ledger_rows_kept = self.ledger_rows_kept

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if message is not UNSET:
            field_dict["message"] = message
        if ledger_rows_removed is not UNSET:
            field_dict["ledger_rows_removed"] = ledger_rows_removed
        if ledger_rows_kept is not UNSET:
            field_dict["ledger_rows_kept"] = ledger_rows_kept

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        message = d.pop("message", UNSET)

        ledger_rows_removed = d.pop("ledger_rows_removed", UNSET)

        ledger_rows_kept = d.pop("ledger_rows_kept", UNSET)

        schedule_close_cycle_response_200 = cls(
            message=message,
            ledger_rows_removed=ledger_rows_removed,
            ledger_rows_kept=ledger_rows_kept,
        )

        schedule_close_cycle_response_200.additional_properties = d
        return schedule_close_cycle_response_200

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
