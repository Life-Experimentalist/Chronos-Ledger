from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ReservationUpdate")


@_attrs_define
class ReservationUpdate:
    """What the caller may change about a reservation it already holds: its reference, for now. The window is what the
    conflict check and the idempotency fingerprint are built on, so moving it is a cancel and a new booking. Any other
    field is refused with a 422 rather than ignored.

        Attributes:
            external_ref (None | str | Unset): The new reference, or null to clear it. Leaving the field out leaves the
                reference as it is.
                 Example: visit-43.
    """

    external_ref: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        external_ref: None | str | Unset
        if isinstance(self.external_ref, Unset):
            external_ref = UNSET
        else:
            external_ref = self.external_ref

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if external_ref is not UNSET:
            field_dict["external_ref"] = external_ref

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_external_ref(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        external_ref = _parse_external_ref(d.pop("external_ref", UNSET))

        reservation_update = cls(
            external_ref=external_ref,
        )

        return reservation_update
