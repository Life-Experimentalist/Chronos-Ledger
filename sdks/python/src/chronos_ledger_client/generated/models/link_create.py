from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="LinkCreate")


@_attrs_define
class LinkCreate:
    """
    Attributes:
        issuer_id (int): The registration the subject belongs to. Example: 3.
        subject (str): The `sub` notes for this person will carry. Opaque and scoped to its issuer: two issuers may use
            the same string for different people, which is why the pair is what has to be unique.
             Example: u-4417.
        user_id (str): The account that subject signs in as. An `ORG_ADMIN` or `UNIT_ADMIN` account is refused: the role
            map cannot grant either role, and a link would be a way around that.
             Example: EMP1042.
    """

    issuer_id: int
    subject: str
    user_id: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        issuer_id = self.issuer_id

        subject = self.subject

        user_id = self.user_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "issuer_id": issuer_id,
                "subject": subject,
                "user_id": user_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        issuer_id = d.pop("issuer_id")

        subject = d.pop("subject")

        user_id = d.pop("user_id")

        link_create = cls(
            issuer_id=issuer_id,
            subject=subject,
            user_id=user_id,
        )

        link_create.additional_properties = d
        return link_create

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
