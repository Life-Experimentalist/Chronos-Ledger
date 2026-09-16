from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.log_verification_state import LogVerificationState
from ..types import UNSET, Unset

T = TypeVar("T", bound="GuestResponse")


@_attrs_define
class GuestResponse:
    """
    Attributes:
        id (int | Unset):
        guest_name (str | Unset):
        contact_phone (str | Unset):
        originating_body (str | Unset):
        target_staff_id (str | Unset):
        visitation_intent (str | Unset):
        handshake_status (LogVerificationState | Unset): Approval workflow state for absence requests and guest
            handshakes.
        timestamp_marked (datetime.datetime | Unset):
    """

    id: int | Unset = UNSET
    guest_name: str | Unset = UNSET
    contact_phone: str | Unset = UNSET
    originating_body: str | Unset = UNSET
    target_staff_id: str | Unset = UNSET
    visitation_intent: str | Unset = UNSET
    handshake_status: LogVerificationState | Unset = UNSET
    timestamp_marked: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        guest_name = self.guest_name

        contact_phone = self.contact_phone

        originating_body = self.originating_body

        target_staff_id = self.target_staff_id

        visitation_intent = self.visitation_intent

        handshake_status: str | Unset = UNSET
        if not isinstance(self.handshake_status, Unset):
            handshake_status = self.handshake_status.value

        timestamp_marked: str | Unset = UNSET
        if not isinstance(self.timestamp_marked, Unset):
            timestamp_marked = self.timestamp_marked.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if guest_name is not UNSET:
            field_dict["guest_name"] = guest_name
        if contact_phone is not UNSET:
            field_dict["contact_phone"] = contact_phone
        if originating_body is not UNSET:
            field_dict["originating_body"] = originating_body
        if target_staff_id is not UNSET:
            field_dict["target_staff_id"] = target_staff_id
        if visitation_intent is not UNSET:
            field_dict["visitation_intent"] = visitation_intent
        if handshake_status is not UNSET:
            field_dict["handshake_status"] = handshake_status
        if timestamp_marked is not UNSET:
            field_dict["timestamp_marked"] = timestamp_marked

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        guest_name = d.pop("guest_name", UNSET)

        contact_phone = d.pop("contact_phone", UNSET)

        originating_body = d.pop("originating_body", UNSET)

        target_staff_id = d.pop("target_staff_id", UNSET)

        visitation_intent = d.pop("visitation_intent", UNSET)

        _handshake_status = d.pop("handshake_status", UNSET)
        handshake_status: LogVerificationState | Unset
        if isinstance(_handshake_status, Unset):
            handshake_status = UNSET
        else:
            handshake_status = LogVerificationState(_handshake_status)

        _timestamp_marked = d.pop("timestamp_marked", UNSET)
        timestamp_marked: datetime.datetime | Unset
        if isinstance(_timestamp_marked, Unset):
            timestamp_marked = UNSET
        else:
            timestamp_marked = datetime.datetime.fromisoformat(_timestamp_marked)

        guest_response = cls(
            id=id,
            guest_name=guest_name,
            contact_phone=contact_phone,
            originating_body=originating_body,
            target_staff_id=target_staff_id,
            visitation_intent=visitation_intent,
            handshake_status=handshake_status,
            timestamp_marked=timestamp_marked,
        )

        guest_response.additional_properties = d
        return guest_response

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
