from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.unmet_requirement_enforcement import UnmetRequirementEnforcement
from ..models.unmet_requirement_owner_kind import UnmetRequirementOwnerKind

if TYPE_CHECKING:
    from ..models.busy_interval import BusyInterval


T = TypeVar("T", bound="UnmetRequirement")


@_attrs_define
class UnmetRequirement:
    """A requirement that could not be held, and why. On a booking it is an ADVISORY gap. On GET availability with
    `with_requirements` it is whatever would stop the window being held, whatever the enforcement.

        Attributes:
            requirement_id (int):
            owner_kind (UnmetRequirementOwnerKind):
            owner_id (int):
            target_resource_id (int | None):
            target_kind (None | str): A resource class code.
            quantity (int): How many units or resources were missing, not how many were asked for.
            enforcement (UnmetRequirementEnforcement): The enforcement that applied, with the organization's default filled
                in where the requirement did not say.
            message (str):
            conflicts (list[BusyInterval]): What stands in the way on a named target. Empty when a kind had no free resource
                to name.
    """

    requirement_id: int
    owner_kind: UnmetRequirementOwnerKind
    owner_id: int
    target_resource_id: int | None
    target_kind: None | str
    quantity: int
    enforcement: UnmetRequirementEnforcement
    message: str
    conflicts: list[BusyInterval]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        requirement_id = self.requirement_id

        owner_kind = self.owner_kind.value

        owner_id = self.owner_id

        target_resource_id: int | None
        target_resource_id = self.target_resource_id

        target_kind: None | str
        target_kind = self.target_kind

        quantity = self.quantity

        enforcement = self.enforcement.value

        message = self.message

        conflicts = []
        for conflicts_item_data in self.conflicts:
            conflicts_item = conflicts_item_data.to_dict()
            conflicts.append(conflicts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "requirement_id": requirement_id,
                "owner_kind": owner_kind,
                "owner_id": owner_id,
                "target_resource_id": target_resource_id,
                "target_kind": target_kind,
                "quantity": quantity,
                "enforcement": enforcement,
                "message": message,
                "conflicts": conflicts,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.busy_interval import BusyInterval  # noqa: PLC0415

        d = dict(src_dict)
        requirement_id = d.pop("requirement_id")

        owner_kind = UnmetRequirementOwnerKind(d.pop("owner_kind"))

        owner_id = d.pop("owner_id")

        def _parse_target_resource_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        target_resource_id = _parse_target_resource_id(d.pop("target_resource_id"))

        def _parse_target_kind(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        target_kind = _parse_target_kind(d.pop("target_kind"))

        quantity = d.pop("quantity")

        enforcement = UnmetRequirementEnforcement(d.pop("enforcement"))

        message = d.pop("message")

        conflicts = []
        _conflicts = d.pop("conflicts")
        for conflicts_item_data in _conflicts:
            conflicts_item = BusyInterval.from_dict(conflicts_item_data)

            conflicts.append(conflicts_item)

        unmet_requirement = cls(
            requirement_id=requirement_id,
            owner_kind=owner_kind,
            owner_id=owner_id,
            target_resource_id=target_resource_id,
            target_kind=target_kind,
            quantity=quantity,
            enforcement=enforcement,
            message=message,
            conflicts=conflicts,
        )

        unmet_requirement.additional_properties = d
        return unmet_requirement

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
