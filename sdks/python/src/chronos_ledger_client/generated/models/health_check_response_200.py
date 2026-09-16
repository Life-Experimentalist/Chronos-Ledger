from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="HealthCheckResponse200")


@_attrs_define
class HealthCheckResponse200:
    """
    Attributes:
        status (str | Unset):  Example: healthy.
        service (str | Unset):  Example: chronos-ledger.
        version (str | Unset):  Example: 0.13.0.
        migration_revision (None | str | Unset): Null before the first migration. Example: 022.
    """

    status: str | Unset = UNSET
    service: str | Unset = UNSET
    version: str | Unset = UNSET
    migration_revision: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        service = self.service

        version = self.version

        migration_revision: None | str | Unset
        if isinstance(self.migration_revision, Unset):
            migration_revision = UNSET
        else:
            migration_revision = self.migration_revision

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if service is not UNSET:
            field_dict["service"] = service
        if version is not UNSET:
            field_dict["version"] = version
        if migration_revision is not UNSET:
            field_dict["migration_revision"] = migration_revision

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        status = d.pop("status", UNSET)

        service = d.pop("service", UNSET)

        version = d.pop("version", UNSET)

        def _parse_migration_revision(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        migration_revision = _parse_migration_revision(
            d.pop("migration_revision", UNSET)
        )

        health_check_response_200 = cls(
            status=status,
            service=service,
            version=version,
            migration_revision=migration_revision,
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
