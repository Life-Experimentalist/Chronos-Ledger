from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="GuestExtendVisitResponse200")


@_attrs_define
class GuestExtendVisitResponse200:
    """
    Attributes:
        status (str | Unset):  Example: VISIT_EXTENDED.
        guest (str | Unset): The visitor's name.
        visit_expires_at (datetime.datetime | Unset): When the visit is now over.
    """

    status: str | Unset = UNSET
    guest: str | Unset = UNSET
    visit_expires_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        guest = self.guest

        visit_expires_at: str | Unset = UNSET
        if not isinstance(self.visit_expires_at, Unset):
            visit_expires_at = self.visit_expires_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if guest is not UNSET:
            field_dict["guest"] = guest
        if visit_expires_at is not UNSET:
            field_dict["visit_expires_at"] = visit_expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status", UNSET)

        guest = d.pop("guest", UNSET)

        _visit_expires_at = d.pop("visit_expires_at", UNSET)
        visit_expires_at: datetime.datetime | Unset
        if isinstance(_visit_expires_at, Unset):
            visit_expires_at = UNSET
        else:
            visit_expires_at = datetime.datetime.fromisoformat(_visit_expires_at)

        guest_extend_visit_response_200 = cls(
            status=status,
            guest=guest,
            visit_expires_at=visit_expires_at,
        )

        guest_extend_visit_response_200.additional_properties = d
        return guest_extend_visit_response_200

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
