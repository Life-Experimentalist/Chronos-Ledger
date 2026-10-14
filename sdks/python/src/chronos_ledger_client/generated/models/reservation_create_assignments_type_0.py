from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ReservationCreateAssignmentsType0")


@_attrs_define
class ReservationCreateAssignmentsType0:
    """Which resources to hold for the requirements that name a kind of resource: `ROOM` or `PERSON` mapped to resource
    ids, used in order. Where it says nothing, or runs out, the engine picks the first free resources of the kind by
    code. An id that is not an active resource of that kind in this organization, or that no requirement asks for, is a
    422. A named resource that is not free is a gap and is not swapped for another. Part of what a retry is compared on
    only when it is sent.

        Example:
            {'PERSON': [12, 15]}

    """

    additional_properties: dict[str, list[int]] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        reservation_create_assignments_type_0 = cls()

        additional_properties = {}
        for prop_name, prop_dict in d.items():
            additional_property = cast(list[int], prop_dict)

            additional_properties[prop_name] = additional_property

        reservation_create_assignments_type_0.additional_properties = additional_properties
        return reservation_create_assignments_type_0

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> list[int]:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: list[int]) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
