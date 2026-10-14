from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.readiness_database import ReadinessDatabase
from ..models.readiness_redis import ReadinessRedis
from ..models.readiness_status import ReadinessStatus
from ..types import UNSET, Unset

T = TypeVar("T", bound="Readiness")


@_attrs_define
class Readiness:
    """
    Attributes:
        status (ReadinessStatus | Unset):
        database (ReadinessDatabase | Unset):
        redis (ReadinessRedis | Unset):
    """

    status: ReadinessStatus | Unset = UNSET
    database: ReadinessDatabase | Unset = UNSET
    redis: ReadinessRedis | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        database: str | Unset = UNSET
        if not isinstance(self.database, Unset):
            database = self.database.value

        redis: str | Unset = UNSET
        if not isinstance(self.redis, Unset):
            redis = self.redis.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if database is not UNSET:
            field_dict["database"] = database
        if redis is not UNSET:
            field_dict["redis"] = redis

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _status = d.pop("status", UNSET)
        status: ReadinessStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ReadinessStatus(_status)

        _database = d.pop("database", UNSET)
        database: ReadinessDatabase | Unset
        if isinstance(_database, Unset):
            database = UNSET
        else:
            database = ReadinessDatabase(_database)

        _redis = d.pop("redis", UNSET)
        redis: ReadinessRedis | Unset
        if isinstance(_redis, Unset):
            redis = UNSET
        else:
            redis = ReadinessRedis(_redis)

        readiness = cls(
            status=status,
            database=database,
            redis=redis,
        )

        readiness.additional_properties = d
        return readiness

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
