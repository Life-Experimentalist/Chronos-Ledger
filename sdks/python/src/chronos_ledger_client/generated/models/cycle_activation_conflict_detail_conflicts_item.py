from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..types import UNSET, Unset

T = TypeVar("T", bound="CycleActivationConflictDetailConflictsItem")


@_attrs_define
class CycleActivationConflictDetailConflictsItem:
    """
    Attributes:
        blocked_slot_id (int): The slot in the cycle being opened that this interval stands against.
             Example: 88.
        date (datetime.date | Unset):  Example: 2026-01-05.
        start (str | Unset):  Example: 09:00:00.
        end_date (datetime.date | Unset): Always present, and the same as date for a window that finishes on the day it
            started. It is spelled out rather than left to be inferred, because inferring it wrong is silent: a reader that
            takes date with end and ignores this computes minus sixteen hours for a night shift running 22:00 to 06:00, and
            a plausible answer for every interval written before overnight windows existed.
             Example: 2026-01-05.
        end (str | Unset):  Example: 10:00:00.
        activity_id (int | None | Unset):
        activity_code (None | str | Unset):
        master_slot_id (int | None | Unset):
        reservation_id (int | None | Unset):
    """

    blocked_slot_id: int
    date: datetime.date | Unset = UNSET
    start: str | Unset = UNSET
    end_date: datetime.date | Unset = UNSET
    end: str | Unset = UNSET
    activity_id: int | None | Unset = UNSET
    activity_code: None | str | Unset = UNSET
    master_slot_id: int | None | Unset = UNSET
    reservation_id: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        blocked_slot_id = self.blocked_slot_id

        date: str | Unset = UNSET
        if not isinstance(self.date, Unset):
            date = self.date.isoformat()

        start = self.start

        end_date: str | Unset = UNSET
        if not isinstance(self.end_date, Unset):
            end_date = self.end_date.isoformat()

        end = self.end

        activity_id: int | None | Unset
        if isinstance(self.activity_id, Unset):
            activity_id = UNSET
        else:
            activity_id = self.activity_id

        activity_code: None | str | Unset
        if isinstance(self.activity_code, Unset):
            activity_code = UNSET
        else:
            activity_code = self.activity_code

        master_slot_id: int | None | Unset
        if isinstance(self.master_slot_id, Unset):
            master_slot_id = UNSET
        else:
            master_slot_id = self.master_slot_id

        reservation_id: int | None | Unset
        if isinstance(self.reservation_id, Unset):
            reservation_id = UNSET
        else:
            reservation_id = self.reservation_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "blocked_slot_id": blocked_slot_id,
            }
        )
        if date is not UNSET:
            field_dict["date"] = date
        if start is not UNSET:
            field_dict["start"] = start
        if end_date is not UNSET:
            field_dict["end_date"] = end_date
        if end is not UNSET:
            field_dict["end"] = end
        if activity_id is not UNSET:
            field_dict["activity_id"] = activity_id
        if activity_code is not UNSET:
            field_dict["activity_code"] = activity_code
        if master_slot_id is not UNSET:
            field_dict["master_slot_id"] = master_slot_id
        if reservation_id is not UNSET:
            field_dict["reservation_id"] = reservation_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        blocked_slot_id = d.pop("blocked_slot_id")

        _date = d.pop("date", UNSET)
        date: datetime.date | Unset
        if isinstance(_date, Unset):
            date = UNSET
        else:
            date = datetime.date.fromisoformat(_date)

        start = d.pop("start", UNSET)

        _end_date = d.pop("end_date", UNSET)
        end_date: datetime.date | Unset
        if isinstance(_end_date, Unset):
            end_date = UNSET
        else:
            end_date = datetime.date.fromisoformat(_end_date)

        end = d.pop("end", UNSET)

        def _parse_activity_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        activity_id = _parse_activity_id(d.pop("activity_id", UNSET))

        def _parse_activity_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        activity_code = _parse_activity_code(d.pop("activity_code", UNSET))

        def _parse_master_slot_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        master_slot_id = _parse_master_slot_id(d.pop("master_slot_id", UNSET))

        def _parse_reservation_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        reservation_id = _parse_reservation_id(d.pop("reservation_id", UNSET))

        cycle_activation_conflict_detail_conflicts_item = cls(
            blocked_slot_id=blocked_slot_id,
            date=date,
            start=start,
            end_date=end_date,
            end=end,
            activity_id=activity_id,
            activity_code=activity_code,
            master_slot_id=master_slot_id,
            reservation_id=reservation_id,
        )

        cycle_activation_conflict_detail_conflicts_item.additional_properties = d
        return cycle_activation_conflict_detail_conflicts_item

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
