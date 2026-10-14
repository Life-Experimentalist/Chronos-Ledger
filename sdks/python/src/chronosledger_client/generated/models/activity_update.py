from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ActivityUpdate")


@_attrs_define
class ActivityUpdate:
    """Only the title can change. The code and the cycle are what identify an activity, the same pair a CSV upsert matches
    on, so changing either is a different activity. The unit is what a unit admin's permission is checked against, and
    moving an activity between units is left to an import, which only an org admin can run.

        Attributes:
            activity_title (str):
    """

    activity_title: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        activity_title = self.activity_title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "activity_title": activity_title,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        activity_title = d.pop("activity_title")

        activity_update = cls(
            activity_title=activity_title,
        )

        activity_update.additional_properties = d
        return activity_update

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
