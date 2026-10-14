from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="GuestExtensionRequest")


@_attrs_define
class GuestExtensionRequest:
    """
    Attributes:
        minutes (int): How much longer the visit gets. The ceiling is GUEST_VISIT_EXTENSION_MAX_MINUTES, which defaults
            to 240 and is checked in the route rather than here, because a schema is fixed at import and the setting is an
            operator's to change.
             Example: 30.
    """

    minutes: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        minutes = self.minutes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "minutes": minutes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        minutes = d.pop("minutes")

        guest_extension_request = cls(
            minutes=minutes,
        )

        guest_extension_request.additional_properties = d
        return guest_extension_request

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
