from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.busy_interval import BusyInterval


T = TypeVar("T", bound="CapacityExceededDetail")


@_attrs_define
class CapacityExceededDetail:
    """
    Attributes:
        message (str):  Example: the resource does not have that many units left for that window.
        conflicts (list[BusyInterval]):
        capacity (int):  Example: 12.
        taken (int):  Example: 12.
        requested (int):  Example: 1.
    """

    message: str
    conflicts: list[BusyInterval]
    capacity: int
    taken: int
    requested: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        message = self.message

        conflicts = []
        for conflicts_item_data in self.conflicts:
            conflicts_item = conflicts_item_data.to_dict()
            conflicts.append(conflicts_item)

        capacity = self.capacity

        taken = self.taken

        requested = self.requested

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "message": message,
                "conflicts": conflicts,
                "capacity": capacity,
                "taken": taken,
                "requested": requested,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.busy_interval import BusyInterval  # noqa: PLC0415

        d = dict(src_dict)
        message = d.pop("message")

        conflicts = []
        _conflicts = d.pop("conflicts")
        for conflicts_item_data in _conflicts:
            conflicts_item = BusyInterval.from_dict(conflicts_item_data)

            conflicts.append(conflicts_item)

        capacity = d.pop("capacity")

        taken = d.pop("taken")

        requested = d.pop("requested")

        capacity_exceeded_detail = cls(
            message=message,
            conflicts=conflicts,
            capacity=capacity,
            taken=taken,
            requested=requested,
        )

        capacity_exceeded_detail.additional_properties = d
        return capacity_exceeded_detail

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
