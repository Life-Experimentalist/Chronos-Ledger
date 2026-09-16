from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.access_readiness import AccessReadiness
from ..types import UNSET, Unset

T = TypeVar("T", bound="StaffLocationResponse")


@_attrs_define
class StaffLocationResponse:
    """
    Attributes:
        resolved_location (str | Unset): A room, OFF_SITE for somebody on approved leave that day, the base station (or
            Unassigned) when nothing is scheduled, or UNKNOWN when a status override answered.
             Example: LH-204.
        status (str | Unset): A sentence for display, not an enum. Example: Leading CS101 in Room LH-204.
        staff_id (str | Unset):
        full_name (str | Unset):
        occupancy_index (AccessReadiness | Unset): Staff availability / occupancy index visible to members.
    """

    resolved_location: str | Unset = UNSET
    status: str | Unset = UNSET
    staff_id: str | Unset = UNSET
    full_name: str | Unset = UNSET
    occupancy_index: AccessReadiness | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        resolved_location = self.resolved_location

        status = self.status

        staff_id = self.staff_id

        full_name = self.full_name

        occupancy_index: str | Unset = UNSET
        if not isinstance(self.occupancy_index, Unset):
            occupancy_index = self.occupancy_index.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if resolved_location is not UNSET:
            field_dict["resolved_location"] = resolved_location
        if status is not UNSET:
            field_dict["status"] = status
        if staff_id is not UNSET:
            field_dict["staff_id"] = staff_id
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if occupancy_index is not UNSET:
            field_dict["occupancy_index"] = occupancy_index

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        resolved_location = d.pop("resolved_location", UNSET)

        status = d.pop("status", UNSET)

        staff_id = d.pop("staff_id", UNSET)

        full_name = d.pop("full_name", UNSET)

        _occupancy_index = d.pop("occupancy_index", UNSET)
        occupancy_index: AccessReadiness | Unset
        if isinstance(_occupancy_index, Unset):
            occupancy_index = UNSET
        else:
            occupancy_index = AccessReadiness(_occupancy_index)

        staff_location_response = cls(
            resolved_location=resolved_location,
            status=status,
            staff_id=staff_id,
            full_name=full_name,
            occupancy_index=occupancy_index,
        )

        staff_location_response.additional_properties = d
        return staff_location_response

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
