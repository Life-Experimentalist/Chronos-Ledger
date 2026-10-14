from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.slot_requirement_gap import SlotRequirementGap


T = TypeVar("T", bound="ScheduleCreateSlotResponse200")


@_attrs_define
class ScheduleCreateSlotResponse200:
    """
    Attributes:
        id (int | Unset):
        requirements_unmet (list[SlotRequirementGap] | Unset):
    """

    id: int | Unset = UNSET
    requirements_unmet: list[SlotRequirementGap] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        requirements_unmet: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.requirements_unmet, Unset):
            requirements_unmet = []
            for requirements_unmet_item_data in self.requirements_unmet:
                requirements_unmet_item = requirements_unmet_item_data.to_dict()
                requirements_unmet.append(requirements_unmet_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if requirements_unmet is not UNSET:
            field_dict["requirements_unmet"] = requirements_unmet

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.slot_requirement_gap import SlotRequirementGap  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        _requirements_unmet = d.pop("requirements_unmet", UNSET)
        requirements_unmet: list[SlotRequirementGap] | Unset = UNSET
        if _requirements_unmet is not UNSET:
            requirements_unmet = []
            for requirements_unmet_item_data in _requirements_unmet:
                requirements_unmet_item = SlotRequirementGap.from_dict(requirements_unmet_item_data)

                requirements_unmet.append(requirements_unmet_item)

        schedule_create_slot_response_200 = cls(
            id=id,
            requirements_unmet=requirements_unmet,
        )

        schedule_create_slot_response_200.additional_properties = d
        return schedule_create_slot_response_200

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
