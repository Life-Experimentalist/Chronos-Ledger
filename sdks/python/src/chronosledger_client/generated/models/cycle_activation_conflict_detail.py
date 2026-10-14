from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.cycle_activation_conflict_detail_conflicts_item import (
        CycleActivationConflictDetailConflictsItem,
    )


T = TypeVar("T", bound="CycleActivationConflictDetail")


@_attrs_define
class CycleActivationConflictDetail:
    """
    Attributes:
        message (str | Unset):  Example: opening this cycle would put its slots on rooms already taken.
        conflicts (list[CycleActivationConflictDetailConflictsItem] | Unset):
    """

    message: str | Unset = UNSET
    conflicts: list[CycleActivationConflictDetailConflictsItem] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        message = self.message

        conflicts: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.conflicts, Unset):
            conflicts = []
            for conflicts_item_data in self.conflicts:
                conflicts_item = conflicts_item_data.to_dict()
                conflicts.append(conflicts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if message is not UNSET:
            field_dict["message"] = message
        if conflicts is not UNSET:
            field_dict["conflicts"] = conflicts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.cycle_activation_conflict_detail_conflicts_item import (
            CycleActivationConflictDetailConflictsItem,  # noqa: PLC0415
        )

        d = dict(src_dict)
        message = d.pop("message", UNSET)

        _conflicts = d.pop("conflicts", UNSET)
        conflicts: list[CycleActivationConflictDetailConflictsItem] | Unset = UNSET
        if _conflicts is not UNSET:
            conflicts = []
            for conflicts_item_data in _conflicts:
                conflicts_item = CycleActivationConflictDetailConflictsItem.from_dict(conflicts_item_data)

                conflicts.append(conflicts_item)

        cycle_activation_conflict_detail = cls(
            message=message,
            conflicts=conflicts,
        )

        cycle_activation_conflict_detail.additional_properties = d
        return cycle_activation_conflict_detail

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
