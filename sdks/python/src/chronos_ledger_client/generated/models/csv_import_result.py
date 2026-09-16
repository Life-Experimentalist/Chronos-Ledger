from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from typing_extensions import Self

from ..models.csv_import_result_status import CsvImportResultStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.import_orphans import ImportOrphans
    from ..models.provisioned_credential import ProvisionedCredential


T = TypeVar("T", bound="CsvImportResult")


@_attrs_define
class CsvImportResult:
    """
    Attributes:
        status (CsvImportResultStatus):
        rows_ingested (int | Unset): Present when status is SUCCESS.
        provisioned_credentials (list[ProvisionedCredential] | Unset): One entry per member this import created, empty
            when the file only touched members who already existed. The single copy of these passwords: save them or reset
            the members individually.
        slots_corrected (int | Unset): Slots this file changed rather than created. Re-uploading a file with a corrected
            room or lead is how a timetable is edited in bulk; a slot whose start time moved does not match and arrives as a
            second slot instead, with the original reported in not_in_file.
        ledger_rows_updated (int | Unset): Days already generated from a corrected slot that were still plans and now
            carry the new lead and room. A day whose room changed also has its geofence cleared, because the old one fenced
            members out of the room they have just been sent to.
        ledger_rows_kept (int | Unset): Days left alone because attendance or a note has been recorded against them.
            They now disagree with the timetable on purpose: they record what happened. Days already past are never touched
            and are not counted here.
        not_in_file (ImportOrphans | Unset): What the cycle holds that this file did not mention. A report and never an
            action: a file covering half a timetable cannot be told apart from a timetable that lost half its classes, so
            nothing here is removed and somebody decides.

            Scoped to the units named in the file, not to the whole cycle, so a file covering one unit does not report every
            class in every other unit each time it is uploaded.
        error_log (str | Unset): Present when status is FAILED.
    """

    status: CsvImportResultStatus
    rows_ingested: int | Unset = UNSET
    provisioned_credentials: list[ProvisionedCredential] | Unset = UNSET
    slots_corrected: int | Unset = UNSET
    ledger_rows_updated: int | Unset = UNSET
    ledger_rows_kept: int | Unset = UNSET
    not_in_file: ImportOrphans | Unset = UNSET
    error_log: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status.value

        rows_ingested = self.rows_ingested

        provisioned_credentials: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.provisioned_credentials, Unset):
            provisioned_credentials = []
            for provisioned_credentials_item_data in self.provisioned_credentials:
                provisioned_credentials_item = (
                    provisioned_credentials_item_data.to_dict()
                )
                provisioned_credentials.append(provisioned_credentials_item)

        slots_corrected = self.slots_corrected

        ledger_rows_updated = self.ledger_rows_updated

        ledger_rows_kept = self.ledger_rows_kept

        not_in_file: dict[str, Any] | Unset = UNSET
        if not isinstance(self.not_in_file, Unset):
            not_in_file = self.not_in_file.to_dict()

        error_log = self.error_log

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "status": status,
            }
        )
        if rows_ingested is not UNSET:
            field_dict["rows_ingested"] = rows_ingested
        if provisioned_credentials is not UNSET:
            field_dict["provisioned_credentials"] = provisioned_credentials
        if slots_corrected is not UNSET:
            field_dict["slots_corrected"] = slots_corrected
        if ledger_rows_updated is not UNSET:
            field_dict["ledger_rows_updated"] = ledger_rows_updated
        if ledger_rows_kept is not UNSET:
            field_dict["ledger_rows_kept"] = ledger_rows_kept
        if not_in_file is not UNSET:
            field_dict["not_in_file"] = not_in_file
        if error_log is not UNSET:
            field_dict["error_log"] = error_log

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.import_orphans import ImportOrphans
        from ..models.provisioned_credential import (
            ProvisionedCredential,
        )

        d = dict(src_dict)
        status = CsvImportResultStatus(d.pop("status"))

        rows_ingested = d.pop("rows_ingested", UNSET)

        _provisioned_credentials = d.pop("provisioned_credentials", UNSET)
        provisioned_credentials: list[ProvisionedCredential] | Unset = UNSET
        if _provisioned_credentials is not UNSET:
            provisioned_credentials = []
            for provisioned_credentials_item_data in _provisioned_credentials:
                provisioned_credentials_item = ProvisionedCredential.from_dict(
                    provisioned_credentials_item_data
                )

                provisioned_credentials.append(provisioned_credentials_item)

        slots_corrected = d.pop("slots_corrected", UNSET)

        ledger_rows_updated = d.pop("ledger_rows_updated", UNSET)

        ledger_rows_kept = d.pop("ledger_rows_kept", UNSET)

        _not_in_file = d.pop("not_in_file", UNSET)
        not_in_file: ImportOrphans | Unset
        if isinstance(_not_in_file, Unset):
            not_in_file = UNSET
        else:
            not_in_file = ImportOrphans.from_dict(_not_in_file)

        error_log = d.pop("error_log", UNSET)

        csv_import_result = cls(
            status=status,
            rows_ingested=rows_ingested,
            provisioned_credentials=provisioned_credentials,
            slots_corrected=slots_corrected,
            ledger_rows_updated=ledger_rows_updated,
            ledger_rows_kept=ledger_rows_kept,
            not_in_file=not_in_file,
            error_log=error_log,
        )

        csv_import_result.additional_properties = d
        return csv_import_result

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
