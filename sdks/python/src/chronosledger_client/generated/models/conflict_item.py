from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ConflictItem")


@_attrs_define
class ConflictItem:
    """One of the rows taking part in a clash, with the window it holds. type is `slot` (a weekly slot on one date, id is
    the slot), `ledger_day` (a generated day, id is the ledger row) or `reservation` (a held booking, id is the
    reservation). It is a string rather than an enum so that a new kind of row can be added later; a reader should skip
    a type it does not know. date is the day the window opened on and end_date the day it finishes on, as in
    BusyInterval.

        Attributes:
            type_ (str):  Example: slot.
            id (int):
            date (datetime.date):  Example: 2026-01-05.
            start (str):  Example: 09:00:00.
            end_date (datetime.date):  Example: 2026-01-05.
            end (str):  Example: 10:00:00.
            activity_id (int | None): Null for a reservation.
            resource_id (int | None): Null for a slot or a day that names no resource.
    """

    type_: str
    id: int
    date: datetime.date
    start: str
    end_date: datetime.date
    end: str
    activity_id: int | None
    resource_id: int | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_

        id = self.id

        date = self.date.isoformat()

        start = self.start

        end_date = self.end_date.isoformat()

        end = self.end

        activity_id: int | None
        activity_id = self.activity_id

        resource_id: int | None
        resource_id = self.resource_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "id": id,
                "date": date,
                "start": start,
                "end_date": end_date,
                "end": end,
                "activity_id": activity_id,
                "resource_id": resource_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = d.pop("type")

        id = d.pop("id")

        date = datetime.date.fromisoformat(d.pop("date"))

        start = d.pop("start")

        end_date = datetime.date.fromisoformat(d.pop("end_date"))

        end = d.pop("end")

        def _parse_activity_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        activity_id = _parse_activity_id(d.pop("activity_id"))

        def _parse_resource_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        resource_id = _parse_resource_id(d.pop("resource_id"))

        conflict_item = cls(
            type_=type_,
            id=id,
            date=date,
            start=start,
            end_date=end_date,
            end=end,
            activity_id=activity_id,
            resource_id=resource_id,
        )

        conflict_item.additional_properties = d
        return conflict_item

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
