from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MasterSlotResponse")


@_attrs_define
class MasterSlotResponse:
    """
    Attributes:
        id (int | Unset):
        day_of_week_index (int | Unset):
        time_window_start (str | Unset):
        time_window_end (str | Unset):
        activity_id (int | Unset):
        primary_lead_id (None | str | Unset):
        resource_id (int | None | Unset): Prefer this over target_room_identifier.
        target_room_identifier (None | str | Unset): The room's name, mirrored from the resource. Being retired.
    """

    id: int | Unset = UNSET
    day_of_week_index: int | Unset = UNSET
    time_window_start: str | Unset = UNSET
    time_window_end: str | Unset = UNSET
    activity_id: int | Unset = UNSET
    primary_lead_id: None | str | Unset = UNSET
    resource_id: int | None | Unset = UNSET
    target_room_identifier: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        day_of_week_index = self.day_of_week_index

        time_window_start = self.time_window_start

        time_window_end = self.time_window_end

        activity_id = self.activity_id

        primary_lead_id: None | str | Unset
        if isinstance(self.primary_lead_id, Unset):
            primary_lead_id = UNSET
        else:
            primary_lead_id = self.primary_lead_id

        resource_id: int | None | Unset
        if isinstance(self.resource_id, Unset):
            resource_id = UNSET
        else:
            resource_id = self.resource_id

        target_room_identifier: None | str | Unset
        if isinstance(self.target_room_identifier, Unset):
            target_room_identifier = UNSET
        else:
            target_room_identifier = self.target_room_identifier

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if day_of_week_index is not UNSET:
            field_dict["day_of_week_index"] = day_of_week_index
        if time_window_start is not UNSET:
            field_dict["time_window_start"] = time_window_start
        if time_window_end is not UNSET:
            field_dict["time_window_end"] = time_window_end
        if activity_id is not UNSET:
            field_dict["activity_id"] = activity_id
        if primary_lead_id is not UNSET:
            field_dict["primary_lead_id"] = primary_lead_id
        if resource_id is not UNSET:
            field_dict["resource_id"] = resource_id
        if target_room_identifier is not UNSET:
            field_dict["target_room_identifier"] = target_room_identifier

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        day_of_week_index = d.pop("day_of_week_index", UNSET)

        time_window_start = d.pop("time_window_start", UNSET)

        time_window_end = d.pop("time_window_end", UNSET)

        activity_id = d.pop("activity_id", UNSET)

        def _parse_primary_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        primary_lead_id = _parse_primary_lead_id(d.pop("primary_lead_id", UNSET))

        def _parse_resource_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        resource_id = _parse_resource_id(d.pop("resource_id", UNSET))

        def _parse_target_room_identifier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        target_room_identifier = _parse_target_room_identifier(d.pop("target_room_identifier", UNSET))

        master_slot_response = cls(
            id=id,
            day_of_week_index=day_of_week_index,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            activity_id=activity_id,
            primary_lead_id=primary_lead_id,
            resource_id=resource_id,
            target_room_identifier=target_room_identifier,
        )

        master_slot_response.additional_properties = d
        return master_slot_response

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
