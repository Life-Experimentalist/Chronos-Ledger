from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="MasterSlotCreate")


@_attrs_define
class MasterSlotCreate:
    """
    Attributes:
        day_of_week_index (int): ISO weekday, 1 = Monday through 7 = Sunday.
        time_window_start (str):  Example: 09:00:00.
        time_window_end (str): Earlier than the start means the window runs past midnight and finishes on the day after
            the one the slot lands on: 22:00 to 06:00 is an eight hour night shift. Equal to the start is refused, because
            09:00 to 09:00 is either nothing at all or a full day and there is no way to tell which was meant.
             Example: 10:00:00.
        activity_id (int):
        target_room_identifier (str): The room's name. Resolved to a resource, creating one on first sight, so a room
            does not have to be registered before a timetable can name it. Surrounding spaces are stripped.
             Example: LH-201.
        primary_lead_id (None | str | Unset):
    """

    day_of_week_index: int
    time_window_start: str
    time_window_end: str
    activity_id: int
    target_room_identifier: str
    primary_lead_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        day_of_week_index = self.day_of_week_index

        time_window_start = self.time_window_start

        time_window_end = self.time_window_end

        activity_id = self.activity_id

        target_room_identifier = self.target_room_identifier

        primary_lead_id: None | str | Unset
        if isinstance(self.primary_lead_id, Unset):
            primary_lead_id = UNSET
        else:
            primary_lead_id = self.primary_lead_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "day_of_week_index": day_of_week_index,
                "time_window_start": time_window_start,
                "time_window_end": time_window_end,
                "activity_id": activity_id,
                "target_room_identifier": target_room_identifier,
            }
        )
        if primary_lead_id is not UNSET:
            field_dict["primary_lead_id"] = primary_lead_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        day_of_week_index = d.pop("day_of_week_index")

        time_window_start = d.pop("time_window_start")

        time_window_end = d.pop("time_window_end")

        activity_id = d.pop("activity_id")

        target_room_identifier = d.pop("target_room_identifier")

        def _parse_primary_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        primary_lead_id = _parse_primary_lead_id(d.pop("primary_lead_id", UNSET))

        master_slot_create = cls(
            day_of_week_index=day_of_week_index,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            activity_id=activity_id,
            target_room_identifier=target_room_identifier,
            primary_lead_id=primary_lead_id,
        )

        master_slot_create.additional_properties = d
        return master_slot_create

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
