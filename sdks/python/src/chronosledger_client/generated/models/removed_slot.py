from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="RemovedSlot")


@_attrs_define
class RemovedSlot:
    """A slot the upload removed, as it was listed in `not_in_file`.

    Attributes:
        id (int): What DELETE /schedule/slots/{slot_id} takes, if it should go.
        activity_code (str):
        rrule (str):  Example: FREQ=WEEKLY;BYDAY=MO.
        dtstart (datetime.date):
        time_window_start (str):
        ledger_rows_removed (int): Days from today on that the slot had produced, now withdrawn.
        ledger_rows_detached (int): Days already past, kept with everything recorded on them and no longer pointing at a
            slot.
        room (None | str | Unset):
    """

    id: int
    activity_code: str
    rrule: str
    dtstart: datetime.date
    time_window_start: str
    ledger_rows_removed: int
    ledger_rows_detached: int
    room: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        activity_code = self.activity_code

        rrule = self.rrule

        dtstart = self.dtstart.isoformat()

        time_window_start = self.time_window_start

        ledger_rows_removed = self.ledger_rows_removed

        ledger_rows_detached = self.ledger_rows_detached

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
                "ledger_rows_removed": ledger_rows_removed,
                "ledger_rows_detached": ledger_rows_detached,
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

        ledger_rows_removed = d.pop("ledger_rows_removed")

        ledger_rows_detached = d.pop("ledger_rows_detached")

        def _parse_room(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        room = _parse_room(d.pop("room", UNSET))

        removed_slot = cls(
            id=id,
            activity_code=activity_code,
            rrule=rrule,
            dtstart=dtstart,
            time_window_start=time_window_start,
            ledger_rows_removed=ledger_rows_removed,
            ledger_rows_detached=ledger_rows_detached,
            room=room,
        )

        removed_slot.additional_properties = d
        return removed_slot

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
