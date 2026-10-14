from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="KeptDay")


@_attrs_define
class KeptDay:
    """A day a re-import left as it was, because attendance or a note has been recorded against it. It keeps the room, lead
    and window it was held with.

        Attributes:
            id (int): The ledger entry, as GET /schedule/ledger returns it.
            date (datetime.date):
            activity_code (str):
            master_slot_id (int): The slot the file corrected.
            time_window_start (str):
            room (None | str): The room the day still has, not the one the file names.
    """

    id: int
    date: datetime.date
    activity_code: str
    master_slot_id: int
    time_window_start: str
    room: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        date = self.date.isoformat()

        activity_code = self.activity_code

        master_slot_id = self.master_slot_id

        time_window_start = self.time_window_start

        room: None | str
        room = self.room

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "date": date,
                "activity_code": activity_code,
                "master_slot_id": master_slot_id,
                "time_window_start": time_window_start,
                "room": room,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        date = datetime.date.fromisoformat(d.pop("date"))

        activity_code = d.pop("activity_code")

        master_slot_id = d.pop("master_slot_id")

        time_window_start = d.pop("time_window_start")

        def _parse_room(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        room = _parse_room(d.pop("room"))

        kept_day = cls(
            id=id,
            date=date,
            activity_code=activity_code,
            master_slot_id=master_slot_id,
            time_window_start=time_window_start,
            room=room,
        )

        kept_day.additional_properties = d
        return kept_day

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
