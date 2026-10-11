from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssuerCreate")


@_attrs_define
class IssuerCreate:
    """
    Attributes:
        issuer (str): The exact `iss` value notes will carry. Compared, never parsed: nothing here fetches it, so it is
            an identifier that happens to look like a URL.
             Example: https://sso.example.internal.
        display_name (str): What an administrator calls this issuer in a list. Example: Campus SSO.
        audience (str): The `aud` this instance answers to. An issuer serving several relying parties should give each
            one its own value, so a note minted for another one is refused here.
             Example: chronos-ledger.
        enabled (bool | Unset): False is refused the same way an unknown issuer is, so turning an issuer off does not
            mean deleting what it was allowed to assert.
             Default: True.
    """

    issuer: str
    display_name: str
    audience: str
    enabled: bool | Unset = True
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        issuer = self.issuer

        display_name = self.display_name

        audience = self.audience

        enabled = self.enabled

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "issuer": issuer,
                "display_name": display_name,
                "audience": audience,
            }
        )
        if enabled is not UNSET:
            field_dict["enabled"] = enabled

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        issuer = d.pop("issuer")

        display_name = d.pop("display_name")

        audience = d.pop("audience")

        enabled = d.pop("enabled", UNSET)

        issuer_create = cls(
            issuer=issuer,
            display_name=display_name,
            audience=audience,
            enabled=enabled,
        )

        issuer_create.additional_properties = d
        return issuer_create

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
