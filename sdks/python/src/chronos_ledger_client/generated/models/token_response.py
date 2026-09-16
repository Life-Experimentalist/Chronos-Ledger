from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.institutional_role import InstitutionalRole
from ..types import UNSET, Unset

T = TypeVar("T", bound="TokenResponse")


@_attrs_define
class TokenResponse:
    """
    Attributes:
        access_token (str | Unset): Signed JWT. Include as `Authorization: Bearer <token>`.
        refresh_token (str | Unset): Exchange at `POST /auth/refresh` for a new pair when the access token expires.
        token_type (str | Unset):  Example: bearer.
        user_id (str | Unset):  Example: FAC001.
        role (InstitutionalRole | Unset): Role assigned to a system user.
        full_name (str | Unset):  Example: Dr. Priya Sharma.
        initial_login_state (bool | Unset): True on first login, client should prompt password change.
    """

    access_token: str | Unset = UNSET
    refresh_token: str | Unset = UNSET
    token_type: str | Unset = UNSET
    user_id: str | Unset = UNSET
    role: InstitutionalRole | Unset = UNSET
    full_name: str | Unset = UNSET
    initial_login_state: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access_token = self.access_token

        refresh_token = self.refresh_token

        token_type = self.token_type

        user_id = self.user_id

        role: str | Unset = UNSET
        if not isinstance(self.role, Unset):
            role = self.role.value

        full_name = self.full_name

        initial_login_state = self.initial_login_state

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if access_token is not UNSET:
            field_dict["access_token"] = access_token
        if refresh_token is not UNSET:
            field_dict["refresh_token"] = refresh_token
        if token_type is not UNSET:
            field_dict["token_type"] = token_type
        if user_id is not UNSET:
            field_dict["user_id"] = user_id
        if role is not UNSET:
            field_dict["role"] = role
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if initial_login_state is not UNSET:
            field_dict["initial_login_state"] = initial_login_state

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        access_token = d.pop("access_token", UNSET)

        refresh_token = d.pop("refresh_token", UNSET)

        token_type = d.pop("token_type", UNSET)

        user_id = d.pop("user_id", UNSET)

        _role = d.pop("role", UNSET)
        role: InstitutionalRole | Unset
        if isinstance(_role, Unset):
            role = UNSET
        else:
            role = InstitutionalRole(_role)

        full_name = d.pop("full_name", UNSET)

        initial_login_state = d.pop("initial_login_state", UNSET)

        token_response = cls(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            user_id=user_id,
            role=role,
            full_name=full_name,
            initial_login_state=initial_login_state,
        )

        token_response.additional_properties = d
        return token_response

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
