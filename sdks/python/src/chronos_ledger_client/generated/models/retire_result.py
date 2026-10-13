from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="RetireResult")


@_attrs_define
class RetireResult:
    """What retiring an activity or a slot did to the days ahead. Days from today onward that nobody has marked or
    annotated are removed; the ones carrying attendance or a note are kept. Days before today are records and are not
    touched.

        Attributes:
            retired_at (datetime.datetime | Unset):
            slots_retired (int | Unset): Slots marked retired by this request. Always 1 when a slot is retired; for an
                activity, every slot it had that was still live.
            ledger_rows_removed (int | Unset): Days from today onward that were still plans.
            ledger_rows_kept (int | Unset): Days from today onward kept because attendance or a note has been recorded
                against them.
    """

    retired_at: datetime.datetime | Unset = UNSET
    slots_retired: int | Unset = UNSET
    ledger_rows_removed: int | Unset = UNSET
    ledger_rows_kept: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        retired_at: str | Unset = UNSET
        if not isinstance(self.retired_at, Unset):
            retired_at = self.retired_at.isoformat()

        slots_retired = self.slots_retired

        ledger_rows_removed = self.ledger_rows_removed

        ledger_rows_kept = self.ledger_rows_kept

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if retired_at is not UNSET:
            field_dict["retired_at"] = retired_at
        if slots_retired is not UNSET:
            field_dict["slots_retired"] = slots_retired
        if ledger_rows_removed is not UNSET:
            field_dict["ledger_rows_removed"] = ledger_rows_removed
        if ledger_rows_kept is not UNSET:
            field_dict["ledger_rows_kept"] = ledger_rows_kept

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _retired_at = d.pop("retired_at", UNSET)
        retired_at: datetime.datetime | Unset
        if isinstance(_retired_at, Unset):
            retired_at = UNSET
        else:
            retired_at = datetime.datetime.fromisoformat(_retired_at)

        slots_retired = d.pop("slots_retired", UNSET)

        ledger_rows_removed = d.pop("ledger_rows_removed", UNSET)

        ledger_rows_kept = d.pop("ledger_rows_kept", UNSET)

        retire_result = cls(
            retired_at=retired_at,
            slots_retired=slots_retired,
            ledger_rows_removed=ledger_rows_removed,
            ledger_rows_kept=ledger_rows_kept,
        )

        retire_result.additional_properties = d
        return retire_result

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
