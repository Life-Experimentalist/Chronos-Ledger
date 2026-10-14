from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.dynamic_state import DynamicState
from ..models.execution_mode import ExecutionMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="DailyLedgerUpdate")


@_attrs_define
class DailyLedgerUpdate:
    """A field left out keeps its value and a null clears it, except operational_state and delivery_format, which cannot be
    null (422).

        Attributes:
            operational_state (DynamicState | Unset): Operational state of a daily ledger entry.
            substitute_lead_id (None | str | Unset):
            delivery_format (ExecutionMode | Unset): Class delivery format.
            virtual_connection_string (None | str | Unset):  Example: https://meet.google.com/xyz-abc.
            latitude_target (float | None | Unset):
            longitude_target (float | None | Unset):
            altitude_target (float | None | Unset):
            precision_radius_meters (int | None | Unset): Geofence radius override for this specific session.
    """

    operational_state: DynamicState | Unset = UNSET
    substitute_lead_id: None | str | Unset = UNSET
    delivery_format: ExecutionMode | Unset = UNSET
    virtual_connection_string: None | str | Unset = UNSET
    latitude_target: float | None | Unset = UNSET
    longitude_target: float | None | Unset = UNSET
    altitude_target: float | None | Unset = UNSET
    precision_radius_meters: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        operational_state: str | Unset = UNSET
        if not isinstance(self.operational_state, Unset):
            operational_state = self.operational_state.value

        substitute_lead_id: None | str | Unset
        if isinstance(self.substitute_lead_id, Unset):
            substitute_lead_id = UNSET
        else:
            substitute_lead_id = self.substitute_lead_id

        delivery_format: str | Unset = UNSET
        if not isinstance(self.delivery_format, Unset):
            delivery_format = self.delivery_format.value

        virtual_connection_string: None | str | Unset
        if isinstance(self.virtual_connection_string, Unset):
            virtual_connection_string = UNSET
        else:
            virtual_connection_string = self.virtual_connection_string

        latitude_target: float | None | Unset
        if isinstance(self.latitude_target, Unset):
            latitude_target = UNSET
        else:
            latitude_target = self.latitude_target

        longitude_target: float | None | Unset
        if isinstance(self.longitude_target, Unset):
            longitude_target = UNSET
        else:
            longitude_target = self.longitude_target

        altitude_target: float | None | Unset
        if isinstance(self.altitude_target, Unset):
            altitude_target = UNSET
        else:
            altitude_target = self.altitude_target

        precision_radius_meters: int | None | Unset
        if isinstance(self.precision_radius_meters, Unset):
            precision_radius_meters = UNSET
        else:
            precision_radius_meters = self.precision_radius_meters

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if operational_state is not UNSET:
            field_dict["operational_state"] = operational_state
        if substitute_lead_id is not UNSET:
            field_dict["substitute_lead_id"] = substitute_lead_id
        if delivery_format is not UNSET:
            field_dict["delivery_format"] = delivery_format
        if virtual_connection_string is not UNSET:
            field_dict["virtual_connection_string"] = virtual_connection_string
        if latitude_target is not UNSET:
            field_dict["latitude_target"] = latitude_target
        if longitude_target is not UNSET:
            field_dict["longitude_target"] = longitude_target
        if altitude_target is not UNSET:
            field_dict["altitude_target"] = altitude_target
        if precision_radius_meters is not UNSET:
            field_dict["precision_radius_meters"] = precision_radius_meters

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _operational_state = d.pop("operational_state", UNSET)
        operational_state: DynamicState | Unset
        if isinstance(_operational_state, Unset):
            operational_state = UNSET
        else:
            operational_state = DynamicState(_operational_state)

        def _parse_substitute_lead_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        substitute_lead_id = _parse_substitute_lead_id(d.pop("substitute_lead_id", UNSET))

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

        def _parse_latitude_target(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        latitude_target = _parse_latitude_target(d.pop("latitude_target", UNSET))

        def _parse_longitude_target(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        longitude_target = _parse_longitude_target(d.pop("longitude_target", UNSET))

        def _parse_altitude_target(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        altitude_target = _parse_altitude_target(d.pop("altitude_target", UNSET))

        def _parse_precision_radius_meters(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        precision_radius_meters = _parse_precision_radius_meters(d.pop("precision_radius_meters", UNSET))

        daily_ledger_update = cls(
            operational_state=operational_state,
            substitute_lead_id=substitute_lead_id,
            delivery_format=delivery_format,
            virtual_connection_string=virtual_connection_string,
            latitude_target=latitude_target,
            longitude_target=longitude_target,
            altitude_target=altitude_target,
            precision_radius_meters=precision_radius_meters,
        )

        daily_ledger_update.additional_properties = d
        return daily_ledger_update

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
