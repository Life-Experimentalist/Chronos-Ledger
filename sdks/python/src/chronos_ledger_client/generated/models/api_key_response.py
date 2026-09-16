from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ApiKeyResponse")


@_attrs_define
class ApiKeyResponse:
    """
    Attributes:
        id (int | Unset):
        key_prefix (str | Unset): The first 12 characters, enough to tell two keys apart. Example: ck_8Kd2mQ7x.
        label (str | Unset):
        user_id (str | Unset):
        scopes (str | Unset): Comma separated, or `*` for a key that was never narrowed. Example:
            resources:read,schedule:read.
        expires_at (datetime.datetime | None | Unset):
        created_at (datetime.datetime | None | Unset):
    """

    id: int | Unset = UNSET
    key_prefix: str | Unset = UNSET
    label: str | Unset = UNSET
    user_id: str | Unset = UNSET
    scopes: str | Unset = UNSET
    expires_at: datetime.datetime | None | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        key_prefix = self.key_prefix

        label = self.label

        user_id = self.user_id

        scopes = self.scopes

        expires_at: None | str | Unset
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        elif isinstance(self.expires_at, datetime.datetime):
            expires_at = self.expires_at.isoformat()
        else:
            expires_at = self.expires_at

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
        if key_prefix is not UNSET:
            field_dict["key_prefix"] = key_prefix
        if label is not UNSET:
            field_dict["label"] = label
        if user_id is not UNSET:
            field_dict["user_id"] = user_id
        if scopes is not UNSET:
            field_dict["scopes"] = scopes
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at
        if created_at is not UNSET:
            field_dict["created_at"] = created_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        key_prefix = d.pop("key_prefix", UNSET)

        label = d.pop("label", UNSET)

        user_id = d.pop("user_id", UNSET)

        scopes = d.pop("scopes", UNSET)

        def _parse_expires_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                expires_at_type_0 = datetime.datetime.fromisoformat(data)

                return expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

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

        api_key_response = cls(
            id=id,
            key_prefix=key_prefix,
            label=label,
            user_id=user_id,
            scopes=scopes,
            expires_at=expires_at,
            created_at=created_at,
        )

        api_key_response.additional_properties = d
        return api_key_response

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
