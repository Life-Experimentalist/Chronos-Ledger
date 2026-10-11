from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="FederatedTokenRequest")


@_attrs_define
class FederatedTokenRequest:
    """
    Attributes:
        token (str): The note, exactly as its issuer minted it. A signed JWT whose `iss` names a registered issuer,
            whose header `kid` names one of that issuer's registered keys, and which carries `aud`, `sub`, `jti`, `iat` and
            `exp`. An `email` claim is what a first-time subject is provisioned from; `name` and `groups` are read if they
            are there.
    """

    token: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        token = self.token

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "token": token,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        token = d.pop("token")

        federated_token_request = cls(
            token=token,
        )

        federated_token_request.additional_properties = d
        return federated_token_request

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
