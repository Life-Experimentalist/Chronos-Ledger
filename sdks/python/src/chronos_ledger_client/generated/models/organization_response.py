from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.organization_response_default_requirement_enforcement import (
    OrganizationResponseDefaultRequirementEnforcement,
)

T = TypeVar("T", bound="OrganizationResponse")


@_attrs_define
class OrganizationResponse:
    """
    Attributes:
        id (str):
        name (str):
        default_requirement_enforcement (OrganizationResponseDefaultRequirementEnforcement):
    """

    id: str
    name: str
    default_requirement_enforcement: OrganizationResponseDefaultRequirementEnforcement
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        default_requirement_enforcement = self.default_requirement_enforcement.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "default_requirement_enforcement": default_requirement_enforcement,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        default_requirement_enforcement = OrganizationResponseDefaultRequirementEnforcement(
            d.pop("default_requirement_enforcement")
        )

        organization_response = cls(
            id=id,
            name=name,
            default_requirement_enforcement=default_requirement_enforcement,
        )

        organization_response.additional_properties = d
        return organization_response

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
