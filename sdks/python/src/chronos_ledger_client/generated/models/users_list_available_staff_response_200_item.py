from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.access_readiness import AccessReadiness
from ..types import UNSET, Unset

T = TypeVar("T", bound="UsersListAvailableStaffResponse200Item")


@_attrs_define
class UsersListAvailableStaffResponse200Item:
    """
    Attributes:
        id (str | Unset):
        full_name (str | Unset):
        unit_code (None | str | Unset):
        current_occupancy_index (AccessReadiness | Unset): Staff availability / occupancy index visible to members.
    """

    id: str | Unset = UNSET
    full_name: str | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    current_occupancy_index: AccessReadiness | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        full_name = self.full_name

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        current_occupancy_index: str | Unset = UNSET
        if not isinstance(self.current_occupancy_index, Unset):
            current_occupancy_index = self.current_occupancy_index.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if current_occupancy_index is not UNSET:
            field_dict["current_occupancy_index"] = current_occupancy_index

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        full_name = d.pop("full_name", UNSET)

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        _current_occupancy_index = d.pop("current_occupancy_index", UNSET)
        current_occupancy_index: AccessReadiness | Unset
        if isinstance(_current_occupancy_index, Unset):
            current_occupancy_index = UNSET
        else:
            current_occupancy_index = AccessReadiness(_current_occupancy_index)

        users_list_available_staff_response_200_item = cls(
            id=id,
            full_name=full_name,
            unit_code=unit_code,
            current_occupancy_index=current_occupancy_index,
        )

        users_list_available_staff_response_200_item.additional_properties = d
        return users_list_available_staff_response_200_item

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
