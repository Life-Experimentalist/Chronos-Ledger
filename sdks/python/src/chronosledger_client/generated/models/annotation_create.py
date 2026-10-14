from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AnnotationCreate")


@_attrs_define
class AnnotationCreate:
    """
    Attributes:
        ledger_instance_id (int):
        classification_tag (str): Free text, not a fixed vocabulary. Bounded because the column is a VARCHAR(30).
             Example: LATE_START.
        annotation_payload (str):  Example: Class started 10 minutes late due to lab setup..
    """

    ledger_instance_id: int
    classification_tag: str
    annotation_payload: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ledger_instance_id = self.ledger_instance_id

        classification_tag = self.classification_tag

        annotation_payload = self.annotation_payload

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ledger_instance_id": ledger_instance_id,
                "classification_tag": classification_tag,
                "annotation_payload": annotation_payload,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ledger_instance_id = d.pop("ledger_instance_id")

        classification_tag = d.pop("classification_tag")

        annotation_payload = d.pop("annotation_payload")

        annotation_create = cls(
            ledger_instance_id=ledger_instance_id,
            classification_tag=classification_tag,
            annotation_payload=annotation_payload,
        )

        annotation_create.additional_properties = d
        return annotation_create

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
