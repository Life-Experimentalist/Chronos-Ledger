from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role_map_entry_create_role_type import RoleMapEntryCreateRoleType
from ..types import UNSET, Unset

T = TypeVar("T", bound="RoleMapEntryCreate")


@_attrs_define
class RoleMapEntryCreate:
    """
    Attributes:
        group_claim_value (str): One value out of the note's `groups` claim, matched exactly. A group with no entry
            lands on `MEMBER`, so an issuer trusted to say who somebody is has not thereby been trusted to say what they may
            do.
             Example: library-staff.
        role_type (RoleMapEntryCreateRoleType): `ORG_ADMIN` and `UNIT_ADMIN` are refused with a 422, and refused again
            by a check constraint. It is the one rule whose failure would hand an outside system this instance.
             Example: STAFF.
        unit_code (None | str | Unset): The unit somebody in this group belongs to, if any. Example: LIB.
    """

    group_claim_value: str
    role_type: RoleMapEntryCreateRoleType
    unit_code: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        group_claim_value = self.group_claim_value

        role_type = self.role_type.value

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "group_claim_value": group_claim_value,
                "role_type": role_type,
            }
        )
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        group_claim_value = d.pop("group_claim_value")

        role_type = RoleMapEntryCreateRoleType(d.pop("role_type"))

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        role_map_entry_create = cls(
            group_claim_value=group_claim_value,
            role_type=role_type,
            unit_code=unit_code,
        )

        role_map_entry_create.additional_properties = d
        return role_map_entry_create

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
