from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.conflict import Conflict


T = TypeVar("T", bound="ConflictReport")


@_attrs_define
class ConflictReport:
    """
    Attributes:
        from_ (datetime.date):
        to (datetime.date):
        conflicts (list[Conflict]): Every clash that reaches into the range, each pair named once. Ordered by kind, then
            resource_id or member_id, then the moment the shared window starts. Times are naive wall clock in the
            organization's own timezone.
    """

    from_: datetime.date
    to: datetime.date
    conflicts: list[Conflict]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from_ = self.from_.isoformat()

        to = self.to.isoformat()

        conflicts = []
        for conflicts_item_data in self.conflicts:
            conflicts_item = conflicts_item_data.to_dict()
            conflicts.append(conflicts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "from": from_,
                "to": to,
                "conflicts": conflicts,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.conflict import Conflict  # noqa: PLC0415

        d = dict(src_dict)
        from_ = datetime.date.fromisoformat(d.pop("from"))

        to = datetime.date.fromisoformat(d.pop("to"))

        conflicts = []
        _conflicts = d.pop("conflicts")
        for conflicts_item_data in _conflicts:
            conflicts_item = Conflict.from_dict(conflicts_item_data)

            conflicts.append(conflicts_item)

        conflict_report = cls(
            from_=from_,
            to=to,
            conflicts=conflicts,
        )

        conflict_report.additional_properties = d
        return conflict_report

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
