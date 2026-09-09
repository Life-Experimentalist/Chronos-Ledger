# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.security import generate_password, hash_password
from app.models.db import (
    Activity,
    ActivityEnrollment,
    InstitutionalRole,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from app.services.availability import held_against_slot
from app.services.master_slot import propagate_slot_corrections
from app.services.resource import get_or_create_room

REQUIRED_COLUMNS = {
    "member_id",
    "member_name",
    "member_email",
    "activity_code",
    "activity_title",
    "unit",
    "day_of_week_index",
    "time_window_start",
    "time_window_end",
    "lead_id",
    "room",
}


def _parse_time(raw: str) -> datetime.time:
    """Parse HH:MM or HH:MM:SS strings into datetime.time for SQLAlchemy Time columns."""
    raw = str(raw).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time value '{raw}', expected HH:MM or HH:MM:SS")


class ChronosIngestionEngine:
    def __init__(self, db: Session):
        self.db = db

    def process_member_centric_matrix(self, file_path: str, cycle_id: int) -> dict[str, Any]:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return {"status": "FAILED", "error_log": f"CSV parse error: {e}"}

        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            return {"status": "FAILED", "error_log": f"Missing columns: {missing}"}

        records_processed = 0
        # Raw passwords for the members this import creates. Handed back once,
        # in the upload response, for the admin to distribute. Never stored and
        # never logged: the database keeps only the bcrypt hash, as it does for
        # every other account.
        provisioned: list[dict[str, str]] = []
        # Slots this file actually changed, collected so the days already
        # generated from them are brought into line once at the end rather
        # than once per CSV row.
        corrected: dict[int, StructuralMasterSlot] = {}
        # What the file accounted for, gathered as the loop matches each row,
        # so the orphan report below is computed from the same match the
        # import itself made. A second key written separately would drift
        # from this one and the report would start naming rows the file did
        # in fact cover.
        seen_slots: set[int] = set()
        seen_enrollments: set[tuple[int, str]] = set()
        units: set[str] = set()
        # A slot only occupies its room while its cycle is open, so an upload
        # into a closed cycle is checked against nothing, the same way a
        # booking is not blocked by a closed cycle's slot.
        cycle = self.db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first()
        cycle_is_open = bool(cycle and cycle.operational_status)

        try:
            for _, row in df.iterrows():
                # 1. Upsert member user
                member = self.db.query(User).filter(User.id == str(row["member_id"])).first()
                if not member:
                    # One password per member. The shared constant this replaces
                    # meant a single leaked credential opened every account the
                    # import had ever created, across every unit.
                    raw_password = generate_password()
                    member = User(
                        id=str(row["member_id"]),
                        full_name=str(row["member_name"]),
                        email_address=str(row["member_email"]),
                        credential_secure_hash=hash_password(raw_password),
                        role_type=InstitutionalRole.MEMBER,
                        unit_code=str(row["unit"]),
                    )
                    self.db.add(member)
                    provisioned.append(
                        {
                            "member_id": str(row["member_id"]),
                            "email_address": str(row["member_email"]),
                            "initial_password": raw_password,
                        }
                    )
                else:
                    member.full_name = str(row["member_name"])
                    member.unit_code = str(row["unit"])
                    if member.email_address != str(row["member_email"]):
                        # email_address is unique. Letting the collision reach
                        # the database turns a fixable typo into a rolled-back
                        # import explained by a raw driver error.
                        clash = (
                            self.db.query(User)
                            .filter(
                                User.email_address == str(row["member_email"]),
                                User.id != member.id,
                            )
                            .first()
                        )
                        if clash:
                            raise ValueError(
                                f"member '{row['member_id']}': email "
                                f"{row['member_email']} already belongs to '{clash.id}'"
                            )
                        member.email_address = str(row["member_email"])
                    # role_type is deliberately not touched. Somebody promoted
                    # to STAFF since the last import stays STAFF.

                # 2. Upsert activity offering
                offering = (
                    self.db.query(Activity)
                    .filter(
                        Activity.activity_code == str(row["activity_code"]),
                        Activity.cycle_id == cycle_id,
                    )
                    .first()
                )
                if not offering:
                    offering = Activity(
                        activity_code=str(row["activity_code"]),
                        activity_title=str(row["activity_title"]),
                        unit_code=str(row["unit"]),
                        cycle_id=cycle_id,
                    )
                    self.db.add(offering)
                    self.db.flush()
                else:
                    offering.activity_title = str(row["activity_title"])
                    offering.unit_code = str(row["unit"])

                # 3. Upsert registration
                reg = (
                    self.db.query(ActivityEnrollment)
                    .filter(
                        ActivityEnrollment.activity_id == offering.id,
                        ActivityEnrollment.member_id == str(row["member_id"]),
                    )
                    .first()
                )
                if not reg:
                    self.db.add(
                        ActivityEnrollment(activity_id=offering.id, member_id=str(row["member_id"]))
                    )
                seen_enrollments.add((offering.id, str(row["member_id"])))
                units.add(str(row["unit"]))

                # 4. Upsert master slot (deduplicate by activity + day + start time)
                t_start = _parse_time(row["time_window_start"])
                t_end = _parse_time(row["time_window_end"])
                if t_end == t_start:
                    raise ValueError(
                        f"member '{row['member_id']}': time_window_end {t_end} is the "
                        f"same as time_window_start {t_start}, which is either no window "
                        "at all or a whole day and the row does not say which"
                    )

                slot = (
                    self.db.query(StructuralMasterSlot)
                    .filter(
                        StructuralMasterSlot.activity_id == offering.id,
                        StructuralMasterSlot.day_of_week_index == int(row["day_of_week_index"]),
                        StructuralMasterSlot.time_window_start == t_start,
                    )
                    .first()
                )
                room = get_or_create_room(str(row["room"]), self.db)
                if cycle_is_open and (
                    slot is None or slot.resource_id != room.id or slot.time_window_end != t_end
                ):
                    # Only when the row would put this class somewhere it is
                    # not already: a re-upload of an unchanged file must not
                    # start failing because a hold was placed on a room the
                    # timetable has had all along. The API refuses the same
                    # clash on POST and PATCH; a CSV is the third way in and
                    # would otherwise be the way around it.
                    held = held_against_slot(
                        self.db,
                        room.id,
                        int(row["day_of_week_index"]),
                        t_start,
                        t_end,
                    )
                    if held:
                        taken = held[0]
                        raise ValueError(
                            f"activity '{row['activity_code']}': room "
                            f"{room.code} is already held on {taken['date']} "
                            f"from {taken['start']} to {taken['end']}, "
                            "so the class cannot be put there"
                        )
                if not slot:
                    slot = StructuralMasterSlot(
                        day_of_week_index=int(row["day_of_week_index"]),
                        time_window_start=t_start,
                        time_window_end=t_end,
                        activity_id=offering.id,
                        primary_lead_id=str(row["lead_id"]),
                        resource_id=room.id,
                        target_room_identifier=room.code,
                    )
                    self.db.add(slot)
                elif (
                    slot.time_window_end != t_end
                    or slot.primary_lead_id != str(row["lead_id"])
                    or slot.resource_id != room.id
                ):
                    # A re-uploaded file is a correction. This branch used to
                    # not exist: a slot matching on (activity, day, start) was
                    # skipped, so moving a class to another room, or handing it
                    # to another lead, and re-importing did nothing at all and
                    # said nothing about having done nothing.
                    #
                    # A changed start time is a different story. It does not
                    # match, so it arrives as a second slot and the original
                    # stays. The file has no column that could say "this is the
                    # 09:00 class, moved", so the import cannot know, and
                    # guessing would silently delete somebody's timetable.

                    slot.time_window_end = t_end
                    slot.primary_lead_id = str(row["lead_id"])
                    slot.resource_id = room.id
                    slot.target_room_identifier = room.code
                    corrected[slot.id] = slot

                records_processed += 1
                # The session runs with autoflush=False, so without this flush
                # the dedup queries above cannot see rows added for earlier CSV
                # lines: every member sharing a class would add a duplicate
                # registration and master slot.
                self.db.flush()
                # After the flush, so a slot this row created has an id.
                seen_slots.add(slot.id)

            propagation = propagate_slot_corrections(list(corrected.values()), self.db)
            orphans = self._orphans(cycle_id, units, seen_slots, seen_enrollments)

            self.db.commit()
            return {
                "status": "SUCCESS",
                "rows_ingested": records_processed,
                "provisioned_credentials": provisioned,
                "slots_corrected": len(corrected),
                "not_in_file": orphans,
                **propagation,
            }

        except Exception as e:
            self.db.rollback()
            return {"status": "FAILED", "error_log": str(e)}

    def _orphans(
        self,
        cycle_id: int,
        units: set[str],
        seen_slots: set[int],
        seen_enrollments: set[tuple[int, str]],
    ) -> dict[str, list[dict[str, Any]]]:
        """What the cycle holds that this file did not mention.

        A report and never an action. The import has no way to tell a class
        that ended from a file that only covers half the timetable, and a
        partial upload treated as authoritative would delete every enrollment
        it happened not to list. So this names the rows and leaves them alone,
        and somebody decides.

        Scoped to the units the file names, not to the whole cycle. A file
        covering CSE would otherwise report every ECE class as missing, every
        time, which teaches an admin to skip past the field.
        """
        codes = dict(
            self.db.query(Activity.id, Activity.activity_code)
            .filter(Activity.cycle_id == cycle_id, Activity.unit_code.in_(units))
            .all()
        )
        if not codes:
            return {"slots": [], "enrollments": []}
        activity_ids = list(codes)

        slots = [
            {
                "id": slot.id,
                "activity_code": codes[slot.activity_id],
                "day_of_week_index": slot.day_of_week_index,
                "time_window_start": str(slot.time_window_start),
                "room": slot.resource.code if slot.resource else slot.target_room_identifier,
            }
            for slot in self.db.query(StructuralMasterSlot)
            .filter(StructuralMasterSlot.activity_id.in_(activity_ids))
            .all()
            if slot.id not in seen_slots
        ]

        enrollments = [
            {"member_id": reg.member_id, "activity_code": codes[reg.activity_id]}
            for reg in self.db.query(ActivityEnrollment)
            .filter(ActivityEnrollment.activity_id.in_(activity_ids))
            .all()
            if (reg.activity_id, reg.member_id) not in seen_enrollments
        ]

        return {
            "slots": sorted(
                slots,
                key=lambda s: (
                    s["activity_code"],
                    s["day_of_week_index"],
                    s["time_window_start"],
                ),
            ),
            "enrollments": sorted(enrollments, key=lambda e: (e["activity_code"], e["member_id"])),
        }
