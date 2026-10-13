from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.webhook_delivery_response_entity_kind import WebhookDeliveryResponseEntityKind
from ..models.webhook_delivery_response_status import WebhookDeliveryResponseStatus
from ..models.webhook_event_type import WebhookEventType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.webhook_attempt_response import WebhookAttemptResponse


T = TypeVar("T", bound="WebhookDeliveryResponse")


@_attrs_define
class WebhookDeliveryResponse:
    """
    Attributes:
        id (int | Unset):
        subscription_id (int | Unset):
        event_id (str | Unset): The `webhook-id` header, the same on every attempt.
        event_type (WebhookEventType | Unset):
        entity_kind (WebhookDeliveryResponseEntityKind | Unset):
        entity_id (int | Unset):
        marker_id (int | Unset): The change feed cursor this delivery was made from.
        status (WebhookDeliveryResponseStatus | Unset):
        attempt_count (int | Unset):
        next_attempt_at (datetime.datetime | None | Unset):
        created_at (datetime.datetime | None | Unset):
        completed_at (datetime.datetime | None | Unset):
        attempts (list[WebhookAttemptResponse] | Unset):
    """

    id: int | Unset = UNSET
    subscription_id: int | Unset = UNSET
    event_id: str | Unset = UNSET
    event_type: WebhookEventType | Unset = UNSET
    entity_kind: WebhookDeliveryResponseEntityKind | Unset = UNSET
    entity_id: int | Unset = UNSET
    marker_id: int | Unset = UNSET
    status: WebhookDeliveryResponseStatus | Unset = UNSET
    attempt_count: int | Unset = UNSET
    next_attempt_at: datetime.datetime | None | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    completed_at: datetime.datetime | None | Unset = UNSET
    attempts: list[WebhookAttemptResponse] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        subscription_id = self.subscription_id

        event_id = self.event_id

        event_type: str | Unset = UNSET
        if not isinstance(self.event_type, Unset):
            event_type = self.event_type.value

        entity_kind: str | Unset = UNSET
        if not isinstance(self.entity_kind, Unset):
            entity_kind = self.entity_kind.value

        entity_id = self.entity_id

        marker_id = self.marker_id

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        attempt_count = self.attempt_count

        next_attempt_at: None | str | Unset
        if isinstance(self.next_attempt_at, Unset):
            next_attempt_at = UNSET
        elif isinstance(self.next_attempt_at, datetime.datetime):
            next_attempt_at = self.next_attempt_at.isoformat()
        else:
            next_attempt_at = self.next_attempt_at

        created_at: None | str | Unset
        if isinstance(self.created_at, Unset):
            created_at = UNSET
        elif isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        completed_at: None | str | Unset
        if isinstance(self.completed_at, Unset):
            completed_at = UNSET
        elif isinstance(self.completed_at, datetime.datetime):
            completed_at = self.completed_at.isoformat()
        else:
            completed_at = self.completed_at

        attempts: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attempts, Unset):
            attempts = []
            for attempts_item_data in self.attempts:
                attempts_item = attempts_item_data.to_dict()
                attempts.append(attempts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if subscription_id is not UNSET:
            field_dict["subscription_id"] = subscription_id
        if event_id is not UNSET:
            field_dict["event_id"] = event_id
        if event_type is not UNSET:
            field_dict["event_type"] = event_type
        if entity_kind is not UNSET:
            field_dict["entity_kind"] = entity_kind
        if entity_id is not UNSET:
            field_dict["entity_id"] = entity_id
        if marker_id is not UNSET:
            field_dict["marker_id"] = marker_id
        if status is not UNSET:
            field_dict["status"] = status
        if attempt_count is not UNSET:
            field_dict["attempt_count"] = attempt_count
        if next_attempt_at is not UNSET:
            field_dict["next_attempt_at"] = next_attempt_at
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if completed_at is not UNSET:
            field_dict["completed_at"] = completed_at
        if attempts is not UNSET:
            field_dict["attempts"] = attempts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.webhook_attempt_response import WebhookAttemptResponse  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        subscription_id = d.pop("subscription_id", UNSET)

        event_id = d.pop("event_id", UNSET)

        _event_type = d.pop("event_type", UNSET)
        event_type: WebhookEventType | Unset
        if isinstance(_event_type, Unset):
            event_type = UNSET
        else:
            event_type = WebhookEventType(_event_type)

        _entity_kind = d.pop("entity_kind", UNSET)
        entity_kind: WebhookDeliveryResponseEntityKind | Unset
        if isinstance(_entity_kind, Unset):
            entity_kind = UNSET
        else:
            entity_kind = WebhookDeliveryResponseEntityKind(_entity_kind)

        entity_id = d.pop("entity_id", UNSET)

        marker_id = d.pop("marker_id", UNSET)

        _status = d.pop("status", UNSET)
        status: WebhookDeliveryResponseStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = WebhookDeliveryResponseStatus(_status)

        attempt_count = d.pop("attempt_count", UNSET)

        def _parse_next_attempt_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_attempt_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_attempt_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        next_attempt_at = _parse_next_attempt_at(d.pop("next_attempt_at", UNSET))

        def _parse_created_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                created_at_type_0 = datetime.datetime.fromisoformat(data)

                return created_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        created_at = _parse_created_at(d.pop("created_at", UNSET))

        def _parse_completed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                completed_at_type_0 = datetime.datetime.fromisoformat(data)

                return completed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        completed_at = _parse_completed_at(d.pop("completed_at", UNSET))

        _attempts = d.pop("attempts", UNSET)
        attempts: list[WebhookAttemptResponse] | Unset = UNSET
        if _attempts is not UNSET:
            attempts = []
            for attempts_item_data in _attempts:
                attempts_item = WebhookAttemptResponse.from_dict(attempts_item_data)

                attempts.append(attempts_item)

        webhook_delivery_response = cls(
            id=id,
            subscription_id=subscription_id,
            event_id=event_id,
            event_type=event_type,
            entity_kind=entity_kind,
            entity_id=entity_id,
            marker_id=marker_id,
            status=status,
            attempt_count=attempt_count,
            next_attempt_at=next_attempt_at,
            created_at=created_at,
            completed_at=completed_at,
            attempts=attempts,
        )

        webhook_delivery_response.additional_properties = d
        return webhook_delivery_response

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
