from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ResourceUpdate")


@_attrs_define
class ResourceUpdate:
    """Every field is optional and a field left out is left alone. code, resource_type and user_id are absent on purpose:
    code is the importer's match key, and a room that becomes a person is a different resource, not an edit.

        Attributes:
            label (str | Unset):
            capacity (int | None | Unset):
            latitude (float | None | Unset): Set or cleared together with longitude. Setting the pair is what switches
                geofencing on for sessions held here.
            longitude (float | None | Unset):
            altitude_target (float | None | Unset): Optional. Without it the fence is horizontal only.
            active (bool | Unset):
    """

    label: str | Unset = UNSET
    capacity: int | None | Unset = UNSET
    latitude: float | None | Unset = UNSET
    longitude: float | None | Unset = UNSET
    altitude_target: float | None | Unset = UNSET
    active: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        label = self.label

        capacity: int | None | Unset
        if isinstance(self.capacity, Unset):
            capacity = UNSET
        else:
            capacity = self.capacity

        latitude: float | None | Unset
        if isinstance(self.latitude, Unset):
            latitude = UNSET
        else:
            latitude = self.latitude

        longitude: float | None | Unset
        if isinstance(self.longitude, Unset):
            longitude = UNSET
        else:
            longitude = self.longitude

        altitude_target: float | None | Unset
        if isinstance(self.altitude_target, Unset):
            altitude_target = UNSET
        else:
            altitude_target = self.altitude_target

        active = self.active

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if label is not UNSET:
            field_dict["label"] = label
        if capacity is not UNSET:
            field_dict["capacity"] = capacity
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude
        if altitude_target is not UNSET:
            field_dict["altitude_target"] = altitude_target
        if active is not UNSET:
            field_dict["active"] = active

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        label = d.pop("label", UNSET)

        def _parse_capacity(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        capacity = _parse_capacity(d.pop("capacity", UNSET))

        def _parse_latitude(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        latitude = _parse_latitude(d.pop("latitude", UNSET))

        def _parse_longitude(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        longitude = _parse_longitude(d.pop("longitude", UNSET))

        def _parse_altitude_target(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        altitude_target = _parse_altitude_target(d.pop("altitude_target", UNSET))

        active = d.pop("active", UNSET)

        resource_update = cls(
            label=label,
            capacity=capacity,
            latitude=latitude,
            longitude=longitude,
            altitude_target=altitude_target,
            active=active,
        )

        resource_update.additional_properties = d
        return resource_update

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
