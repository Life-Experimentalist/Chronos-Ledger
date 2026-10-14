from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.not_removed_slot import NotRemovedSlot


T = TypeVar("T", bound="ImportNotRemoved")


@_attrs_define
class ImportNotRemoved:
    """What an upload with `remove_missing` set listed for removal and left in place. Empty when the option is off.

    Attributes:
        slots (list[NotRemovedSlot]):
    """

    slots: list[NotRemovedSlot]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        slots = []
        for slots_item_data in self.slots:
            slots_item = slots_item_data.to_dict()
            slots.append(slots_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "slots": slots,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.not_removed_slot import NotRemovedSlot  # noqa: PLC0415

        d = dict(src_dict)
        slots = []
        _slots = d.pop("slots")
        for slots_item_data in _slots:
            slots_item = NotRemovedSlot.from_dict(slots_item_data)

            slots.append(slots_item)

        import_not_removed = cls(
            slots=slots,
        )

        import_not_removed.additional_properties = d
        return import_not_removed

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
