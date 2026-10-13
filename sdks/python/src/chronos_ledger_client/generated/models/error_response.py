from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.error_code import ErrorCode

T = TypeVar("T", bound="ErrorResponse")


@_attrs_define
class ErrorResponse:
    """The body of every error. detail is for a person to read and code is for a program to branch on. A 409 that names
    what stood in the way has its own schema, with detail as an object; see ReservationConflict.

        Attributes:
            code (ErrorCode): What went wrong, for a program to branch on. docs/api.md says what each one means. A code is
                never renamed or reused for a different meaning, but new codes are added, so a client should treat one it does
                not know by its HTTP status. VALIDATION_FAILED is the only code whose detail is a list: FastAPI's field errors
                for a request that did not match the declared shape.
                 Example: NOT_FOUND.
            detail (str):  Example: Not authorized..
    """

    code: ErrorCode
    detail: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code.value

        detail = self.detail

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
        d = dict(src_dict)
        code = ErrorCode(d.pop("code"))

        detail = d.pop("detail")

        error_response = cls(
            code=code,
            detail=detail,
        )

        error_response.additional_properties = d
        return error_response

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
