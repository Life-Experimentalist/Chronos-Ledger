from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.config_get_response_200_labels import ConfigGetResponse200Labels


T = TypeVar("T", bound="ConfigGetResponse200")


@_attrs_define
class ConfigGetResponse200:
    """
    Attributes:
        labels (ConfigGetResponse200Labels | Unset):
        password_min_length (int | Unset): PASSWORD_MIN_LENGTH on this deployment. The onboarding wizard states it in a
            placeholder and refuses a shorter password before sending it. Example: 12.
        version (str | Unset): The API version, the same string GET /health reports. It is here so a client that pins a
            version can read it without leaving the /api/v1 prefix it builds its URLs from. The database revision stays on
            /health. Example: 0.14.0.
    """

    labels: ConfigGetResponse200Labels | Unset = UNSET
    password_min_length: int | Unset = UNSET
    version: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        labels: dict[str, Any] | Unset = UNSET
        if not isinstance(self.labels, Unset):
            labels = self.labels.to_dict()

        password_min_length = self.password_min_length

        version = self.version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if labels is not UNSET:
            field_dict["labels"] = labels
        if password_min_length is not UNSET:
            field_dict["password_min_length"] = password_min_length
        if version is not UNSET:
            field_dict["version"] = version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.config_get_response_200_labels import ConfigGetResponse200Labels  # noqa: PLC0415

        d = dict(src_dict)
        _labels = d.pop("labels", UNSET)
        labels: ConfigGetResponse200Labels | Unset
        if isinstance(_labels, Unset):
            labels = UNSET
        else:
            labels = ConfigGetResponse200Labels.from_dict(_labels)

        password_min_length = d.pop("password_min_length", UNSET)

        version = d.pop("version", UNSET)

        config_get_response_200 = cls(
            labels=labels,
            password_min_length=password_min_length,
            version=version,
        )

        config_get_response_200.additional_properties = d
        return config_get_response_200

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
