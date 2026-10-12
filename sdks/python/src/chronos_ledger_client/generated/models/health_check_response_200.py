from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="HealthCheckResponse200")


@_attrs_define
class HealthCheckResponse200:
    """
    Attributes:
        status (str | Unset):  Example: healthy.
        service (str | Unset):  Example: chronos-ledger.
        version (str | Unset):  Example: 0.13.0.
        schema_version (str | Unset): Bumped by the maintainers when the models change. There are no migrations: a
            database built by one schema version is not upgraded to the next.
             Example: 1.
    """

    status: str | Unset = UNSET
    service: str | Unset = UNSET
    version: str | Unset = UNSET
    schema_version: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        service = self.service

        version = self.version

        schema_version = self.schema_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if service is not UNSET:
            field_dict["service"] = service
        if version is not UNSET:
            field_dict["version"] = version
        if schema_version is not UNSET:
            field_dict["schema_version"] = schema_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = d.pop("status", UNSET)

        service = d.pop("service", UNSET)

        version = d.pop("version", UNSET)

        schema_version = d.pop("schema_version", UNSET)

        health_check_response_200 = cls(
            status=status,
            service=service,
            version=version,
            schema_version=schema_version,
        )

        health_check_response_200.additional_properties = d
        return health_check_response_200

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
