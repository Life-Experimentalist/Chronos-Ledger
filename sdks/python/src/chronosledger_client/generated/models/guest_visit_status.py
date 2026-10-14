from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.log_verification_state import LogVerificationState
from ..types import UNSET, Unset

T = TypeVar("T", bound="GuestVisitStatus")


@_attrs_define
class GuestVisitStatus:
    """What a visit code opens. The name, phone and target are left out, because a code on a kiosk screen can be read over
    a shoulder.

        Attributes:
            handshake_status (LogVerificationState | Unset): Approval workflow state for absence requests and guest
                handshakes.
            timestamp_marked (datetime.datetime | Unset): When the visitor checked in.
            visit_expires_at (datetime.datetime | None | Unset): When to leave, which is the one thing the visitor most
                needs from this and gives away nothing about them: whoever reads the code over a shoulder learns a time, not a
                name. Null is an open-ended visit.
    """

    handshake_status: LogVerificationState | Unset = UNSET
    timestamp_marked: datetime.datetime | Unset = UNSET
    visit_expires_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        handshake_status: str | Unset = UNSET
        if not isinstance(self.handshake_status, Unset):
            handshake_status = self.handshake_status.value

        timestamp_marked: str | Unset = UNSET
        if not isinstance(self.timestamp_marked, Unset):
            timestamp_marked = self.timestamp_marked.isoformat()

        visit_expires_at: None | str | Unset
        if isinstance(self.visit_expires_at, Unset):
            visit_expires_at = UNSET
        elif isinstance(self.visit_expires_at, datetime.datetime):
            visit_expires_at = self.visit_expires_at.isoformat()
        else:
            visit_expires_at = self.visit_expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if handshake_status is not UNSET:
            field_dict["handshake_status"] = handshake_status
        if timestamp_marked is not UNSET:
            field_dict["timestamp_marked"] = timestamp_marked
        if visit_expires_at is not UNSET:
            field_dict["visit_expires_at"] = visit_expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
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

        def _parse_visit_expires_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                visit_expires_at_type_0 = datetime.datetime.fromisoformat(data)

                return visit_expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        visit_expires_at = _parse_visit_expires_at(d.pop("visit_expires_at", UNSET))

        guest_visit_status = cls(
            handshake_status=handshake_status,
            timestamp_marked=timestamp_marked,
            visit_expires_at=visit_expires_at,
        )

        guest_visit_status.additional_properties = d
        return guest_visit_status

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
