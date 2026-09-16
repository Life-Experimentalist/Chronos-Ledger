from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="UserUpdate")


@_attrs_define
class UserUpdate:
    """A field left out keeps its value and a null clears it, except full_name and email_address, which cannot be null
    (422).

        Attributes:
            full_name (str | Unset):
            email_address (str | Unset):
            unit_code (None | str | Unset):
            assigned_base_station (None | str | Unset):
            reporting_line_manager (None | str | Unset):
    """

    full_name: str | Unset = UNSET
    email_address: str | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    assigned_base_station: None | str | Unset = UNSET
    reporting_line_manager: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        full_name = self.full_name

        email_address = self.email_address

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        assigned_base_station: None | str | Unset
        if isinstance(self.assigned_base_station, Unset):
            assigned_base_station = UNSET
        else:
            assigned_base_station = self.assigned_base_station

        reporting_line_manager: None | str | Unset
        if isinstance(self.reporting_line_manager, Unset):
            reporting_line_manager = UNSET
        else:
            reporting_line_manager = self.reporting_line_manager

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if email_address is not UNSET:
            field_dict["email_address"] = email_address
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if assigned_base_station is not UNSET:
            field_dict["assigned_base_station"] = assigned_base_station
        if reporting_line_manager is not UNSET:
            field_dict["reporting_line_manager"] = reporting_line_manager

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        full_name = d.pop("full_name", UNSET)

        email_address = d.pop("email_address", UNSET)

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        def _parse_assigned_base_station(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        assigned_base_station = _parse_assigned_base_station(
            d.pop("assigned_base_station", UNSET)
        )

        def _parse_reporting_line_manager(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reporting_line_manager = _parse_reporting_line_manager(
            d.pop("reporting_line_manager", UNSET)
        )

        user_update = cls(
            full_name=full_name,
            email_address=email_address,
            unit_code=unit_code,
            assigned_base_station=assigned_base_station,
            reporting_line_manager=reporting_line_manager,
        )

        user_update.additional_properties = d
        return user_update

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
