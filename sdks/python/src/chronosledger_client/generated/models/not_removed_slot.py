from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="NotRemovedSlot")


@_attrs_define
class NotRemovedSlot:
    """A slot the upload did not remove, as it was listed in `not_in_file`. It stays on the timetable with all its days.

    Attributes:
        id (int): What DELETE /schedule/slots/{slot_id} takes, if it should go.
        activity_code (str):
        rrule (str):  Example: FREQ=WEEKLY;BYDAY=MO.
        dtstart (datetime.date):
        time_window_start (str):
        reason (str): Why it was left, naming the dates of the days ahead that carry attendance or a note. Act on it
            with `POST /schedule/slots/{id}/retire`, which keeps those days.
        room (None | str | Unset):
    """

    id: int
    activity_code: str
    rrule: str
    dtstart: datetime.date
    time_window_start: str
    reason: str
    room: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        activity_code = self.activity_code

        rrule = self.rrule

        dtstart = self.dtstart.isoformat()

        time_window_start = self.time_window_start

        reason = self.reason

        room: None | str | Unset
        if isinstance(self.room, Unset):
            room = UNSET
        else:
            room = self.room

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "activity_code": activity_code,
                "rrule": rrule,
                "dtstart": dtstart,
                "time_window_start": time_window_start,
                "reason": reason,
            }
        )
        if room is not UNSET:
            field_dict["room"] = room

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        activity_code = d.pop("activity_code")

        rrule = d.pop("rrule")

        dtstart = datetime.date.fromisoformat(d.pop("dtstart"))

        time_window_start = d.pop("time_window_start")

        reason = d.pop("reason")

        def _parse_room(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        room = _parse_room(d.pop("room", UNSET))

        not_removed_slot = cls(
            id=id,
            activity_code=activity_code,
            rrule=rrule,
            dtstart=dtstart,
            time_window_start=time_window_start,
            reason=reason,
            room=room,
        )

        not_removed_slot.additional_properties = d
        return not_removed_slot

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
