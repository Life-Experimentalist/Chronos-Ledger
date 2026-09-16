from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.busy_interval import BusyInterval


T = TypeVar("T", bound="ReservationConflictDetail")


@_attrs_define
class ReservationConflictDetail:
    """
    Attributes:
        message (str | Unset):  Example: the resource is already taken for part of that window.
        conflicts (list[BusyInterval] | Unset):
    """

    message: str | Unset = UNSET
    conflicts: list[BusyInterval] | Unset = UNSET
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
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.busy_interval import BusyInterval

        d = dict(src_dict)
        message = d.pop("message", UNSET)

        _conflicts = d.pop("conflicts", UNSET)
        conflicts: list[BusyInterval] | Unset = UNSET
        if _conflicts is not UNSET:
            conflicts = []
            for conflicts_item_data in _conflicts:
                conflicts_item = BusyInterval.from_dict(conflicts_item_data)

                conflicts.append(conflicts_item)

        reservation_conflict_detail = cls(
            message=message,
            conflicts=conflicts,
        )

        reservation_conflict_detail.additional_properties = d
        return reservation_conflict_detail

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
