# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An absence request can cover more than one day

end_date is the last day of the absence, inclusive. Existing requests keep a
null end_date and go on meaning the single target_absence_date.
"""

import sqlalchemy as sa

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reverse_rsvp_logs", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("reverse_rsvp_logs", "end_date")
