from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="OrphanSlot")


@_attrs_define
class OrphanSlot:
    """
    Attributes:
        id (int): What DELETE /schedule/slots/{slot_id} takes, if it should go.
        activity_code (str):
        day_of_week_index (int):
        time_window_start (str):
        room (None | str | Unset):
    """

    id: int
    activity_code: str
    day_of_week_index: int
    time_window_start: str
    room: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        activity_code = self.activity_code

        day_of_week_index = self.day_of_week_index

        time_window_start = self.time_window_start

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
                "day_of_week_index": day_of_week_index,
                "time_window_start": time_window_start,
            }
        )
        if room is not UNSET:
            field_dict["room"] = room

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id")

        activity_code = d.pop("activity_code")

        day_of_week_index = d.pop("day_of_week_index")

        time_window_start = d.pop("time_window_start")

        def _parse_room(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        room = _parse_room(d.pop("room", UNSET))

        orphan_slot = cls(
            id=id,
            activity_code=activity_code,
            day_of_week_index=day_of_week_index,
            time_window_start=time_window_start,
            room=room,
        )

        orphan_slot.additional_properties = d
        return orphan_slot

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
