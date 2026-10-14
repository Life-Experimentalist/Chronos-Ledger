from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="LinkResponse")


@_attrs_define
class LinkResponse:
    """
    Attributes:
        id (int | Unset):
        issuer_id (int | Unset):
        subject (str | Unset):
        user_id (str | Unset):
        created_at (datetime.datetime | None | Unset):
    """

    id: int | Unset = UNSET
    issuer_id: int | Unset = UNSET
    subject: str | Unset = UNSET
    user_id: str | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        issuer_id = self.issuer_id

        subject = self.subject

        user_id = self.user_id

        created_at: None | str | Unset
        if isinstance(self.created_at, Unset):
            created_at = UNSET
        elif isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if issuer_id is not UNSET:
            field_dict["issuer_id"] = issuer_id
        if subject is not UNSET:
            field_dict["subject"] = subject
        if user_id is not UNSET:
            field_dict["user_id"] = user_id
        if created_at is not UNSET:
            field_dict["created_at"] = created_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        issuer_id = d.pop("issuer_id", UNSET)

        subject = d.pop("subject", UNSET)

        user_id = d.pop("user_id", UNSET)

        def _parse_created_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                created_at_type_0 = datetime.datetime.fromisoformat(data)

                return created_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        created_at = _parse_created_at(d.pop("created_at", UNSET))

        link_response = cls(
            id=id,
            issuer_id=issuer_id,
            subject=subject,
            user_id=user_id,
            created_at=created_at,
        )

        link_response.additional_properties = d
        return link_response

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
