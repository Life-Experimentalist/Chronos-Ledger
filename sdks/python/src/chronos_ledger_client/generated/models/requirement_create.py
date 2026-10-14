from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.requirement_create_enforcement import RequirementCreateEnforcement
from ..models.requirement_create_target_kind import RequirementCreateTargetKind
from ..types import UNSET, Unset

T = TypeVar("T", bound="RequirementCreate")


@_attrs_define
class RequirementCreate:
    """One rule: whoever uses the owner also needs the target. Set exactly one of `target_resource_id` and `target_kind`.

    Attributes:
        target_resource_id (int | None | Unset): A specific resource of this organization. Never an activity.
        target_kind (RequirementCreateTargetKind | Unset): Any resource of this kind, picked at booking time.
        quantity (int | Unset): How many. Units of the pool on a POOLED named target, which a named target of another
            mode cannot take above 1 (422); the number of distinct resources on a kind. 1 when left out.
        before_minutes (int | Unset): Setup time held before the window. 0 when left out.
        after_minutes (int | Unset): Turnover time held after the window. 0 when left out.
        enforcement (RequirementCreateEnforcement | Unset): REQUIRED refuses a booking that cannot meet it. ADVISORY
            books without it and lists the gap. Null, or left out, follows the organization's
            `default_requirement_enforcement`.
    """

    target_resource_id: int | None | Unset = UNSET
    target_kind: RequirementCreateTargetKind | Unset = UNSET
    quantity: int | Unset = UNSET
    before_minutes: int | Unset = UNSET
    after_minutes: int | Unset = UNSET
    enforcement: RequirementCreateEnforcement | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        target_resource_id: int | None | Unset
        if isinstance(self.target_resource_id, Unset):
            target_resource_id = UNSET
        else:
            target_resource_id = self.target_resource_id

        target_kind: str | Unset = UNSET
        if not isinstance(self.target_kind, Unset):
            target_kind = self.target_kind.value

        quantity = self.quantity

        before_minutes = self.before_minutes

        after_minutes = self.after_minutes

        enforcement: str | Unset = UNSET
        if not isinstance(self.enforcement, Unset):
            enforcement = self.enforcement.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if target_resource_id is not UNSET:
            field_dict["target_resource_id"] = target_resource_id
        if target_kind is not UNSET:
            field_dict["target_kind"] = target_kind
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if before_minutes is not UNSET:
            field_dict["before_minutes"] = before_minutes
        if after_minutes is not UNSET:
            field_dict["after_minutes"] = after_minutes
        if enforcement is not UNSET:
            field_dict["enforcement"] = enforcement

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_target_resource_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        target_resource_id = _parse_target_resource_id(d.pop("target_resource_id", UNSET))

        _target_kind = d.pop("target_kind", UNSET)
        target_kind: RequirementCreateTargetKind | Unset
        if isinstance(_target_kind, Unset):
            target_kind = UNSET
        else:
            target_kind = RequirementCreateTargetKind(_target_kind)

        quantity = d.pop("quantity", UNSET)

        before_minutes = d.pop("before_minutes", UNSET)

        after_minutes = d.pop("after_minutes", UNSET)

        _enforcement = d.pop("enforcement", UNSET)
        enforcement: RequirementCreateEnforcement | Unset
        if isinstance(_enforcement, Unset):
            enforcement = UNSET
        else:
            enforcement = RequirementCreateEnforcement(_enforcement)

        requirement_create = cls(
            target_resource_id=target_resource_id,
            target_kind=target_kind,
            quantity=quantity,
            before_minutes=before_minutes,
            after_minutes=after_minutes,
            enforcement=enforcement,
        )

        requirement_create.additional_properties = d
        return requirement_create

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
