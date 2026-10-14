from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.error_code import ErrorCode

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
            code (ErrorCode): What went wrong, for a program to branch on. docs/api.md says what each one means. A code is
                never renamed or reused for a different meaning, but new codes are added, so a client should treat one it does
                not know by its HTTP status. VALIDATION_FAILED is the only code whose detail is a list: FastAPI's field errors
                for a request that did not match the declared shape.
                 Example: NOT_FOUND.
            detail (CycleActivationConflictDetail):
    """

    code: ErrorCode
    detail: CycleActivationConflictDetail
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code.value

        detail = self.detail.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "code": code,
                "detail": detail,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.cycle_activation_conflict_detail import CycleActivationConflictDetail  # noqa: PLC0415

        d = dict(src_dict)
        code = ErrorCode(d.pop("code"))

        detail = CycleActivationConflictDetail.from_dict(d.pop("detail"))

        cycle_activation_conflict = cls(
            code=code,
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
