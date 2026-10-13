from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.webhook_event_type import WebhookEventType
from ..types import UNSET, Unset

T = TypeVar("T", bound="WebhookCreate")


@_attrs_define
class WebhookCreate:
    """
    Attributes:
        url (str): Where to POST each event. HTTPS, unless the host is listed in `WEBHOOK_ALLOW_HTTP_HOSTS`. A name that
            resolves to a loopback, private, link-local or otherwise internal address is refused unless
            `WEBHOOK_ALLOW_PRIVATE_TARGETS` is on.
             Example: https://receiver.example.com/hooks/chronos.
        event_types (list[WebhookEventType]): Which events to send. Stored sorted and deduplicated. Example:
            ['reservation.created', 'reservation.updated'].
        active (bool | Unset): An inactive subscription keeps its place and sends nothing. Made active again, it sends
            what happened in between.
             Default: True.
    """

    url: str
    event_types: list[WebhookEventType]
    active: bool | Unset = True
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        url = self.url

        event_types = []
        for event_types_item_data in self.event_types:
            event_types_item = event_types_item_data.value
            event_types.append(event_types_item)

        active = self.active

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "url": url,
                "event_types": event_types,
            }
        )
        if active is not UNSET:
            field_dict["active"] = active

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url = d.pop("url")

        event_types = []
        _event_types = d.pop("event_types")
        for event_types_item_data in _event_types:
            event_types_item = WebhookEventType(event_types_item_data)

            event_types.append(event_types_item)

        active = d.pop("active", UNSET)

        webhook_create = cls(
            url=url,
            event_types=event_types,
            active=active,
        )

        webhook_create.additional_properties = d
        return webhook_create

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
