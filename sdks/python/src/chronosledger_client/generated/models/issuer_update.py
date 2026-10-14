from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssuerUpdate")


@_attrs_define
class IssuerUpdate:
    """Every field is optional and one left out is unchanged. `issuer` cannot be changed: it is the value notes already in
    the wild carry, and editing it would retarget a registration rather than register another.

        Attributes:
            display_name (str | Unset):
            audience (str | Unset):
            enabled (bool | Unset):
    """

    display_name: str | Unset = UNSET
    audience: str | Unset = UNSET
    enabled: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        display_name = self.display_name

        audience = self.audience

        enabled = self.enabled

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if display_name is not UNSET:
            field_dict["display_name"] = display_name
        if audience is not UNSET:
            field_dict["audience"] = audience
        if enabled is not UNSET:
            field_dict["enabled"] = enabled

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        display_name = d.pop("display_name", UNSET)

        audience = d.pop("audience", UNSET)

        enabled = d.pop("enabled", UNSET)

        issuer_update = cls(
            display_name=display_name,
            audience=audience,
            enabled=enabled,
        )

        issuer_update.additional_properties = d
        return issuer_update

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
