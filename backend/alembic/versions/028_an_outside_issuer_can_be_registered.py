# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An outside issuer can be registered

Four tables and no change to any existing one. An instance that never
registers an issuer is behaving exactly as it did, which is the point: the
feature is off unless somebody turns it on, and these tables are empty until
somebody fills them.

federated_issuers is who may vouch for a person. federated_issuer_keys is what
they sign with, several at once so a key rotation has an overlap rather than a
restart. federated_role_map is what a group they assert means here, and the
check constraint is the rule that neither admin role can come from outside:
that one is worth having in the database and not only in a validator.
federated_identities is the link between a subject over there and an account
here, which is the only thing consulted to decide whether a note belongs to an
account that already exists.

institutional_role already exists as a type, so the enum is bound with
create_type False. Creating it again would fail on Postgres and the failure
would arrive in the middle of a migration rather than at the start.

Revision ID: 028
Revises: 027
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "federated_issuers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_federated_issuers_issuer", "federated_issuers", ["issuer"], unique=True)

    op.create_table(
        "federated_issuer_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issuer_id", sa.Integer(), nullable=False),
        sa.Column("kid", sa.String(length=100), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["issuer_id"], ["federated_issuers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("issuer_id", "kid", name="uq_federated_key_kid"),
    )
    op.create_index("ix_federated_issuer_keys_issuer_id", "federated_issuer_keys", ["issuer_id"])

    op.create_table(
        "federated_role_map",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issuer_id", sa.Integer(), nullable=False),
        sa.Column("group_claim_value", sa.String(length=200), nullable=False),
        sa.Column(
            "role_type",
            postgresql.ENUM(
                "ORG_ADMIN",
                "UNIT_ADMIN",
                "STAFF",
                "MEMBER",
                name="institutional_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("unit_code", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["issuer_id"], ["federated_issuers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("issuer_id", "group_claim_value", name="uq_federated_role_map_group"),
        sa.CheckConstraint(
            "role_type IN ('STAFF', 'MEMBER')", name="ck_federated_role_map_no_admin"
        ),
    )
    op.create_index("ix_federated_role_map_issuer_id", "federated_role_map", ["issuer_id"])

    op.create_table(
        "federated_identities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issuer_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["issuer_id"], ["federated_issuers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("issuer_id", "subject", name="uq_federated_identity"),
    )
    op.create_index("ix_federated_identities_issuer_id", "federated_identities", ["issuer_id"])
    op.create_index("ix_federated_identities_user_id", "federated_identities", ["user_id"])


def downgrade() -> None:
    op.drop_table("federated_identities")
    op.drop_table("federated_role_map")
    op.drop_table("federated_issuer_keys")
    op.drop_index("ix_federated_issuers_issuer", table_name="federated_issuers")
    op.drop_table("federated_issuers")
