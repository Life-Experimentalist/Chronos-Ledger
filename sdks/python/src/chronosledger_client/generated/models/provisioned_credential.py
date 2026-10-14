from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ProvisionedCredential")


@_attrs_define
class ProvisionedCredential:
    """A password generated for a member the import created. Returned only in the upload response and never stored.

    Attributes:
        member_id (str):
        email_address (str):
        initial_password (str):
    """

    member_id: str
    email_address: str
    initial_password: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        member_id = self.member_id

        email_address = self.email_address

        initial_password = self.initial_password

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "member_id": member_id,
                "email_address": email_address,
                "initial_password": initial_password,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        member_id = d.pop("member_id")

        email_address = d.pop("email_address")

        initial_password = d.pop("initial_password")

        provisioned_credential = cls(
            member_id=member_id,
            email_address=email_address,
            initial_password=initial_password,
        )

        provisioned_credential.additional_properties = d
        return provisioned_credential

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
