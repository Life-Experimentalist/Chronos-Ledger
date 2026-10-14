from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

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

    `resource_overbooked` is a POOLED resource whose reservations together hold more than its capacity. date to end is
    the whole stretch in which they do, items is every reservation open in it, and capacity and taken say by how much:
    taken is the most held at any moment of the stretch. capacity and taken are null on the other kinds. Two
    reservations on a pooled resource are never a `resource_overlap`, and reservations on a SHARED resource are never
    reported at all.

    `requirement_unmet` is a weekly slot or a generated day, its one item, whose activity or resource requires something
    the window cannot have. requirement_id names the requirement and message says what is missing; both are null on the
    other kinds. resource_id is the row's own resource. It is a report: nothing is refused for it.

        Attributes:
            kind (str):  Example: resource_overlap.
            resource_id (int | None):
            member_id (None | str):
            date (datetime.date):  Example: 2026-01-05.
            start (str):  Example: 09:30:00.
            end_date (datetime.date):  Example: 2026-01-05.
            end (str):  Example: 10:00:00.
            items (list[ConflictItem]):
            capacity (int | None | Unset): The pool's capacity, on `resource_overbooked` only.
            taken (int | None | Unset): The most units held at once, on `resource_overbooked` only.
            requirement_id (int | None | Unset): The requirement that is not met, on `requirement_unmet` only.
            message (None | str | Unset): What is missing, on `requirement_unmet` only.
    """

    kind: str
    resource_id: int | None
    member_id: None | str
    date: datetime.date
    start: str
    end_date: datetime.date
    end: str
    items: list[ConflictItem]
    capacity: int | None | Unset = UNSET
    taken: int | None | Unset = UNSET
    requirement_id: int | None | Unset = UNSET
    message: None | str | Unset = UNSET
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

        capacity: int | None | Unset
        if isinstance(self.capacity, Unset):
            capacity = UNSET
        else:
            capacity = self.capacity

        taken: int | None | Unset
        if isinstance(self.taken, Unset):
            taken = UNSET
        else:
            taken = self.taken

        requirement_id: int | None | Unset
        if isinstance(self.requirement_id, Unset):
            requirement_id = UNSET
        else:
            requirement_id = self.requirement_id

        message: None | str | Unset
        if isinstance(self.message, Unset):
            message = UNSET
        else:
            message = self.message

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
        if capacity is not UNSET:
            field_dict["capacity"] = capacity
        if taken is not UNSET:
            field_dict["taken"] = taken
        if requirement_id is not UNSET:
            field_dict["requirement_id"] = requirement_id
        if message is not UNSET:
            field_dict["message"] = message

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

        def _parse_capacity(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        capacity = _parse_capacity(d.pop("capacity", UNSET))

        def _parse_taken(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        taken = _parse_taken(d.pop("taken", UNSET))

        def _parse_requirement_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        requirement_id = _parse_requirement_id(d.pop("requirement_id", UNSET))

        def _parse_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        message = _parse_message(d.pop("message", UNSET))

        conflict = cls(
            kind=kind,
            resource_id=resource_id,
            member_id=member_id,
            date=date,
            start=start,
            end_date=end_date,
            end=end,
            items=items,
            capacity=capacity,
            taken=taken,
            requirement_id=requirement_id,
            message=message,
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
