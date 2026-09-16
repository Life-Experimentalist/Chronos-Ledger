from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.cycle_activation_conflict_detail import CycleActivationConflictDetail


T = TypeVar("T", bound="CycleActivationConflict")


@_attrs_define
class CycleActivationConflict:
    """The body of the 409 that refuses to open a planning cycle. Every clash across every slot in the cycle, listed at
    once rather than one per attempt, because an admin opening a hundred slots should not have to make a hundred
    attempts to see the list.

    Each entry is a BusyInterval naming what was already there, plus blocked_slot_id naming which of the cycle's own
    slots wanted it. A pair of the cycle's own slots is listed twice, once from each side, because neither of the two is
    the one at fault.

        Attributes:
            detail (CycleActivationConflictDetail | Unset):
    """

    detail: CycleActivationConflictDetail | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        detail: dict[str, Any] | Unset = UNSET
        if not isinstance(self.detail, Unset):
            detail = self.detail.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if detail is not UNSET:
            field_dict["detail"] = detail

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.cycle_activation_conflict_detail import (
            CycleActivationConflictDetail,
        )

        d = dict(src_dict)
        _detail = d.pop("detail", UNSET)
        detail: CycleActivationConflictDetail | Unset
        if isinstance(_detail, Unset):
            detail = UNSET
        else:
            detail = CycleActivationConflictDetail.from_dict(_detail)

        cycle_activation_conflict = cls(
            detail=detail,
        )

        cycle_activation_conflict.additional_properties = d
        return cycle_activation_conflict

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
