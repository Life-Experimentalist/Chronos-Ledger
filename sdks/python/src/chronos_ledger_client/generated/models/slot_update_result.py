from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="SlotUpdateResult")


@_attrs_define
class SlotUpdateResult:
    """
    Attributes:
        ledger_rows_updated (int | Unset): Days that were still plans and now carry the new lead or room.
        ledger_rows_kept (int | Unset): Days left as they were because attendance or a note has been recorded against
            them. They now disagree with the timetable, and that is deliberate: they record what happened.
        ledger_rows_removed (int | Unset): Days withdrawn because the slot moved to another weekday and they sit on the
            old one. Zero for every other change.
    """

    ledger_rows_updated: int | Unset = UNSET
    ledger_rows_kept: int | Unset = UNSET
    ledger_rows_removed: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ledger_rows_updated = self.ledger_rows_updated

        ledger_rows_kept = self.ledger_rows_kept

        ledger_rows_removed = self.ledger_rows_removed

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if ledger_rows_updated is not UNSET:
            field_dict["ledger_rows_updated"] = ledger_rows_updated
        if ledger_rows_kept is not UNSET:
            field_dict["ledger_rows_kept"] = ledger_rows_kept
        if ledger_rows_removed is not UNSET:
            field_dict["ledger_rows_removed"] = ledger_rows_removed

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        ledger_rows_updated = d.pop("ledger_rows_updated", UNSET)

        ledger_rows_kept = d.pop("ledger_rows_kept", UNSET)

        ledger_rows_removed = d.pop("ledger_rows_removed", UNSET)

        slot_update_result = cls(
            ledger_rows_updated=ledger_rows_updated,
            ledger_rows_kept=ledger_rows_kept,
            ledger_rows_removed=ledger_rows_removed,
        )

        slot_update_result.additional_properties = d
        return slot_update_result

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
