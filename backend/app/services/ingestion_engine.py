# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.db import (
    CourseOffering,
    CourseRegistration,
    InstitutionalRole,
    StructuralMasterSlot,
    User,
)

REQUIRED_COLUMNS = {
    "student_id",
    "student_name",
    "student_email",
    "subject_code",
    "subject_title",
    "department",
    "day_of_week_index",
    "time_window_start",
    "time_window_end",
    "teacher_id",
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
    raise ValueError(f"Cannot parse time value '{raw}' — expected HH:MM or HH:MM:SS")


class ChronosIngestionEngine:
    def __init__(self, db: Session):
        self.db = db

    def process_student_centric_matrix(self, file_path: str, cycle_id: int) -> dict[str, Any]:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return {"status": "FAILED", "error_log": f"CSV parse error: {e}"}

        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            return {"status": "FAILED", "error_log": f"Missing columns: {missing}"}

        records_processed = 0

        try:
            for _, row in df.iterrows():
                # 1. Upsert student user
                student = self.db.query(User).filter(User.id == str(row["student_id"])).first()
                if not student:
                    student = User(
                        id=str(row["student_id"]),
                        full_name=str(row["student_name"]),
                        email_address=str(row["student_email"]),
                        credential_secure_hash=hash_password("ChangeMe2026!"),
                        role_type=InstitutionalRole.STUDENT,
                        department_code=str(row["department"]),
                    )
                    self.db.add(student)
                else:
                    student.full_name = str(row["student_name"])

                # 2. Upsert course offering
                offering = (
                    self.db.query(CourseOffering)
                    .filter(
                        CourseOffering.course_code == str(row["subject_code"]),
                        CourseOffering.cycle_id == cycle_id,
                    )
                    .first()
                )
                if not offering:
                    offering = CourseOffering(
                        course_code=str(row["subject_code"]),
                        course_title=str(row["subject_title"]),
                        department_code=str(row["department"]),
                        cycle_id=cycle_id,
                    )
                    self.db.add(offering)
                    self.db.flush()

                # 3. Upsert registration
                reg = (
                    self.db.query(CourseRegistration)
                    .filter(
                        CourseRegistration.course_offering_id == offering.id,
                        CourseRegistration.student_id == str(row["student_id"]),
                    )
                    .first()
                )
                if not reg:
                    self.db.add(
                        CourseRegistration(
                            course_offering_id=offering.id, student_id=str(row["student_id"])
                        )
                    )

                # 4. Upsert master slot (deduplicate by course + day + start time)
                t_start = _parse_time(row["time_window_start"])
                t_end = _parse_time(row["time_window_end"])

                slot = (
                    self.db.query(StructuralMasterSlot)
                    .filter(
                        StructuralMasterSlot.course_offering_id == offering.id,
                        StructuralMasterSlot.day_of_week_index == int(row["day_of_week_index"]),
                        StructuralMasterSlot.time_window_start == t_start,
                    )
                    .first()
                )
                if not slot:
                    self.db.add(
                        StructuralMasterSlot(
                            day_of_week_index=int(row["day_of_week_index"]),
                            time_window_start=t_start,
                            time_window_end=t_end,
                            course_offering_id=offering.id,
                            primary_instructor_id=str(row["teacher_id"]),
                            target_room_identifier=str(row["room"]),
                        )
                    )

                records_processed += 1
                # The session runs with autoflush=False, so without this flush
                # the dedup queries above cannot see rows added for earlier CSV
                # lines: every student sharing a class would add a duplicate
                # registration and master slot.
                self.db.flush()

            self.db.commit()
            return {"status": "SUCCESS", "rows_ingested": records_processed}

        except Exception as e:
            self.db.rollback()
            return {"status": "FAILED", "error_log": str(e)}
