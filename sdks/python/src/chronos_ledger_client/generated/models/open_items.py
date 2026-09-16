from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OpenItems")


@_attrs_define
class OpenItems:
    """What still names a deactivated account. Deactivating changes none of it and is never refused because of it; calling
    deactivate again counts afresh.

        Attributes:
            pending_absence_requests (int): Absence requests sent to the account that nobody has decided. An admin decides
                them from `GET /attendance/absence/pending`.
            direct_reports (int): Active accounts that name it as their manager.
            slots_led (int): Slots it leads in a cycle that has not ended, drafts included.
            ledger_rows_ahead (int): Ledger rows dated today or later that it leads or covers.
    """

    pending_absence_requests: int
    direct_reports: int
    slots_led: int
    ledger_rows_ahead: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pending_absence_requests = self.pending_absence_requests

        direct_reports = self.direct_reports

        slots_led = self.slots_led

        ledger_rows_ahead = self.ledger_rows_ahead

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "pending_absence_requests": pending_absence_requests,
                "direct_reports": direct_reports,
                "slots_led": slots_led,
                "ledger_rows_ahead": ledger_rows_ahead,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        pending_absence_requests = d.pop("pending_absence_requests")

        direct_reports = d.pop("direct_reports")

        slots_led = d.pop("slots_led")

        ledger_rows_ahead = d.pop("ledger_rows_ahead")

        open_items = cls(
            pending_absence_requests=pending_absence_requests,
            direct_reports=direct_reports,
            slots_led=slots_led,
            ledger_rows_ahead=ledger_rows_ahead,
        )

        open_items.additional_properties = d
        return open_items

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
