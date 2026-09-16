from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="StaffAvailabilityResponse")


@_attrs_define
class StaffAvailabilityResponse:
    """
    Attributes:
        staff_id (str | Unset):
        full_name (str | Unset):
        unit_code (None | str | Unset):
        availability_label (str | Unset): Human-readable availability derived from current_occupancy_index.
    """

    staff_id: str | Unset = UNSET
    full_name: str | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    availability_label: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        staff_id = self.staff_id

        full_name = self.full_name

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        availability_label = self.availability_label

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if staff_id is not UNSET:
            field_dict["staff_id"] = staff_id
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if availability_label is not UNSET:
            field_dict["availability_label"] = availability_label

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        staff_id = d.pop("staff_id", UNSET)

        full_name = d.pop("full_name", UNSET)

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        availability_label = d.pop("availability_label", UNSET)

        staff_availability_response = cls(
            staff_id=staff_id,
            full_name=full_name,
            unit_code=unit_code,
            availability_label=availability_label,
        )

        staff_availability_response.additional_properties = d
        return staff_availability_response

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
