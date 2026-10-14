from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.webhook_event_type import WebhookEventType
from ..types import UNSET, Unset

T = TypeVar("T", bound="WebhookWithSecret")


@_attrs_define
class WebhookWithSecret:
    """
    Attributes:
        secret (str): The signing secret, `whsec_` and the base64 of 32 random bytes. Returned here and nowhere else, so
            keep it: it cannot be read back, only replaced by rotating.
        id (int | Unset):
        url (str | Unset):
        event_types (list[WebhookEventType] | Unset):
        active (bool | Unset):
        paused_at (datetime.datetime | None | Unset): Set while the subscription is paused, after five deliveries in a
            row ran out of attempts or by an import that carried no secrets. Cleared by resume.
        consecutive_failures (int | Unset): Deliveries in a row that ran out of attempts. A success resets it.
        previous_secret_expires_at (datetime.datetime | None | Unset): Set while the secret before the last rotation
            still signs alongside the current one.
        created_at (datetime.datetime | None | Unset):
        updated_at (datetime.datetime | None | Unset):
    """

    secret: str
    id: int | Unset = UNSET
    url: str | Unset = UNSET
    event_types: list[WebhookEventType] | Unset = UNSET
    active: bool | Unset = UNSET
    paused_at: datetime.datetime | None | Unset = UNSET
    consecutive_failures: int | Unset = UNSET
    previous_secret_expires_at: datetime.datetime | None | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    updated_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        secret = self.secret

        id = self.id

        url = self.url

        event_types: list[str] | Unset = UNSET
        if not isinstance(self.event_types, Unset):
            event_types = []
            for event_types_item_data in self.event_types:
                event_types_item = event_types_item_data.value
                event_types.append(event_types_item)

        active = self.active

        paused_at: None | str | Unset
        if isinstance(self.paused_at, Unset):
            paused_at = UNSET
        elif isinstance(self.paused_at, datetime.datetime):
            paused_at = self.paused_at.isoformat()
        else:
            paused_at = self.paused_at

        consecutive_failures = self.consecutive_failures

        previous_secret_expires_at: None | str | Unset
        if isinstance(self.previous_secret_expires_at, Unset):
            previous_secret_expires_at = UNSET
        elif isinstance(self.previous_secret_expires_at, datetime.datetime):
            previous_secret_expires_at = self.previous_secret_expires_at.isoformat()
        else:
            previous_secret_expires_at = self.previous_secret_expires_at

        created_at: None | str | Unset
        if isinstance(self.created_at, Unset):
            created_at = UNSET
        elif isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        updated_at: None | str | Unset
        if isinstance(self.updated_at, Unset):
            updated_at = UNSET
        elif isinstance(self.updated_at, datetime.datetime):
            updated_at = self.updated_at.isoformat()
        else:
            updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "secret": secret,
            }
        )
        if id is not UNSET:
            field_dict["id"] = id
        if url is not UNSET:
            field_dict["url"] = url
        if event_types is not UNSET:
            field_dict["event_types"] = event_types
        if active is not UNSET:
            field_dict["active"] = active
        if paused_at is not UNSET:
            field_dict["paused_at"] = paused_at
        if consecutive_failures is not UNSET:
            field_dict["consecutive_failures"] = consecutive_failures
        if previous_secret_expires_at is not UNSET:
            field_dict["previous_secret_expires_at"] = previous_secret_expires_at
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        secret = d.pop("secret")

        id = d.pop("id", UNSET)

        url = d.pop("url", UNSET)

        _event_types = d.pop("event_types", UNSET)
        event_types: list[WebhookEventType] | Unset = UNSET
        if _event_types is not UNSET:
            event_types = []
            for event_types_item_data in _event_types:
                event_types_item = WebhookEventType(event_types_item_data)

                event_types.append(event_types_item)

        active = d.pop("active", UNSET)

        def _parse_paused_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                paused_at_type_0 = datetime.datetime.fromisoformat(data)

                return paused_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        paused_at = _parse_paused_at(d.pop("paused_at", UNSET))

        consecutive_failures = d.pop("consecutive_failures", UNSET)

        def _parse_previous_secret_expires_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                previous_secret_expires_at_type_0 = datetime.datetime.fromisoformat(data)

                return previous_secret_expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        previous_secret_expires_at = _parse_previous_secret_expires_at(
            d.pop("previous_secret_expires_at", UNSET)
        )

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

        def _parse_updated_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                updated_at_type_0 = datetime.datetime.fromisoformat(data)

                return updated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        updated_at = _parse_updated_at(d.pop("updated_at", UNSET))

        webhook_with_secret = cls(
            secret=secret,
            id=id,
            url=url,
            event_types=event_types,
            active=active,
            paused_at=paused_at,
            consecutive_failures=consecutive_failures,
            previous_secret_expires_at=previous_secret_expires_at,
            created_at=created_at,
            updated_at=updated_at,
        )

        webhook_with_secret.additional_properties = d
        return webhook_with_secret

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
