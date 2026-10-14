from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="WebhookAttemptResponse")


@_attrs_define
class WebhookAttemptResponse:
    """
    Attributes:
        at (datetime.datetime | Unset):
        status_code (int | None | Unset): Null when no response came back.
        response_ms (int | Unset):
        error (None | str | Unset): Why the attempt failed, briefly. Null on success.
        response_excerpt (None | str | Unset): The start of the response body, cut short.
    """

    at: datetime.datetime | Unset = UNSET
    status_code: int | None | Unset = UNSET
    response_ms: int | Unset = UNSET
    error: None | str | Unset = UNSET
    response_excerpt: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        at: str | Unset = UNSET
        if not isinstance(self.at, Unset):
            at = self.at.isoformat()

        status_code: int | None | Unset
        if isinstance(self.status_code, Unset):
            status_code = UNSET
        else:
            status_code = self.status_code

        response_ms = self.response_ms

        error: None | str | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        else:
            error = self.error

        response_excerpt: None | str | Unset
        if isinstance(self.response_excerpt, Unset):
            response_excerpt = UNSET
        else:
            response_excerpt = self.response_excerpt

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if at is not UNSET:
            field_dict["at"] = at
        if status_code is not UNSET:
            field_dict["status_code"] = status_code
        if response_ms is not UNSET:
            field_dict["response_ms"] = response_ms
        if error is not UNSET:
            field_dict["error"] = error
        if response_excerpt is not UNSET:
            field_dict["response_excerpt"] = response_excerpt

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _at = d.pop("at", UNSET)
        at: datetime.datetime | Unset
        if isinstance(_at, Unset):
            at = UNSET
        else:
            at = datetime.datetime.fromisoformat(_at)

        def _parse_status_code(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        status_code = _parse_status_code(d.pop("status_code", UNSET))

        response_ms = d.pop("response_ms", UNSET)

        def _parse_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        def _parse_response_excerpt(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        response_excerpt = _parse_response_excerpt(d.pop("response_excerpt", UNSET))

        webhook_attempt_response = cls(
            at=at,
            status_code=status_code,
            response_ms=response_ms,
            error=error,
            response_excerpt=response_excerpt,
        )

        webhook_attempt_response.additional_properties = d
        return webhook_attempt_response

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
