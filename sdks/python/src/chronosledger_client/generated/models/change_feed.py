from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.change import Change


T = TypeVar("T", bound="ChangeFeed")


@_attrs_define
class ChangeFeed:
    """
    Attributes:
        changes (list[Change] | Unset):
        next_cursor (int | Unset): What the next poll sends as `since`. The cursor that was sent in when nothing
            changed, so storing it unconditionally keeps the caller's place.
    """

    changes: list[Change] | Unset = UNSET
    next_cursor: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        changes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.changes, Unset):
            changes = []
            for changes_item_data in self.changes:
                changes_item = changes_item_data.to_dict()
                changes.append(changes_item)

        next_cursor = self.next_cursor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if changes is not UNSET:
            field_dict["changes"] = changes
        if next_cursor is not UNSET:
            field_dict["next_cursor"] = next_cursor

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.change import Change  # noqa: PLC0415

        d = dict(src_dict)
        _changes = d.pop("changes", UNSET)
        changes: list[Change] | Unset = UNSET
        if _changes is not UNSET:
            changes = []
            for changes_item_data in _changes:
                changes_item = Change.from_dict(changes_item_data)

                changes.append(changes_item)

        next_cursor = d.pop("next_cursor", UNSET)

        change_feed = cls(
            changes=changes,
            next_cursor=next_cursor,
        )

        change_feed.additional_properties = d
        return change_feed

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
