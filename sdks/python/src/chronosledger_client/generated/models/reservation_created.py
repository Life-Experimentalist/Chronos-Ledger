from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.reservation_response_status import ReservationResponseStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.reservation_response import ReservationResponse
    from ..models.unmet_requirement import UnmetRequirement


T = TypeVar("T", bound="ReservationCreated")


@_attrs_define
class ReservationCreated:
    """A new booking with what its requirements held alongside it.

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
        quantity (int | Unset): Units taken. Always 1 off a POOLED resource.
        external_ref (None | str | Unset): The caller's own identifier for the booking, or null if it was given none. A
            cancelled booking keeps its reference.
        created_at (datetime.datetime | Unset):
        cancelled_at (datetime.datetime | None | Unset):
        parent_reservation_id (int | None | Unset): The booking this hold was taken for, when a requirement of the
            resource made it. Null on a booking somebody asked for. Cancelling the parent cancels the holds that name it
            here.
        children (list[ReservationResponse] | Unset): The holds the resource's requirements took under this booking, at
            every depth of a chain, in the order they were taken. Empty when the resource requires nothing. A replay of the
            same request answers with the children as they stand now.
        unmet (list[UnmetRequirement] | Unset): The ADVISORY requirements that could not be met. The booking went ahead
            without them. A REQUIRED one that cannot be met refuses the booking instead (`REQUIREMENT_UNSATISFIED`). Always
            empty on a replay, because a gap is not stored.
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
    quantity: int | Unset = UNSET
    external_ref: None | str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    cancelled_at: datetime.datetime | None | Unset = UNSET
    parent_reservation_id: int | None | Unset = UNSET
    children: list[ReservationResponse] | Unset = UNSET
    unmet: list[UnmetRequirement] | Unset = UNSET
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

        quantity = self.quantity

        external_ref: None | str | Unset
        if isinstance(self.external_ref, Unset):
            external_ref = UNSET
        else:
            external_ref = self.external_ref

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

        parent_reservation_id: int | None | Unset
        if isinstance(self.parent_reservation_id, Unset):
            parent_reservation_id = UNSET
        else:
            parent_reservation_id = self.parent_reservation_id

        children: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.children, Unset):
            children = []
            for children_item_data in self.children:
                children_item = children_item_data.to_dict()
                children.append(children_item)

        unmet: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.unmet, Unset):
            unmet = []
            for unmet_item_data in self.unmet:
                unmet_item = unmet_item_data.to_dict()
                unmet.append(unmet_item)

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
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if external_ref is not UNSET:
            field_dict["external_ref"] = external_ref
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if cancelled_at is not UNSET:
            field_dict["cancelled_at"] = cancelled_at
        if parent_reservation_id is not UNSET:
            field_dict["parent_reservation_id"] = parent_reservation_id
        if children is not UNSET:
            field_dict["children"] = children
        if unmet is not UNSET:
            field_dict["unmet"] = unmet

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reservation_response import ReservationResponse  # noqa: PLC0415
        from ..models.unmet_requirement import UnmetRequirement  # noqa: PLC0415

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

        quantity = d.pop("quantity", UNSET)

        def _parse_external_ref(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        external_ref = _parse_external_ref(d.pop("external_ref", UNSET))

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

        def _parse_parent_reservation_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        parent_reservation_id = _parse_parent_reservation_id(d.pop("parent_reservation_id", UNSET))

        _children = d.pop("children", UNSET)
        children: list[ReservationResponse] | Unset = UNSET
        if _children is not UNSET:
            children = []
            for children_item_data in _children:
                children_item = ReservationResponse.from_dict(children_item_data)

                children.append(children_item)

        _unmet = d.pop("unmet", UNSET)
        unmet: list[UnmetRequirement] | Unset = UNSET
        if _unmet is not UNSET:
            unmet = []
            for unmet_item_data in _unmet:
                unmet_item = UnmetRequirement.from_dict(unmet_item_data)

                unmet.append(unmet_item)

        reservation_created = cls(
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
            quantity=quantity,
            external_ref=external_ref,
            created_at=created_at,
            cancelled_at=cancelled_at,
            parent_reservation_id=parent_reservation_id,
            children=children,
            unmet=unmet,
        )

        reservation_created.additional_properties = d
        return reservation_created

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
