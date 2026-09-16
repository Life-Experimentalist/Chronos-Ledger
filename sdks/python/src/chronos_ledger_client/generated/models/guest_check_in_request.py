from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

T = TypeVar("T", bound="GuestCheckInRequest")


@_attrs_define
class GuestCheckInRequest:
    """
    Attributes:
        guest_name (str):  Example: John Smith.
        contact_phone (str):  Example: +91 98765 43210.
        originating_body (str):  Example: TechCorp Ltd.
        target_staff_id (str):  Example: FAC001.
        visitation_intent (str):  Example: Research collaboration discussion.
    """

    guest_name: str
    contact_phone: str
    originating_body: str
    target_staff_id: str
    visitation_intent: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        guest_name = self.guest_name

        contact_phone = self.contact_phone

        originating_body = self.originating_body

        target_staff_id = self.target_staff_id

        visitation_intent = self.visitation_intent

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "guest_name": guest_name,
                "contact_phone": contact_phone,
                "originating_body": originating_body,
                "target_staff_id": target_staff_id,
                "visitation_intent": visitation_intent,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        guest_name = d.pop("guest_name")

        contact_phone = d.pop("contact_phone")

        originating_body = d.pop("originating_body")

        target_staff_id = d.pop("target_staff_id")

        visitation_intent = d.pop("visitation_intent")

        guest_check_in_request = cls(
            guest_name=guest_name,
            contact_phone=contact_phone,
            originating_body=originating_body,
            target_staff_id=target_staff_id,
            visitation_intent=visitation_intent,
        )

        guest_check_in_request.additional_properties = d
        return guest_check_in_request

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
