from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.dynamic_state import DynamicState
from ..models.execution_mode import ExecutionMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="DailyLedgerResponse")


@_attrs_define
class DailyLedgerResponse:
    """
    Attributes:
        id (int | Unset):
        target_date (datetime.date | Unset):
        activity_id (int | Unset):
        active_lead_id (None | str | Unset):
        substitute_lead_id (None | str | Unset):
        resource_id (int | None | Unset): The room this is booked in. Prefer this over target_room_identifier.
        target_room_identifier (None | str | Unset): The room's name, mirrored from the resource. Being retired.
        delivery_format (ExecutionMode | Unset): Class delivery format.
        virtual_connection_string (None | str | Unset):
        operational_state (DynamicState | Unset): Operational state of a daily ledger entry.
        activity_code (None | str | Unset):
        activity_title (None | str | Unset):
        time_window_start (None | str | Unset): The day's own window, copied off the slot when the day was generated
            rather than read back through it. Editing a slot moves the days it has still to run and leaves the ones that
            already happened saying the hour they happened at; deleting a slot leaves them saying it too. Null on an ad-hoc
            day, which never claimed an hour, and on a day generated before the ledger carried a window.
        time_window_end (None | str | Unset): Earlier than time_window_start means the day finishes on the date after
            target_date. A reader that ignores that computes minus sixteen hours for a night shift running 22:00 to 06:00.
    """

    id: int | Unset = UNSET
    target_date: datetime.date | Unset = UNSET
    activity_id: int | Unset = UNSET
    active_lead_id: None | str | Unset = UNSET
    substitute_lead_id: None | str | Unset = UNSET
    resource_id: int | None | Unset = UNSET
    target_room_identifier: None | str | Unset = UNSET
    delivery_format: ExecutionMode | Unset = UNSET
    virtual_connection_string: None | str | Unset = UNSET
    operational_state: DynamicState | Unset = UNSET
    activity_code: None | str | Unset = UNSET
    activity_title: None | str | Unset = UNSET
    time_window_start: None | str | Unset = UNSET
    time_window_end: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        target_date: str | Unset = UNSET
        if not isinstance(self.target_date, Unset):
            target_date = self.target_date.isoformat()

        activity_id = self.activity_id

        active_lead_id: None | str | Unset
        if isinstance(self.active_lead_id, Unset):
            active_lead_id = UNSET
        else:
            active_lead_id = self.active_lead_id

        substitute_lead_id: None | str | Unset
        if isinstance(self.substitute_lead_id, Unset):
            substitute_lead_id = UNSET
        else:
            substitute_lead_id = self.substitute_lead_id

        resource_id: int | None | Unset
        if isinstance(self.resource_id, Unset):
            resource_id = UNSET
        else:
            resource_id = self.resource_id

        target_room_identifier: None | str | Unset
        if isinstance(self.target_room_identifier, Unset):
            target_room_identifier = UNSET
        else:
            target_room_identifier = self.target_room_identifier

        delivery_format: str | Unset = UNSET
        if not isinstance(self.delivery_format, Unset):
            delivery_format = self.delivery_format.value

        virtual_connection_string: None | str | Unset
        if isinstance(self.virtual_connection_string, Unset):
            virtual_connection_string = UNSET
        else:
            virtual_connection_string = self.virtual_connection_string

        operational_state: str | Unset = UNSET
        if not isinstance(self.operational_state, Unset):
            operational_state = self.operational_state.value

        activity_code: None | str | Unset
        if isinstance(self.activity_code, Unset):
            activity_code = UNSET
        else:
            activity_code = self.activity_code

        activity_title: None | str | Unset
        if isinstance(self.activity_title, Unset):
            activity_title = UNSET
        else:
            activity_title = self.activity_title

        time_window_start: None | str | Unset
        if isinstance(self.time_window_start, Unset):
            time_window_start = UNSET
        else:
            time_window_start = self.time_window_start

        time_window_end: None | str | Unset
        if isinstance(self.time_window_end, Unset):
            time_window_end = UNSET
        else:
            time_window_end = self.time_window_end

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if target_date is not UNSET:
            field_dict["target_date"] = target_date
        if activity_id is not UNSET:
            field_dict["activity_id"] = activity_id
        if active_lead_id is not UNSET:
            field_dict["active_lead_id"] = active_lead_id
        if substitute_lead_id is not UNSET:
            field_dict["substitute_lead_id"] = substitute_lead_id
        if resource_id is not UNSET:
            field_dict["resource_id"] = resource_id
        if target_room_identifier is not UNSET:
            field_dict["target_room_identifier"] = target_room_identifier
        if delivery_format is not UNSET:
            field_dict["delivery_format"] = delivery_format
        if virtual_connection_string is not UNSET:
            field_dict["virtual_connection_string"] = virtual_connection_string
        if operational_state is not UNSET:
            field_dict["operational_state"] = operational_state
        if activity_code is not UNSET:
            field_dict["activity_code"] = activity_code
        if activity_title is not UNSET:
            field_dict["activity_title"] = activity_title
        if time_window_start is not UNSET:
            field_dict["time_window_start"] = time_window_start
        if time_window_end is not UNSET:
            field_dict["time_window_end"] = time_window_end

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        _target_date = d.pop("target_date", UNSET)
        target_date: datetime.date | Unset
        if isinstance(_target_date, Unset):
            target_date = UNSET
        else:
            target_date = datetime.date.fromisoformat(_target_date)

        activity_id = d.pop("activity_id", UNSET)

        def _parse_active_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        active_lead_id = _parse_active_lead_id(d.pop("active_lead_id", UNSET))

        def _parse_substitute_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        substitute_lead_id = _parse_substitute_lead_id(
            d.pop("substitute_lead_id", UNSET)
        )

        def _parse_resource_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        resource_id = _parse_resource_id(d.pop("resource_id", UNSET))

        def _parse_target_room_identifier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        target_room_identifier = _parse_target_room_identifier(
            d.pop("target_room_identifier", UNSET)
        )

        _delivery_format = d.pop("delivery_format", UNSET)
        delivery_format: ExecutionMode | Unset
        if isinstance(_delivery_format, Unset):
            delivery_format = UNSET
        else:
            delivery_format = ExecutionMode(_delivery_format)

        def _parse_virtual_connection_string(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        virtual_connection_string = _parse_virtual_connection_string(
            d.pop("virtual_connection_string", UNSET)
        )

        _operational_state = d.pop("operational_state", UNSET)
        operational_state: DynamicState | Unset
        if isinstance(_operational_state, Unset):
            operational_state = UNSET
        else:
            operational_state = DynamicState(_operational_state)

        def _parse_activity_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        activity_code = _parse_activity_code(d.pop("activity_code", UNSET))

        def _parse_activity_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        activity_title = _parse_activity_title(d.pop("activity_title", UNSET))

        def _parse_time_window_start(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        time_window_start = _parse_time_window_start(d.pop("time_window_start", UNSET))

        def _parse_time_window_end(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        time_window_end = _parse_time_window_end(d.pop("time_window_end", UNSET))

        daily_ledger_response = cls(
            id=id,
            target_date=target_date,
            activity_id=activity_id,
            active_lead_id=active_lead_id,
            substitute_lead_id=substitute_lead_id,
            resource_id=resource_id,
            target_room_identifier=target_room_identifier,
            delivery_format=delivery_format,
            virtual_connection_string=virtual_connection_string,
            operational_state=operational_state,
            activity_code=activity_code,
            activity_title=activity_title,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
        )

        daily_ledger_response.additional_properties = d
        return daily_ledger_response

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
