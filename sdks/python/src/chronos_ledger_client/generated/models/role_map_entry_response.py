from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role_map_entry_response_role_type import RoleMapEntryResponseRoleType
from ..types import UNSET, Unset

T = TypeVar("T", bound="RoleMapEntryResponse")


@_attrs_define
class RoleMapEntryResponse:
    """
    Attributes:
        id (int | Unset):
        issuer_id (int | Unset):
        group_claim_value (str | Unset):
        role_type (RoleMapEntryResponseRoleType | Unset):
        unit_code (None | str | Unset):
    """

    id: int | Unset = UNSET
    issuer_id: int | Unset = UNSET
    group_claim_value: str | Unset = UNSET
    role_type: RoleMapEntryResponseRoleType | Unset = UNSET
    unit_code: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        issuer_id = self.issuer_id

        group_claim_value = self.group_claim_value

        role_type: str | Unset = UNSET
        if not isinstance(self.role_type, Unset):
            role_type = self.role_type.value

        unit_code: None | str | Unset
        if isinstance(self.unit_code, Unset):
            unit_code = UNSET
        else:
            unit_code = self.unit_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if issuer_id is not UNSET:
            field_dict["issuer_id"] = issuer_id
        if group_claim_value is not UNSET:
            field_dict["group_claim_value"] = group_claim_value
        if role_type is not UNSET:
            field_dict["role_type"] = role_type
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        issuer_id = d.pop("issuer_id", UNSET)

        group_claim_value = d.pop("group_claim_value", UNSET)

        _role_type = d.pop("role_type", UNSET)
        role_type: RoleMapEntryResponseRoleType | Unset
        if isinstance(_role_type, Unset):
            role_type = UNSET
        else:
            role_type = RoleMapEntryResponseRoleType(_role_type)

        def _parse_unit_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_code = _parse_unit_code(d.pop("unit_code", UNSET))

        role_map_entry_response = cls(
            id=id,
            issuer_id=issuer_id,
            group_claim_value=group_claim_value,
            role_type=role_type,
            unit_code=unit_code,
        )

        role_map_entry_response.additional_properties = d
        return role_map_entry_response

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
