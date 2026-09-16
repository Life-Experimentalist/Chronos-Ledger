from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.access_readiness import AccessReadiness
from ..models.institutional_role import InstitutionalRole
from ..types import UNSET, Unset

T = TypeVar("T", bound="UserResponse")


@_attrs_define
class UserResponse:
    """
    Attributes:
        id (str | Unset):
        full_name (str | Unset):
        email_address (str | Unset):
        role_type (InstitutionalRole | Unset): Role assigned to a system user.
        unit_code (None | str | Unset):
        assigned_base_station (None | str | Unset):
        current_occupancy_index (AccessReadiness | Unset): Staff availability / occupancy index visible to members.
        reporting_line_manager (None | str | Unset):
        deactivated_at (datetime.datetime | None | Unset): When the account was deactivated, or null while it is active.
    """

    id: str | Unset = UNSET
    full_name: str | Unset = UNSET
    email_address: str | Unset = UNSET
    role_type: InstitutionalRole | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    assigned_base_station: None | str | Unset = UNSET
    current_occupancy_index: AccessReadiness | Unset = UNSET
    reporting_line_manager: None | str | Unset = UNSET
    deactivated_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        full_name = self.full_name

        email_address = self.email_address

        role_type: str | Unset = UNSET
        if not isinstance(self.role_type, Unset):
            role_type = self.role_type.value

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

        current_occupancy_index: str | Unset = UNSET
        if not isinstance(self.current_occupancy_index, Unset):
            current_occupancy_index = self.current_occupancy_index.value

        reporting_line_manager: None | str | Unset
        if isinstance(self.reporting_line_manager, Unset):
            reporting_line_manager = UNSET
        else:
            reporting_line_manager = self.reporting_line_manager

        deactivated_at: None | str | Unset
        if isinstance(self.deactivated_at, Unset):
            deactivated_at = UNSET
        elif isinstance(self.deactivated_at, datetime.datetime):
            deactivated_at = self.deactivated_at.isoformat()
        else:
            deactivated_at = self.deactivated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if email_address is not UNSET:
            field_dict["email_address"] = email_address
        if role_type is not UNSET:
            field_dict["role_type"] = role_type
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if assigned_base_station is not UNSET:
            field_dict["assigned_base_station"] = assigned_base_station
        if current_occupancy_index is not UNSET:
            field_dict["current_occupancy_index"] = current_occupancy_index
        if reporting_line_manager is not UNSET:
            field_dict["reporting_line_manager"] = reporting_line_manager
        if deactivated_at is not UNSET:
            field_dict["deactivated_at"] = deactivated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        full_name = d.pop("full_name", UNSET)

        email_address = d.pop("email_address", UNSET)

        _role_type = d.pop("role_type", UNSET)
        role_type: InstitutionalRole | Unset
        if isinstance(_role_type, Unset):
            role_type = UNSET
        else:
            role_type = InstitutionalRole(_role_type)

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

        _current_occupancy_index = d.pop("current_occupancy_index", UNSET)
        current_occupancy_index: AccessReadiness | Unset
        if isinstance(_current_occupancy_index, Unset):
            current_occupancy_index = UNSET
        else:
            current_occupancy_index = AccessReadiness(_current_occupancy_index)

        def _parse_reporting_line_manager(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reporting_line_manager = _parse_reporting_line_manager(
            d.pop("reporting_line_manager", UNSET)
        )

        def _parse_deactivated_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                deactivated_at_type_0 = datetime.datetime.fromisoformat(data)

                return deactivated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        deactivated_at = _parse_deactivated_at(d.pop("deactivated_at", UNSET))

        user_response = cls(
            id=id,
            full_name=full_name,
            email_address=email_address,
            role_type=role_type,
            unit_code=unit_code,
            assigned_base_station=assigned_base_station,
            current_occupancy_index=current_occupancy_index,
            reporting_line_manager=reporting_line_manager,
            deactivated_at=deactivated_at,
        )

        user_response.additional_properties = d
        return user_response

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
