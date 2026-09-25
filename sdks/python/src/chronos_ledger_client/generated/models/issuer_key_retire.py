from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="IssuerKeyRetire")


@_attrs_define
class IssuerKeyRetire:
    """
    Attributes:
        not_after (datetime.datetime): The moment the key stops being accepted. A moment in the past stops it now, which
            is what a leaked key wants; a moment in the future is the overlap a planned rotation wants.
    """

    not_after: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        not_after = self.not_after.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "not_after": not_after,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        not_after = datetime.datetime.fromisoformat(d.pop("not_after"))

        issuer_key_retire = cls(
            not_after=not_after,
        )

        issuer_key_retire.additional_properties = d
        return issuer_key_retire

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
