from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="ConfigGetResponse200Labels")


@_attrs_define
class ConfigGetResponse200Labels:
    """
    Attributes:
        staff (str | Unset):
        member (str | Unset):
        activity (str | Unset):
        unit (str | Unset):
        lead (str | Unset):
        cycle (str | Unset):
    """

    staff: str | Unset = UNSET
    member: str | Unset = UNSET
    activity: str | Unset = UNSET
    unit: str | Unset = UNSET
    lead: str | Unset = UNSET
    cycle: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        staff = self.staff

        member = self.member

        activity = self.activity

        unit = self.unit

        lead = self.lead

        cycle = self.cycle

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if staff is not UNSET:
            field_dict["staff"] = staff
        if member is not UNSET:
            field_dict["member"] = member
        if activity is not UNSET:
            field_dict["activity"] = activity
        if unit is not UNSET:
            field_dict["unit"] = unit
        if lead is not UNSET:
            field_dict["lead"] = lead
        if cycle is not UNSET:
            field_dict["cycle"] = cycle

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        staff = d.pop("staff", UNSET)

        member = d.pop("member", UNSET)

        activity = d.pop("activity", UNSET)

        unit = d.pop("unit", UNSET)

        lead = d.pop("lead", UNSET)

        cycle = d.pop("cycle", UNSET)

        config_get_response_200_labels = cls(
            staff=staff,
            member=member,
            activity=activity,
            unit=unit,
            lead=lead,
            cycle=cycle,
        )

        config_get_response_200_labels.additional_properties = d
        return config_get_response_200_labels

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
