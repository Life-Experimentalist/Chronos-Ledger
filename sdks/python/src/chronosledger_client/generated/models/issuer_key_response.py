from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssuerKeyResponse")


@_attrs_define
class IssuerKeyResponse:
    """
    Attributes:
        id (int | Unset):
        issuer_id (int | Unset):
        kid (str | Unset):
        public_key (str | Unset): Read back in full. It is a public key, so there is nothing here a leak would cost
            anybody, and an integrator comparing what was registered against what is being signed with needs to see it.
        not_before (datetime.datetime | Unset):
        not_after (datetime.datetime | None | Unset):
        created_at (datetime.datetime | None | Unset):
    """

    id: int | Unset = UNSET
    issuer_id: int | Unset = UNSET
    kid: str | Unset = UNSET
    public_key: str | Unset = UNSET
    not_before: datetime.datetime | Unset = UNSET
    not_after: datetime.datetime | None | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        issuer_id = self.issuer_id

        kid = self.kid

        public_key = self.public_key

        not_before: str | Unset = UNSET
        if not isinstance(self.not_before, Unset):
            not_before = self.not_before.isoformat()

        not_after: None | str | Unset
        if isinstance(self.not_after, Unset):
            not_after = UNSET
        elif isinstance(self.not_after, datetime.datetime):
            not_after = self.not_after.isoformat()
        else:
            not_after = self.not_after

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
        if kid is not UNSET:
            field_dict["kid"] = kid
        if public_key is not UNSET:
            field_dict["public_key"] = public_key
        if not_before is not UNSET:
            field_dict["not_before"] = not_before
        if not_after is not UNSET:
            field_dict["not_after"] = not_after
        if created_at is not UNSET:
            field_dict["created_at"] = created_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        issuer_id = d.pop("issuer_id", UNSET)

        kid = d.pop("kid", UNSET)

        public_key = d.pop("public_key", UNSET)

        _not_before = d.pop("not_before", UNSET)
        not_before: datetime.datetime | Unset
        if isinstance(_not_before, Unset):
            not_before = UNSET
        else:
            not_before = datetime.datetime.fromisoformat(_not_before)

        def _parse_not_after(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                not_after_type_0 = datetime.datetime.fromisoformat(data)

                return not_after_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        not_after = _parse_not_after(d.pop("not_after", UNSET))

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

        issuer_key_response = cls(
            id=id,
            issuer_id=issuer_id,
            kid=kid,
            public_key=public_key,
            not_before=not_before,
            not_after=not_after,
            created_at=created_at,
        )

        issuer_key_response.additional_properties = d
        return issuer_key_response

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
