from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="GuestCheckInResponse200")


@_attrs_define
class GuestCheckInResponse200:
    """
    Attributes:
        registration_state (str | Unset):  Example: PENDING_STAFF_AUTH.
        reference_token (int | Unset): The entry id that `/guest/{entry_id}/decide` takes.
        visit_code (str | Unset): The visitor's code for `/guest/visit/{code}`. It is in this response and nowhere else:
            the server keeps only its hash.
             Example: 7KQM-3XHP-R9DW-4TNC.
    """

    registration_state: str | Unset = UNSET
    reference_token: int | Unset = UNSET
    visit_code: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        registration_state = self.registration_state

        reference_token = self.reference_token

        visit_code = self.visit_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if registration_state is not UNSET:
            field_dict["registration_state"] = registration_state
        if reference_token is not UNSET:
            field_dict["reference_token"] = reference_token
        if visit_code is not UNSET:
            field_dict["visit_code"] = visit_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        registration_state = d.pop("registration_state", UNSET)

        reference_token = d.pop("reference_token", UNSET)

        visit_code = d.pop("visit_code", UNSET)

        guest_check_in_response_200 = cls(
            registration_state=registration_state,
            reference_token=reference_token,
            visit_code=visit_code,
        )

        guest_check_in_response_200.additional_properties = d
        return guest_check_in_response_200

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
