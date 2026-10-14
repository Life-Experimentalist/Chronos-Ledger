from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.reservation_response import ReservationResponse


T = TypeVar("T", bound="BookingsWouldNotFitDetail")


@_attrs_define
class BookingsWouldNotFitDetail:
    """
    Attributes:
        message (str):  Example: bookings still to come would not fit the resource after that change.
        reservations (list[ReservationResponse]):
    """

    message: str
    reservations: list[ReservationResponse]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        message = self.message

        reservations = []
        for reservations_item_data in self.reservations:
            reservations_item = reservations_item_data.to_dict()
            reservations.append(reservations_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "message": message,
                "reservations": reservations,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reservation_response import ReservationResponse  # noqa: PLC0415

        d = dict(src_dict)
        message = d.pop("message")

        reservations = []
        _reservations = d.pop("reservations")
        for reservations_item_data in _reservations:
            reservations_item = ReservationResponse.from_dict(reservations_item_data)

            reservations.append(reservations_item)

        bookings_would_not_fit_detail = cls(
            message=message,
            reservations=reservations,
        )

        bookings_would_not_fit_detail.additional_properties = d
        return bookings_would_not_fit_detail

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
