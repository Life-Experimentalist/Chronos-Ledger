from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.requirement_response_enforcement import RequirementResponseEnforcement
from ..models.requirement_response_owner_kind import RequirementResponseOwnerKind
from ..models.requirement_response_target_kind import RequirementResponseTargetKind

T = TypeVar("T", bound="RequirementResponse")


@_attrs_define
class RequirementResponse:
    """
    Attributes:
        id (int):
        owner_kind (RequirementResponseOwnerKind):
        owner_id (int):
        target_resource_id (int | None):
        target_kind (RequirementResponseTargetKind):
        quantity (int):
        before_minutes (int):
        after_minutes (int):
        enforcement (RequirementResponseEnforcement): Null means the organization's default applies.
        created_at (datetime.datetime):
    """

    id: int
    owner_kind: RequirementResponseOwnerKind
    owner_id: int
    target_resource_id: int | None
    target_kind: RequirementResponseTargetKind
    quantity: int
    before_minutes: int
    after_minutes: int
    enforcement: RequirementResponseEnforcement
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        owner_kind = self.owner_kind.value

        owner_id = self.owner_id

        target_resource_id: int | None
        target_resource_id = self.target_resource_id

        target_kind = self.target_kind.value

        quantity = self.quantity

        before_minutes = self.before_minutes

        after_minutes = self.after_minutes

        enforcement = self.enforcement.value

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "owner_kind": owner_kind,
                "owner_id": owner_id,
                "target_resource_id": target_resource_id,
                "target_kind": target_kind,
                "quantity": quantity,
                "before_minutes": before_minutes,
                "after_minutes": after_minutes,
                "enforcement": enforcement,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        owner_kind = RequirementResponseOwnerKind(d.pop("owner_kind"))

        owner_id = d.pop("owner_id")

        def _parse_target_resource_id(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        target_resource_id = _parse_target_resource_id(d.pop("target_resource_id"))

        target_kind = RequirementResponseTargetKind(d.pop("target_kind"))

        quantity = d.pop("quantity")

        before_minutes = d.pop("before_minutes")

        after_minutes = d.pop("after_minutes")

        enforcement = RequirementResponseEnforcement(d.pop("enforcement"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        requirement_response = cls(
            id=id,
            owner_kind=owner_kind,
            owner_id=owner_id,
            target_resource_id=target_resource_id,
            target_kind=target_kind,
            quantity=quantity,
            before_minutes=before_minutes,
            after_minutes=after_minutes,
            enforcement=enforcement,
            created_at=created_at,
        )

        requirement_response.additional_properties = d
        return requirement_response

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
