from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ResourceClassResponse")


@_attrs_define
class ResourceClassResponse:
    """
    Attributes:
        id (int):
        code (str): The stable identifier. Uppercase, unique in the organization, never changed. Example: ROOM.
        name (str): What is shown. Free to change. Example: Room.
        active (bool): Whether a new resource or requirement may name the class. Switching it off leaves the ones that
            already do as they are.
        seeded (bool): True for `ROOM` and `PERSON`, which every organization has and which can be renamed but not
            removed or switched off. They are also where the engine's older behaviour is anchored: an import files rooms
            under `ROOM`. Any other class carries no behaviour, it is a label that resources are filed under and
            requirements can ask for.
        created_at (datetime.datetime):
    """

    id: int
    code: str
    name: str
    active: bool
    seeded: bool
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        code = self.code

        name = self.name

        active = self.active

        seeded = self.seeded

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "code": code,
                "name": name,
                "active": active,
                "seeded": seeded,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        code = d.pop("code")

        name = d.pop("name")

        active = d.pop("active")

        seeded = d.pop("seeded")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        resource_class_response = cls(
            id=id,
            code=code,
            name=name,
            active=active,
            seeded=seeded,
            created_at=created_at,
        )

        resource_class_response.additional_properties = d
        return resource_class_response

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
