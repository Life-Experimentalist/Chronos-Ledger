from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="MasterSlotUpdate")


@_attrs_define
class MasterSlotUpdate:
    """Every field is optional and only the fields present are changed. Only primary_lead_id may be null, which takes the
    lead off the slot; a null for any other field is a 422. activity_id is absent on purpose: every day the slot has
    produced carries its own copy of the activity, so pointing the slot at another one is a delete and a create, not an
    edit.

        Attributes:
            day_of_week_index (int | Unset):
            time_window_start (str | Unset):
            time_window_end (str | Unset):
            primary_lead_id (None | str | Unset):
            target_room_identifier (str | Unset):
    """

    day_of_week_index: int | Unset = UNSET
    time_window_start: str | Unset = UNSET
    time_window_end: str | Unset = UNSET
    primary_lead_id: None | str | Unset = UNSET
    target_room_identifier: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        day_of_week_index = self.day_of_week_index

        time_window_start = self.time_window_start

        time_window_end = self.time_window_end

        primary_lead_id: None | str | Unset
        if isinstance(self.primary_lead_id, Unset):
            primary_lead_id = UNSET
        else:
            primary_lead_id = self.primary_lead_id

        target_room_identifier = self.target_room_identifier

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if day_of_week_index is not UNSET:
            field_dict["day_of_week_index"] = day_of_week_index
        if time_window_start is not UNSET:
            field_dict["time_window_start"] = time_window_start
        if time_window_end is not UNSET:
            field_dict["time_window_end"] = time_window_end
        if primary_lead_id is not UNSET:
            field_dict["primary_lead_id"] = primary_lead_id
        if target_room_identifier is not UNSET:
            field_dict["target_room_identifier"] = target_room_identifier

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        day_of_week_index = d.pop("day_of_week_index", UNSET)

        time_window_start = d.pop("time_window_start", UNSET)

        time_window_end = d.pop("time_window_end", UNSET)

        def _parse_primary_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        primary_lead_id = _parse_primary_lead_id(d.pop("primary_lead_id", UNSET))

        target_room_identifier = d.pop("target_room_identifier", UNSET)

        master_slot_update = cls(
            day_of_week_index=day_of_week_index,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            primary_lead_id=primary_lead_id,
            target_room_identifier=target_room_identifier,
        )

        master_slot_update.additional_properties = d
        return master_slot_update

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
