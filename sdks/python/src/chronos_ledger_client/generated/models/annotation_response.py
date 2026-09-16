from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AnnotationResponse")


@_attrs_define
class AnnotationResponse:
    """
    Attributes:
        id (int | Unset):
        ledger_instance_id (int | Unset):
        creator_id (str | Unset):
        classification_tag (str | Unset):
        annotation_payload (str | Unset):
        distribution_timestamp (datetime.datetime | Unset):
    """

    id: int | Unset = UNSET
    ledger_instance_id: int | Unset = UNSET
    creator_id: str | Unset = UNSET
    classification_tag: str | Unset = UNSET
    annotation_payload: str | Unset = UNSET
    distribution_timestamp: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        ledger_instance_id = self.ledger_instance_id

        creator_id = self.creator_id

        classification_tag = self.classification_tag

        annotation_payload = self.annotation_payload

        distribution_timestamp: str | Unset = UNSET
        if not isinstance(self.distribution_timestamp, Unset):
            distribution_timestamp = self.distribution_timestamp.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if ledger_instance_id is not UNSET:
            field_dict["ledger_instance_id"] = ledger_instance_id
        if creator_id is not UNSET:
            field_dict["creator_id"] = creator_id
        if classification_tag is not UNSET:
            field_dict["classification_tag"] = classification_tag
        if annotation_payload is not UNSET:
            field_dict["annotation_payload"] = annotation_payload
        if distribution_timestamp is not UNSET:
            field_dict["distribution_timestamp"] = distribution_timestamp

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        ledger_instance_id = d.pop("ledger_instance_id", UNSET)

        creator_id = d.pop("creator_id", UNSET)

        classification_tag = d.pop("classification_tag", UNSET)

        annotation_payload = d.pop("annotation_payload", UNSET)

        _distribution_timestamp = d.pop("distribution_timestamp", UNSET)
        distribution_timestamp: datetime.datetime | Unset
        if isinstance(_distribution_timestamp, Unset):
            distribution_timestamp = UNSET
        else:
            distribution_timestamp = datetime.datetime.fromisoformat(_distribution_timestamp)

        annotation_response = cls(
            id=id,
            ledger_instance_id=ledger_instance_id,
            creator_id=creator_id,
            classification_tag=classification_tag,
            annotation_payload=annotation_payload,
            distribution_timestamp=distribution_timestamp,
        )

        annotation_response.additional_properties = d
        return annotation_response

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
