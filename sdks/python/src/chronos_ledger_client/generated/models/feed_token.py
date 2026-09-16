from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="FeedToken")


@_attrs_define
class FeedToken:
    """
    Attributes:
        feed_token (str | Unset): 256 bits out of the system random source, hex encoded.
        feed_path (str | Unset): The feed path this token opens, relative to the server root.
             Example: /api/v1/sync/user-feed/1f4a9c2e.ics.
    """

    feed_token: str | Unset = UNSET
    feed_path: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        feed_token = self.feed_token

        feed_path = self.feed_path

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if feed_token is not UNSET:
            field_dict["feed_token"] = feed_token
        if feed_path is not UNSET:
            field_dict["feed_path"] = feed_path

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        feed_token = d.pop("feed_token", UNSET)

        feed_path = d.pop("feed_path", UNSET)

        feed_token = cls(
            feed_token=feed_token,
            feed_path=feed_path,
        )

        feed_token.additional_properties = d
        return feed_token

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
