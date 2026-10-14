from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.organization_update_default_requirement_enforcement import (
    OrganizationUpdateDefaultRequirementEnforcement,
)

T = TypeVar("T", bound="OrganizationUpdate")


@_attrs_define
class OrganizationUpdate:
    """
    Attributes:
        default_requirement_enforcement (OrganizationUpdateDefaultRequirementEnforcement): What a requirement with no
            enforcement of its own does. Read when a booking is made, so a change applies to the next booking.
    """

    default_requirement_enforcement: OrganizationUpdateDefaultRequirementEnforcement

    def to_dict(self) -> dict[str, Any]:
        default_requirement_enforcement = self.default_requirement_enforcement.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "default_requirement_enforcement": default_requirement_enforcement,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        default_requirement_enforcement = OrganizationUpdateDefaultRequirementEnforcement(
            d.pop("default_requirement_enforcement")
        )

        organization_update = cls(
            default_requirement_enforcement=default_requirement_enforcement,
        )

        return organization_update
