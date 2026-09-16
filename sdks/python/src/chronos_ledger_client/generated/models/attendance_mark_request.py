from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.verification_metric import VerificationMetric
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttendanceMarkRequest")


@_attrs_define
class AttendanceMarkRequest:
    """
    Attributes:
        ledger_instance_id (int):  Example: 1042.
        member_id (str):  Example: STU20210001.
        marking_status (VerificationMetric): Attendance marking status for a member.
        user_lat (float | None | Unset):  Example: 12.971598.
        user_lon (float | None | Unset):  Example: 77.594562.
        user_alt (float | None | Unset): Altitude in meters. Optional. The floor check runs only when the client
            supplies an altitude it can vouch for, and is skipped otherwise; a geo-fenced session requires lat/lon alone.
            Example: 920.5.
        user_accuracy (float | None | Unset): How far off the fix may be, in meters, as the device reports it
            (coords.accuracy in a browser). Optional. On a geo-fenced session a fix coarser than GEOFENCE_ACCURACY_FACTOR
            times precision_radius_meters (30 m on the default 15 m radius) returns 400. Example: 8.0.
    """

    ledger_instance_id: int
    member_id: str
    marking_status: VerificationMetric
    user_lat: float | None | Unset = UNSET
    user_lon: float | None | Unset = UNSET
    user_alt: float | None | Unset = UNSET
    user_accuracy: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ledger_instance_id = self.ledger_instance_id

        member_id = self.member_id

        marking_status = self.marking_status.value

        user_lat: float | None | Unset
        if isinstance(self.user_lat, Unset):
            user_lat = UNSET
        else:
            user_lat = self.user_lat

        user_lon: float | None | Unset
        if isinstance(self.user_lon, Unset):
            user_lon = UNSET
        else:
            user_lon = self.user_lon

        user_alt: float | None | Unset
        if isinstance(self.user_alt, Unset):
            user_alt = UNSET
        else:
            user_alt = self.user_alt

        user_accuracy: float | None | Unset
        if isinstance(self.user_accuracy, Unset):
            user_accuracy = UNSET
        else:
            user_accuracy = self.user_accuracy

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ledger_instance_id": ledger_instance_id,
                "member_id": member_id,
                "marking_status": marking_status,
            }
        )
        if user_lat is not UNSET:
            field_dict["user_lat"] = user_lat
        if user_lon is not UNSET:
            field_dict["user_lon"] = user_lon
        if user_alt is not UNSET:
            field_dict["user_alt"] = user_alt
        if user_accuracy is not UNSET:
            field_dict["user_accuracy"] = user_accuracy

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ledger_instance_id = d.pop("ledger_instance_id")

        member_id = d.pop("member_id")

        marking_status = VerificationMetric(d.pop("marking_status"))

        def _parse_user_lat(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        user_lat = _parse_user_lat(d.pop("user_lat", UNSET))

        def _parse_user_lon(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        user_lon = _parse_user_lon(d.pop("user_lon", UNSET))

        def _parse_user_alt(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        user_alt = _parse_user_alt(d.pop("user_alt", UNSET))

        def _parse_user_accuracy(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        user_accuracy = _parse_user_accuracy(d.pop("user_accuracy", UNSET))

        attendance_mark_request = cls(
            ledger_instance_id=ledger_instance_id,
            member_id=member_id,
            marking_status=marking_status,
            user_lat=user_lat,
            user_lon=user_lon,
            user_alt=user_alt,
            user_accuracy=user_accuracy,
        )

        attendance_mark_request.additional_properties = d
        return attendance_mark_request

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
