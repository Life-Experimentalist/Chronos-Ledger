from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.reservation_response import ReservationResponse
    from ..models.resource_response import ResourceResponse


T = TypeVar("T", bound="Change")


@_attrs_define
class Change:
    """One thing that changed, and what it now holds. `resource` and `reservation` are the row as it stands, one of them
    filled in according to `entity_kind`, so an entry can be applied without a second request. Both are null in the full
    log, which is the markers alone.

        Attributes:
            cursor (int | Unset): Send the last one back as `since`, or `next_cursor`, which is the same number.
            entity_kind (str | Unset): `resource` or `reservation`. Not a closed set: another part of the API gaining a feed
                adds a kind here, and a consumer should ignore one it does not know rather than fail on it.
            entity_id (int | Unset):
            change_kind (str | Unset): `created` or `updated`, and likewise open. Measured against the cursor that was sent
                in, not against the row's whole history: a row created and then edited between two polls reads as `created`,
                because the caller has never seen it. There is no `deleted`: nothing this feed carries is deleted, and a
                cancelled booking keeps its row and reads as `updated`.
            at (datetime.datetime | Unset): When the most recent of the collapsed changes was made.
            resource (None | ResourceResponse | Unset):
            reservation (None | ReservationResponse | Unset):
    """

    cursor: int | Unset = UNSET
    entity_kind: str | Unset = UNSET
    entity_id: int | Unset = UNSET
    change_kind: str | Unset = UNSET
    at: datetime.datetime | Unset = UNSET
    resource: None | ResourceResponse | Unset = UNSET
    reservation: None | ReservationResponse | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.reservation_response import ReservationResponse  # noqa: PLC0415
        from ..models.resource_response import ResourceResponse  # noqa: PLC0415

        cursor = self.cursor

        entity_kind = self.entity_kind

        entity_id = self.entity_id

        change_kind = self.change_kind

        at: str | Unset = UNSET
        if not isinstance(self.at, Unset):
            at = self.at.isoformat()

        resource: dict[str, Any] | None | Unset
        if isinstance(self.resource, Unset):
            resource = UNSET
        elif isinstance(self.resource, ResourceResponse):
            resource = self.resource.to_dict()
        else:
            resource = self.resource

        reservation: dict[str, Any] | None | Unset
        if isinstance(self.reservation, Unset):
            reservation = UNSET
        elif isinstance(self.reservation, ReservationResponse):
            reservation = self.reservation.to_dict()
        else:
            reservation = self.reservation

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if cursor is not UNSET:
            field_dict["cursor"] = cursor
        if entity_kind is not UNSET:
            field_dict["entity_kind"] = entity_kind
        if entity_id is not UNSET:
            field_dict["entity_id"] = entity_id
        if change_kind is not UNSET:
            field_dict["change_kind"] = change_kind
        if at is not UNSET:
            field_dict["at"] = at
        if resource is not UNSET:
            field_dict["resource"] = resource
        if reservation is not UNSET:
            field_dict["reservation"] = reservation

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reservation_response import ReservationResponse  # noqa: PLC0415
        from ..models.resource_response import ResourceResponse  # noqa: PLC0415

        d = dict(src_dict)
        cursor = d.pop("cursor", UNSET)

        entity_kind = d.pop("entity_kind", UNSET)

        entity_id = d.pop("entity_id", UNSET)

        change_kind = d.pop("change_kind", UNSET)

        _at = d.pop("at", UNSET)
        at: datetime.datetime | Unset
        if isinstance(_at, Unset):
            at = UNSET
        else:
            at = datetime.datetime.fromisoformat(_at)

        def _parse_resource(data: object) -> None | ResourceResponse | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                resource_type_1 = ResourceResponse.from_dict(data)

                return resource_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResourceResponse | Unset, data)

        resource = _parse_resource(d.pop("resource", UNSET))

        def _parse_reservation(data: object) -> None | ReservationResponse | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                reservation_type_1 = ReservationResponse.from_dict(data)

                return reservation_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ReservationResponse | Unset, data)

        reservation = _parse_reservation(d.pop("reservation", UNSET))

        change = cls(
            cursor=cursor,
            entity_kind=entity_kind,
            entity_id=entity_id,
            change_kind=change_kind,
            at=at,
            resource=resource,
            reservation=reservation,
        )

        change.additional_properties = d
        return change

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
