from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.error_code import ErrorCode

if TYPE_CHECKING:
    from ..models.capacity_exceeded_detail import CapacityExceededDetail


T = TypeVar("T", bound="CapacityExceeded")


@_attrs_define
class CapacityExceeded:
    """The body of a 409 with `RESOURCE_CAPACITY_EXCEEDED`: a POOLED resource has not got quantity units free for the whole
    window. conflicts are the bookings that hold it, as in ReservationConflict. taken is the most they hold at any one
    moment of the window, so capacity minus taken is the most this window could still have.

        Attributes:
            code (ErrorCode): What went wrong, for a program to branch on. docs/api.md says what each one means. A code is
                never renamed or reused for a different meaning, but new codes are added, so a client should treat one it does
                not know by its HTTP status. VALIDATION_FAILED is the only code whose detail is a list: FastAPI's field errors
                for a request that did not match the declared shape.
                 Example: NOT_FOUND.
            detail (CapacityExceededDetail):
    """

    code: ErrorCode
    detail: CapacityExceededDetail
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
        from ..models.capacity_exceeded_detail import CapacityExceededDetail  # noqa: PLC0415

        d = dict(src_dict)
        code = ErrorCode(d.pop("code"))

        detail = CapacityExceededDetail.from_dict(d.pop("detail"))

        capacity_exceeded = cls(
            code=code,
            detail=detail,
        )

        capacity_exceeded.additional_properties = d
        return capacity_exceeded

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
