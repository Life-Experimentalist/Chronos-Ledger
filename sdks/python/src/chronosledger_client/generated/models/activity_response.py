from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ActivityResponse")


@_attrs_define
class ActivityResponse:
    """
    Attributes:
        id (int | Unset):
        activity_code (str | Unset):
        activity_title (str | Unset):
        unit_code (str | Unset):
        cycle_id (int | Unset):
        retired_at (datetime.datetime | None | Unset): When the activity was retired. Null while it is live.
    """

    id: int | Unset = UNSET
    activity_code: str | Unset = UNSET
    activity_title: str | Unset = UNSET
    unit_code: str | Unset = UNSET
    cycle_id: int | Unset = UNSET
    retired_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        activity_code = self.activity_code

        activity_title = self.activity_title

        unit_code = self.unit_code

        cycle_id = self.cycle_id

        retired_at: None | str | Unset
        if isinstance(self.retired_at, Unset):
            retired_at = UNSET
        elif isinstance(self.retired_at, datetime.datetime):
            retired_at = self.retired_at.isoformat()
        else:
            retired_at = self.retired_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if activity_code is not UNSET:
            field_dict["activity_code"] = activity_code
        if activity_title is not UNSET:
            field_dict["activity_title"] = activity_title
        if unit_code is not UNSET:
            field_dict["unit_code"] = unit_code
        if cycle_id is not UNSET:
            field_dict["cycle_id"] = cycle_id
        if retired_at is not UNSET:
            field_dict["retired_at"] = retired_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        activity_code = d.pop("activity_code", UNSET)

        activity_title = d.pop("activity_title", UNSET)

        unit_code = d.pop("unit_code", UNSET)

        cycle_id = d.pop("cycle_id", UNSET)

        def _parse_retired_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                retired_at_type_0 = datetime.datetime.fromisoformat(data)

                return retired_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        retired_at = _parse_retired_at(d.pop("retired_at", UNSET))

        activity_response = cls(
            id=id,
            activity_code=activity_code,
            activity_title=activity_title,
            unit_code=unit_code,
            cycle_id=cycle_id,
            retired_at=retired_at,
        )

        activity_response.additional_properties = d
        return activity_response

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
