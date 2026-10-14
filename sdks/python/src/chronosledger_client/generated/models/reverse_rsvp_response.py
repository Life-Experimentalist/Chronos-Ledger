from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.log_verification_state import LogVerificationState
from ..types import UNSET, Unset

T = TypeVar("T", bound="ReverseRsvpResponse")


@_attrs_define
class ReverseRsvpResponse:
    """
    Attributes:
        id (int | Unset):
        submitting_user_id (str | Unset):
        target_absence_date (datetime.date | Unset):
        end_date (datetime.date | None | Unset):
        context_justification (str | Unset):
        approval_state (LogVerificationState | Unset): Approval workflow state for absence requests and guest
            handshakes.
        authorized_by_user_id (None | str | Unset):
    """

    id: int | Unset = UNSET
    submitting_user_id: str | Unset = UNSET
    target_absence_date: datetime.date | Unset = UNSET
    end_date: datetime.date | None | Unset = UNSET
    context_justification: str | Unset = UNSET
    approval_state: LogVerificationState | Unset = UNSET
    authorized_by_user_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        submitting_user_id = self.submitting_user_id

        target_absence_date: str | Unset = UNSET
        if not isinstance(self.target_absence_date, Unset):
            target_absence_date = self.target_absence_date.isoformat()

        end_date: None | str | Unset
        if isinstance(self.end_date, Unset):
            end_date = UNSET
        elif isinstance(self.end_date, datetime.date):
            end_date = self.end_date.isoformat()
        else:
            end_date = self.end_date

        context_justification = self.context_justification

        approval_state: str | Unset = UNSET
        if not isinstance(self.approval_state, Unset):
            approval_state = self.approval_state.value

        authorized_by_user_id: None | str | Unset
        if isinstance(self.authorized_by_user_id, Unset):
            authorized_by_user_id = UNSET
        else:
            authorized_by_user_id = self.authorized_by_user_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if submitting_user_id is not UNSET:
            field_dict["submitting_user_id"] = submitting_user_id
        if target_absence_date is not UNSET:
            field_dict["target_absence_date"] = target_absence_date
        if end_date is not UNSET:
            field_dict["end_date"] = end_date
        if context_justification is not UNSET:
            field_dict["context_justification"] = context_justification
        if approval_state is not UNSET:
            field_dict["approval_state"] = approval_state
        if authorized_by_user_id is not UNSET:
            field_dict["authorized_by_user_id"] = authorized_by_user_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        submitting_user_id = d.pop("submitting_user_id", UNSET)

        _target_absence_date = d.pop("target_absence_date", UNSET)
        target_absence_date: datetime.date | Unset
        if isinstance(_target_absence_date, Unset):
            target_absence_date = UNSET
        else:
            target_absence_date = datetime.date.fromisoformat(_target_absence_date)

        def _parse_end_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                end_date_type_0 = datetime.date.fromisoformat(data)

                return end_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        end_date = _parse_end_date(d.pop("end_date", UNSET))

        context_justification = d.pop("context_justification", UNSET)

        _approval_state = d.pop("approval_state", UNSET)
        approval_state: LogVerificationState | Unset
        if isinstance(_approval_state, Unset):
            approval_state = UNSET
        else:
            approval_state = LogVerificationState(_approval_state)

        def _parse_authorized_by_user_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        authorized_by_user_id = _parse_authorized_by_user_id(d.pop("authorized_by_user_id", UNSET))

        reverse_rsvp_response = cls(
            id=id,
            submitting_user_id=submitting_user_id,
            target_absence_date=target_absence_date,
            end_date=end_date,
            context_justification=context_justification,
            approval_state=approval_state,
            authorized_by_user_id=authorized_by_user_id,
        )

        reverse_rsvp_response.additional_properties = d
        return reverse_rsvp_response

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
