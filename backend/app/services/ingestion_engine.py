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
    StructuralMasterSlot,
    User,
)
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

                # 4. Upsert master slot (deduplicate by activity + day + start time)
                t_start = _parse_time(row["time_window_start"])
                t_end = _parse_time(row["time_window_end"])
                if t_end <= t_start:
                    raise ValueError(
                        f"member '{row['member_id']}': time_window_end {t_end} is not "
                        f"after time_window_start {t_start} "
                        "(windows crossing midnight are not supported yet)"
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
                if not slot:
                    self.db.add(
                        StructuralMasterSlot(
                            day_of_week_index=int(row["day_of_week_index"]),
                            time_window_start=t_start,
                            time_window_end=t_end,
                            activity_id=offering.id,
                            primary_lead_id=str(row["lead_id"]),
                            resource_id=room.id,
                            target_room_identifier=room.code,
                        )
                    )
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

            propagation = propagate_slot_corrections(list(corrected.values()), self.db)

            self.db.commit()
            return {
                "status": "SUCCESS",
                "rows_ingested": records_processed,
                "provisioned_credentials": provisioned,
                "slots_corrected": len(corrected),
                **propagation,
            }

        except Exception as e:
            self.db.rollback()
            return {"status": "FAILED", "error_log": str(e)}
