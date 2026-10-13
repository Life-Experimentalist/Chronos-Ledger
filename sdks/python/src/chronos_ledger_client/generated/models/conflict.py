from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.conflict_item import ConflictItem


T = TypeVar("T", bound="Conflict")


@_attrs_define
class Conflict:
    """Two rows that hold the same resource, or the same member, at the same moment. kind is `resource_overlap`, with
    resource_id set and member_id null, or `member_overlap`, with member_id set and resource_id null. Like
    ConflictItem.type, kind is a string so that later kinds can be added; a reader should skip a kind it does not know.
    date, start, end_date and end are the part of the two windows they share. items is a list rather than a pair so that
    a later kind can name more than two rows.

        Attributes:
            kind (str):  Example: resource_overlap.
            resource_id (int | None):
            member_id (None | str):
            date (datetime.date):  Example: 2026-01-05.
            start (str):  Example: 09:30:00.
            end_date (datetime.date):  Example: 2026-01-05.
            end (str):  Example: 10:00:00.
            items (list[ConflictItem]):
    """

    kind: str
    resource_id: int | None
    member_id: None | str
    date: datetime.date
    start: str
    end_date: datetime.date
    end: str
    items: list[ConflictItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        kind = self.kind

        resource_id: int | None
        resource_id = self.resource_id

        member_id: None | str
        member_id = self.member_id

        date = self.date.isoformat()

        start = self.start

        end_date = self.end_date.isoformat()

        end = self.end

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "kind": kind,
                "resource_id": resource_id,
                "member_id": member_id,
                "date": date,
                "start": start,
                "end_date": end_date,
                "end": end,
                "items": items,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.conflict_item import ConflictItem  # noqa: PLC0415

        d = dict(src_dict)
        kind = d.pop("kind")

        def _parse_resource_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        resource_id = _parse_resource_id(d.pop("resource_id"))

        def _parse_member_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        member_id = _parse_member_id(d.pop("member_id"))

        date = datetime.date.fromisoformat(d.pop("date"))

        start = d.pop("start")

        end_date = datetime.date.fromisoformat(d.pop("end_date"))

        end = d.pop("end")

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = ConflictItem.from_dict(items_item_data)

            items.append(items_item)

        conflict = cls(
            kind=kind,
            resource_id=resource_id,
            member_id=member_id,
            date=date,
            start=start,
            end_date=end_date,
            end=end,
            items=items,
        )

        conflict.additional_properties = d
        return conflict

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
