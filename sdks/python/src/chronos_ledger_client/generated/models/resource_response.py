from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.resource_response_mode import ResourceResponseMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="ResourceResponse")


@_attrs_define
class ResourceResponse:
    """
    Attributes:
        id (int | Unset):
        code (str | Unset): The importer's match key. Not editable. Example: LH-3.
        label (str | Unset):  Example: Lecture Hall 3.
        resource_type (str | Unset): The code of one of the organization's resource classes. `ROOM` and `PERSON` exist
            everywhere; see `GET /api/v1/resource-classes/` for the rest.
             Example: ROOM.
        unit_code (None | str | Unset):
        capacity (int | None | Unset): How many people a room holds, or on a POOLED resource how many units the pool
            has.
        mode (ResourceResponseMode | Unset): How a reservation takes the resource. EXCLUSIVE, the default, is one
            booking at a time. POOLED is capacity interchangeable units, of which a booking takes its quantity, refused with
            `RESOURCE_CAPACITY_EXCEEDED` when the bookings already there leave too few at some moment of the window. SHARED
            records who is there and refuses nobody. The mode governs reservations only: the timetable on any resource is
            one class at a time, and a class on a pooled resource takes the whole pool.
        user_id (None | str | Unset): Set when this resource is a person.
        latitude (float | None | Unset):
        longitude (float | None | Unset):
        altitude_target (float | None | Unset):
        active (bool | Unset):
    """

    id: int | Unset = UNSET
    code: str | Unset = UNSET
    label: str | Unset = UNSET
    resource_type: str | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    capacity: int | None | Unset = UNSET
    mode: ResourceResponseMode | Unset = UNSET
    user_id: None | str | Unset = UNSET
    latitude: float | None | Unset = UNSET
    longitude: float | None | Unset = UNSET
    altitude_target: float | None | Unset = UNSET
    active: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        code = self.code

        label = self.label

        resource_type = self.resource_type

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        capacity: int | None | Unset
        if isinstance(self.capacity, Unset):
            capacity = UNSET
        else:
            capacity = self.capacity

        mode: str | Unset = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        user_id: None | str | Unset
        if isinstance(self.user_id, Unset):
            user_id = UNSET
        else:
            user_id = self.user_id

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
        if id is not UNSET:
            field_dict["id"] = id
        if code is not UNSET:
            field_dict["code"] = code
        if label is not UNSET:
            field_dict["label"] = label
        if resource_type is not UNSET:
            field_dict["resource_type"] = resource_type
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if capacity is not UNSET:
            field_dict["capacity"] = capacity
        if mode is not UNSET:
            field_dict["mode"] = mode
        if user_id is not UNSET:
            field_dict["user_id"] = user_id
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
        id = d.pop("id", UNSET)

        code = d.pop("code", UNSET)

        label = d.pop("label", UNSET)

        resource_type = d.pop("resource_type", UNSET)

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        def _parse_capacity(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        capacity = _parse_capacity(d.pop("capacity", UNSET))

        _mode = d.pop("mode", UNSET)
        mode: ResourceResponseMode | Unset
        if isinstance(_mode, Unset):
            mode = UNSET
        else:
            mode = ResourceResponseMode(_mode)

        def _parse_user_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        user_id = _parse_user_id(d.pop("user_id", UNSET))

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

        resource_response = cls(
            id=id,
            code=code,
            label=label,
            resource_type=resource_type,
            unit_code=unit_code,
            capacity=capacity,
            mode=mode,
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            altitude_target=altitude_target,
            active=active,
        )

        resource_response.additional_properties = d
        return resource_response

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
