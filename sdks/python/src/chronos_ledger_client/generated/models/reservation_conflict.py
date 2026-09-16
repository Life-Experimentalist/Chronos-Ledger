from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.reservation_conflict_detail import ReservationConflictDetail


T = TypeVar("T", bound="ReservationConflict")


@_attrs_define
class ReservationConflict:
    """The body of a 409. What the booking ran into, not merely that it ran into something, so a caller can pick its next
    hour without asking availability again and diffing the answers. Nested under detail like every other error here, so
    one error handler reads them all.

        Attributes:
            detail (ReservationConflictDetail | Unset):
    """

    detail: ReservationConflictDetail | Unset = UNSET
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
        from ..models.reservation_conflict_detail import (
            ReservationConflictDetail,
        )

        d = dict(src_dict)
        _detail = d.pop("detail", UNSET)
        detail: ReservationConflictDetail | Unset
        if isinstance(_detail, Unset):
            detail = UNSET
        else:
            detail = ReservationConflictDetail.from_dict(_detail)

        reservation_conflict = cls(
            detail=detail,
        )

        reservation_conflict.additional_properties = d
        return reservation_conflict

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
