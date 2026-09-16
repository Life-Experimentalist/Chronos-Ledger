from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AuditRecord")


@_attrs_define
class AuditRecord:
    """
    Attributes:
        id (int | Unset):
        at (datetime.datetime | Unset):
        actor_id (None | str | Unset): The account, or null when the request carried no valid credentials.
        api_key_id (int | None | Unset): The key used, or null for a signed-in person.
        method (str | Unset):
        path (str | Unset):
        status_code (int | Unset):
    """

    id: int | Unset = UNSET
    at: datetime.datetime | Unset = UNSET
    actor_id: None | str | Unset = UNSET
    api_key_id: int | None | Unset = UNSET
    method: str | Unset = UNSET
    path: str | Unset = UNSET
    status_code: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        at: str | Unset = UNSET
        if not isinstance(self.at, Unset):
            at = self.at.isoformat()

        actor_id: None | str | Unset
        if isinstance(self.actor_id, Unset):
            actor_id = UNSET
        else:
            actor_id = self.actor_id

        api_key_id: int | None | Unset
        if isinstance(self.api_key_id, Unset):
            api_key_id = UNSET
        else:
            api_key_id = self.api_key_id

        method = self.method

        path = self.path

        status_code = self.status_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if at is not UNSET:
            field_dict["at"] = at
        if actor_id is not UNSET:
            field_dict["actor_id"] = actor_id
        if api_key_id is not UNSET:
            field_dict["api_key_id"] = api_key_id
        if method is not UNSET:
            field_dict["method"] = method
        if path is not UNSET:
            field_dict["path"] = path
        if status_code is not UNSET:
            field_dict["status_code"] = status_code

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        _at = d.pop("at", UNSET)
        at: datetime.datetime | Unset
        if isinstance(_at, Unset):
            at = UNSET
        else:
            at = datetime.datetime.fromisoformat(_at)

        def _parse_actor_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        actor_id = _parse_actor_id(d.pop("actor_id", UNSET))

        def _parse_api_key_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        api_key_id = _parse_api_key_id(d.pop("api_key_id", UNSET))

        method = d.pop("method", UNSET)

        path = d.pop("path", UNSET)

        status_code = d.pop("status_code", UNSET)

        audit_record = cls(
            id=id,
            at=at,
            actor_id=actor_id,
            api_key_id=api_key_id,
            method=method,
            path=path,
            status_code=status_code,
        )

        audit_record.additional_properties = d
        return audit_record

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
