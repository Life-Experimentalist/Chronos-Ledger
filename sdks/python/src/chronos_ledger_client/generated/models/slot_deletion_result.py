from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="SlotDeletionResult")


@_attrs_define
class SlotDeletionResult:
    """
    Attributes:
        ledger_rows_removed (int | Unset): Days from today onward, which were still only plans.
        ledger_rows_detached (int | Unset): Days already past. They keep their room, lead, window and attendance, and
            their master_slot_id becomes null.
    """

    ledger_rows_removed: int | Unset = UNSET
    ledger_rows_detached: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ledger_rows_removed = self.ledger_rows_removed

        ledger_rows_detached = self.ledger_rows_detached

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if ledger_rows_removed is not UNSET:
            field_dict["ledger_rows_removed"] = ledger_rows_removed
        if ledger_rows_detached is not UNSET:
            field_dict["ledger_rows_detached"] = ledger_rows_detached

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        ledger_rows_removed = d.pop("ledger_rows_removed", UNSET)

        ledger_rows_detached = d.pop("ledger_rows_detached", UNSET)

        slot_deletion_result = cls(
            ledger_rows_removed=ledger_rows_removed,
            ledger_rows_detached=ledger_rows_detached,
        )

        slot_deletion_result.additional_properties = d
        return slot_deletion_result

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
