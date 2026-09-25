from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssuerKeyCreate")


@_attrs_define
class IssuerKeyCreate:
    """
    Attributes:
        kid (str): The `kid` the note header will carry. A note is verified against the key it names and no other, so an
            overlap during a rotation is two registered keys rather than two candidates per note.
             Example: 2026-key-a.
        public_key (str): An Ed25519 public key in PEM form. Loaded when it is registered, so a key that cannot be read
            is refused here rather than turning every note that names it into a 401 nobody can explain.
             Example: -----BEGIN PUBLIC KEY-----
            MCowBQYDK2VwAyEAWJyyHHtL1RwC53ABtyd229BalcSDxdE3P02wXuDoeV4=
            -----END PUBLIC KEY-----
            .
        not_before (datetime.datetime | None | Unset): When the key starts being accepted. Omitted means now.
        not_after (datetime.datetime | None | Unset): When it stops. Omitted is a key with no planned retirement, which
            is the ordinary case until a rotation gives it one.
    """

    kid: str
    public_key: str
    not_before: datetime.datetime | None | Unset = UNSET
    not_after: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        kid = self.kid

        public_key = self.public_key

        not_before: None | str | Unset
        if isinstance(self.not_before, Unset):
            not_before = UNSET
        elif isinstance(self.not_before, datetime.datetime):
            not_before = self.not_before.isoformat()
        else:
            not_before = self.not_before

        not_after: None | str | Unset
        if isinstance(self.not_after, Unset):
            not_after = UNSET
        elif isinstance(self.not_after, datetime.datetime):
            not_after = self.not_after.isoformat()
        else:
            not_after = self.not_after

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "kid": kid,
                "public_key": public_key,
            }
        )
        if not_before is not UNSET:
            field_dict["not_before"] = not_before
        if not_after is not UNSET:
            field_dict["not_after"] = not_after

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        kid = d.pop("kid")

        public_key = d.pop("public_key")

        def _parse_not_before(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                not_before_type_0 = datetime.datetime.fromisoformat(data)

                return not_before_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        not_before = _parse_not_before(d.pop("not_before", UNSET))

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

        issuer_key_create = cls(
            kid=kid,
            public_key=public_key,
            not_before=not_before,
            not_after=not_after,
        )

        issuer_key_create.additional_properties = d
        return issuer_key_create

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
