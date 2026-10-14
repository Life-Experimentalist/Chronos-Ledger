from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.error_code import ErrorCode

if TYPE_CHECKING:
    from ..models.bookings_would_not_fit_detail import BookingsWouldNotFitDetail


T = TypeVar("T", bound="BookingsWouldNotFit")


@_attrs_define
class BookingsWouldNotFit:
    """The body of a 409 with `RESOURCE_BOOKINGS_WOULD_NOT_FIT`: a change of mode or capacity that bookings still to come
    (from yesterday on) would no longer fit. reservations names them, so the caller can cancel or move them and try
    again.

        Attributes:
            code (ErrorCode): What went wrong, for a program to branch on. docs/api.md says what each one means. A code is
                never renamed or reused for a different meaning, but new codes are added, so a client should treat one it does
                not know by its HTTP status. VALIDATION_FAILED is the only code whose detail is a list: FastAPI's field errors
                for a request that did not match the declared shape.
                 Example: NOT_FOUND.
            detail (BookingsWouldNotFitDetail):
    """

    code: ErrorCode
    detail: BookingsWouldNotFitDetail
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
        from ..models.bookings_would_not_fit_detail import BookingsWouldNotFitDetail  # noqa: PLC0415

        d = dict(src_dict)
        code = ErrorCode(d.pop("code"))

        detail = BookingsWouldNotFitDetail.from_dict(d.pop("detail"))

        bookings_would_not_fit = cls(
            code=code,
            detail=detail,
        )

        bookings_would_not_fit.additional_properties = d
        return bookings_would_not_fit

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
