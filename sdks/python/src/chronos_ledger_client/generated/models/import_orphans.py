from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.orphan_enrollment import OrphanEnrollment
    from ..models.orphan_slot import OrphanSlot


T = TypeVar("T", bound="ImportOrphans")


@_attrs_define
class ImportOrphans:
    """What the cycle holds that this file did not mention. A report and never an action: a file covering half a timetable
    cannot be told apart from a timetable that lost half its classes, so nothing here is removed and somebody decides.

    Scoped to the units named in the file, not to the whole cycle, so a file covering one unit does not report every
    class in every other unit each time it is uploaded.

        Attributes:
            slots (list[OrphanSlot]):
            enrollments (list[OrphanEnrollment]):
    """

    slots: list[OrphanSlot]
    enrollments: list[OrphanEnrollment]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        slots = []
        for slots_item_data in self.slots:
            slots_item = slots_item_data.to_dict()
            slots.append(slots_item)

        enrollments = []
        for enrollments_item_data in self.enrollments:
            enrollments_item = enrollments_item_data.to_dict()
            enrollments.append(enrollments_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "slots": slots,
                "enrollments": enrollments,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.orphan_enrollment import OrphanEnrollment  # noqa: PLC0415
        from ..models.orphan_slot import OrphanSlot  # noqa: PLC0415

        d = dict(src_dict)
        slots = []
        _slots = d.pop("slots")
        for slots_item_data in _slots:
            slots_item = OrphanSlot.from_dict(slots_item_data)

            slots.append(slots_item)

        enrollments = []
        _enrollments = d.pop("enrollments")
        for enrollments_item_data in _enrollments:
            enrollments_item = OrphanEnrollment.from_dict(enrollments_item_data)

            enrollments.append(enrollments_item)

        import_orphans = cls(
            slots=slots,
            enrollments=enrollments,
        )

        import_orphans.additional_properties = d
        return import_orphans

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
