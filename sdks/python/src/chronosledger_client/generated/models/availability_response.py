from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.busy_interval import BusyInterval
    from ..models.unmet_requirement import UnmetRequirement


T = TypeVar("T", bound="AvailabilityResponse")


@_attrs_define
class AvailabilityResponse:
    """
    Attributes:
        resource_id (int | Unset):
        code (str | Unset):
        from_ (datetime.date | Unset):
        to (datetime.date | Unset):
        busy (list[BusyInterval] | Unset): Busy intervals, not free ones. Times are naive wall clock in the
            organization's own timezone, with no offset and no Z.
        requirements_met (bool | None | Unset): Null unless `with_requirements` was asked for. Then true when the
            resource itself is free for the window and nothing it requires is missing, whatever the enforcement.
        unmet (list[UnmetRequirement] | Unset): Empty unless `with_requirements` was asked for. Then the requirements
            that could not be held for the window.
    """

    resource_id: int | Unset = UNSET
    code: str | Unset = UNSET
    from_: datetime.date | Unset = UNSET
    to: datetime.date | Unset = UNSET
    busy: list[BusyInterval] | Unset = UNSET
    requirements_met: bool | None | Unset = UNSET
    unmet: list[UnmetRequirement] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        resource_id = self.resource_id

        code = self.code

        from_: str | Unset = UNSET
        if not isinstance(self.from_, Unset):
            from_ = self.from_.isoformat()

        to: str | Unset = UNSET
        if not isinstance(self.to, Unset):
            to = self.to.isoformat()

        busy: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.busy, Unset):
            busy = []
            for busy_item_data in self.busy:
                busy_item = busy_item_data.to_dict()
                busy.append(busy_item)

        requirements_met: bool | None | Unset
        if isinstance(self.requirements_met, Unset):
            requirements_met = UNSET
        else:
            requirements_met = self.requirements_met

        unmet: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.unmet, Unset):
            unmet = []
            for unmet_item_data in self.unmet:
                unmet_item = unmet_item_data.to_dict()
                unmet.append(unmet_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if resource_id is not UNSET:
            field_dict["resource_id"] = resource_id
        if code is not UNSET:
            field_dict["code"] = code
        if from_ is not UNSET:
            field_dict["from"] = from_
        if to is not UNSET:
            field_dict["to"] = to
        if busy is not UNSET:
            field_dict["busy"] = busy
        if requirements_met is not UNSET:
            field_dict["requirements_met"] = requirements_met
        if unmet is not UNSET:
            field_dict["unmet"] = unmet

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.busy_interval import BusyInterval  # noqa: PLC0415
        from ..models.unmet_requirement import UnmetRequirement  # noqa: PLC0415

        d = dict(src_dict)
        resource_id = d.pop("resource_id", UNSET)

        code = d.pop("code", UNSET)

        _from_ = d.pop("from", UNSET)
        from_: datetime.date | Unset
        if isinstance(_from_, Unset):
            from_ = UNSET
        else:
            from_ = datetime.date.fromisoformat(_from_)

        _to = d.pop("to", UNSET)
        to: datetime.date | Unset
        if isinstance(_to, Unset):
            to = UNSET
        else:
            to = datetime.date.fromisoformat(_to)

        _busy = d.pop("busy", UNSET)
        busy: list[BusyInterval] | Unset = UNSET
        if _busy is not UNSET:
            busy = []
            for busy_item_data in _busy:
                busy_item = BusyInterval.from_dict(busy_item_data)

                busy.append(busy_item)

        def _parse_requirements_met(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        requirements_met = _parse_requirements_met(d.pop("requirements_met", UNSET))

        _unmet = d.pop("unmet", UNSET)
        unmet: list[UnmetRequirement] | Unset = UNSET
        if _unmet is not UNSET:
            unmet = []
            for unmet_item_data in _unmet:
                unmet_item = UnmetRequirement.from_dict(unmet_item_data)

                unmet.append(unmet_item)

        availability_response = cls(
            resource_id=resource_id,
            code=code,
            from_=from_,
            to=to,
            busy=busy,
            requirements_met=requirements_met,
            unmet=unmet,
        )

        availability_response.additional_properties = d
        return availability_response

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
