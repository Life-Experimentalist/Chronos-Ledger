from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.slot_requirement_gap import SlotRequirementGap


T = TypeVar("T", bound="SlotUpdateResult")


@_attrs_define
class SlotUpdateResult:
    """
    Attributes:
        requirements_unmet (list[SlotRequirementGap] | Unset): What the slot's activity or resource requires that its
            next run cannot have. Empty when nothing is required.
        ledger_rows_updated (int | Unset): Days that were still plans and now carry the new lead or room.
        ledger_rows_kept (int | Unset): Days left as they were because attendance or a note has been recorded against
            them. They now disagree with the timetable, and that is deliberate: they record what happened.
        ledger_rows_removed (int | Unset): Days withdrawn because the slot was given another rrule or dtstart and they
            sit on dates it no longer gives. Zero for every other change.
    """

    requirements_unmet: list[SlotRequirementGap] | Unset = UNSET
    ledger_rows_updated: int | Unset = UNSET
    ledger_rows_kept: int | Unset = UNSET
    ledger_rows_removed: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        requirements_unmet: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.requirements_unmet, Unset):
            requirements_unmet = []
            for requirements_unmet_item_data in self.requirements_unmet:
                requirements_unmet_item = requirements_unmet_item_data.to_dict()
                requirements_unmet.append(requirements_unmet_item)

        ledger_rows_updated = self.ledger_rows_updated

        ledger_rows_kept = self.ledger_rows_kept

        ledger_rows_removed = self.ledger_rows_removed

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if requirements_unmet is not UNSET:
            field_dict["requirements_unmet"] = requirements_unmet
        if ledger_rows_updated is not UNSET:
            field_dict["ledger_rows_updated"] = ledger_rows_updated
        if ledger_rows_kept is not UNSET:
            field_dict["ledger_rows_kept"] = ledger_rows_kept
        if ledger_rows_removed is not UNSET:
            field_dict["ledger_rows_removed"] = ledger_rows_removed

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.slot_requirement_gap import SlotRequirementGap  # noqa: PLC0415

        d = dict(src_dict)
        _requirements_unmet = d.pop("requirements_unmet", UNSET)
        requirements_unmet: list[SlotRequirementGap] | Unset = UNSET
        if _requirements_unmet is not UNSET:
            requirements_unmet = []
            for requirements_unmet_item_data in _requirements_unmet:
                requirements_unmet_item = SlotRequirementGap.from_dict(requirements_unmet_item_data)

                requirements_unmet.append(requirements_unmet_item)

        ledger_rows_updated = d.pop("ledger_rows_updated", UNSET)

        ledger_rows_kept = d.pop("ledger_rows_kept", UNSET)

        ledger_rows_removed = d.pop("ledger_rows_removed", UNSET)

        slot_update_result = cls(
            requirements_unmet=requirements_unmet,
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
