from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.reservation_response_status import ReservationResponseStatus
from ..types import UNSET, Unset

T = TypeVar("T", bound="ReservationResponse")


@_attrs_define
class ReservationResponse:
    """
    Attributes:
        id (int | Unset):
        resource_id (int | Unset):
        resource_code (str | Unset):
        date (datetime.date | Unset):
        start (str | Unset):
        end (str | Unset):
        purpose (str | Unset): Returned only to the caller that made the booking. It is not on the availability
            calendar, which anyone signed in can read.
        status (ReservationResponseStatus | Unset):
        requested_by_id (None | str | Unset): Null once the account that booked it has been deleted. A hold outlives the
            service account that placed it.
        idempotency_key (str | Unset):
        created_at (datetime.datetime | Unset):
        cancelled_at (datetime.datetime | None | Unset):
    """

    id: int | Unset = UNSET
    resource_id: int | Unset = UNSET
    resource_code: str | Unset = UNSET
    date: datetime.date | Unset = UNSET
    start: str | Unset = UNSET
    end: str | Unset = UNSET
    purpose: str | Unset = UNSET
    status: ReservationResponseStatus | Unset = UNSET
    requested_by_id: None | str | Unset = UNSET
    idempotency_key: str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    cancelled_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        resource_id = self.resource_id

        resource_code = self.resource_code

        date: str | Unset = UNSET
        if not isinstance(self.date, Unset):
            date = self.date.isoformat()

        start = self.start

        end = self.end

        purpose = self.purpose

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        requested_by_id: None | str | Unset
        if isinstance(self.requested_by_id, Unset):
            requested_by_id = UNSET
        else:
            requested_by_id = self.requested_by_id

        idempotency_key = self.idempotency_key

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        cancelled_at: None | str | Unset
        if isinstance(self.cancelled_at, Unset):
            cancelled_at = UNSET
        elif isinstance(self.cancelled_at, datetime.datetime):
            cancelled_at = self.cancelled_at.isoformat()
        else:
            cancelled_at = self.cancelled_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if resource_id is not UNSET:
            field_dict["resource_id"] = resource_id
        if resource_code is not UNSET:
            field_dict["resource_code"] = resource_code
        if date is not UNSET:
            field_dict["date"] = date
        if start is not UNSET:
            field_dict["start"] = start
        if end is not UNSET:
            field_dict["end"] = end
        if purpose is not UNSET:
            field_dict["purpose"] = purpose
        if status is not UNSET:
            field_dict["status"] = status
        if requested_by_id is not UNSET:
            field_dict["requested_by_id"] = requested_by_id
        if idempotency_key is not UNSET:
            field_dict["idempotency_key"] = idempotency_key
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if cancelled_at is not UNSET:
            field_dict["cancelled_at"] = cancelled_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        resource_id = d.pop("resource_id", UNSET)

        resource_code = d.pop("resource_code", UNSET)

        _date = d.pop("date", UNSET)
        date: datetime.date | Unset
        if isinstance(_date, Unset):
            date = UNSET
        else:
            date = datetime.date.fromisoformat(_date)

        start = d.pop("start", UNSET)

        end = d.pop("end", UNSET)

        purpose = d.pop("purpose", UNSET)

        _status = d.pop("status", UNSET)
        status: ReservationResponseStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ReservationResponseStatus(_status)

        def _parse_requested_by_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        requested_by_id = _parse_requested_by_id(d.pop("requested_by_id", UNSET))

        idempotency_key = d.pop("idempotency_key", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        def _parse_cancelled_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                cancelled_at_type_0 = datetime.datetime.fromisoformat(data)

                return cancelled_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        cancelled_at = _parse_cancelled_at(d.pop("cancelled_at", UNSET))

        reservation_response = cls(
            id=id,
            resource_id=resource_id,
            resource_code=resource_code,
            date=date,
            start=start,
            end=end,
            purpose=purpose,
            status=status,
            requested_by_id=requested_by_id,
            idempotency_key=idempotency_key,
            created_at=created_at,
            cancelled_at=cancelled_at,
        )

        reservation_response.additional_properties = d
        return reservation_response

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
