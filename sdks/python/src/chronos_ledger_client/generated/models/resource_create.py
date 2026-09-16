from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="ResourceCreate")


@_attrs_define
class ResourceCreate:
    """A room. Every string is trimmed first, code included, the same as the importer trims a room name, so this room and
    the same name in a later CSV are one row.

        Attributes:
            code (str): The importer's match key, unique across every resource. Not editable afterwards.
                 Example: LH-3.
            label (str | Unset): Defaults to the code, which is what an imported room gets. Example: Lecture Hall 3.
            unit_code (None | str | Unset):
            capacity (int | None | Unset):
            latitude (float | None | Unset): Set together with longitude, or not at all.
            longitude (float | None | Unset):
            altitude_target (float | None | Unset):
    """

    code: str
    label: str | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    capacity: int | None | Unset = UNSET
    latitude: float | None | Unset = UNSET
    longitude: float | None | Unset = UNSET
    altitude_target: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        label = self.label

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

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "code": code,
            }
        )
        if label is not UNSET:
            field_dict["label"] = label
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if capacity is not UNSET:
            field_dict["capacity"] = capacity
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude
        if altitude_target is not UNSET:
            field_dict["altitude_target"] = altitude_target

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        code = d.pop("code")

        label = d.pop("label", UNSET)

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

        resource_create = cls(
            code=code,
            label=label,
            unit_code=unit_code,
            capacity=capacity,
            latitude=latitude,
            longitude=longitude,
            altitude_target=altitude_target,
        )

        resource_create.additional_properties = d
        return resource_create

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
