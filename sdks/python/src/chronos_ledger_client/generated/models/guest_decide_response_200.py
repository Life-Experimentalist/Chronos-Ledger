from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.log_verification_state import LogVerificationState
from ..types import UNSET, Unset

T = TypeVar("T", bound="GuestDecideResponse200")


@_attrs_define
class GuestDecideResponse200:
    """
    Attributes:
        status (LogVerificationState | Unset): Approval workflow state for absence requests and guest handshakes.
        guest (str | Unset): The visitor's name.
    """

    status: LogVerificationState | Unset = UNSET
    guest: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        guest = self.guest

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if guest is not UNSET:
            field_dict["guest"] = guest

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _status = d.pop("status", UNSET)
        status: LogVerificationState | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = LogVerificationState(_status)

        guest = d.pop("guest", UNSET)

        guest_decide_response_200 = cls(
            status=status,
            guest=guest,
        )

        guest_decide_response_200.additional_properties = d
        return guest_decide_response_200

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
