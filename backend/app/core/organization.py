# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Which organization a row belongs to, and keeping each caller inside its own.

Every table holding an organization's data takes OrganizationScoped, which
gives it an organization_id. A session that knows its caller's organization
(security.get_current_user puts it there with use_organization) then sees
only that organization's rows: every ORM select, update and delete it runs
gets the condition added by _only_this_organization. A row in another
organization is therefore missing, and a route answers it with the same 404
it gives a row that does not exist.

New rows are filed by _file_new_rows: under the session's organization when
it has one, and under DEFAULT_ORGANIZATION_ID when it has none (the
scheduled jobs, the seed, the embedded host's provisioning). Code that knows
better, such as the ledger generator copying a slot's organization onto its
days, sets organization_id itself and is left alone.

What this does not reach: Core statements on a raw connection (the
portability archive, which filters for itself) and text() SQL. A query that
has to look across organizations, such as the check that a user id or an
email address is free in the whole deployment, says so with
`.execution_options(all_organizations=True)`.
"""

from sqlalchemy import Column, ForeignKey, String, event
from sqlalchemy.orm import Session, declared_attr, with_loader_criteria

# The organization every 0.16 row would have been in, and where a new
# deployment's seeded administrator lives (app/core/schema.py).
DEFAULT_ORGANIZATION_ID = "default"
ORGANIZATION_ID_LIMIT = 50

_SESSION_KEY = "organization_id"
ALL_ORGANIZATIONS = "all_organizations"


class OrganizationScoped:
    """A table whose rows each belong to one organization.

    organization_optional is for audit_records alone: a failed sign-in has
    no caller and so no organization. Such a row is in no organization and
    no caller's session ever sees it.
    """

    organization_optional = False

    @declared_attr
    def organization_id(cls):
        return Column(
            String(ORGANIZATION_ID_LIMIT),
            ForeignKey("organizations.id"),
            nullable=cls.organization_optional,
            index=True,
        )


def use_organization(db: Session, organization_id: str) -> None:
    """From here on, this session sees and files rows in this organization only."""
    db.info[_SESSION_KEY] = organization_id


def current_organization(db: Session) -> str | None:
    return db.info.get(_SESSION_KEY)


@event.listens_for(Session, "do_orm_execute")
def _only_this_organization(state):
    organization = state.session.info.get(_SESSION_KEY)
    if organization is None or state.is_column_load or state.is_relationship_load:
        return
    if state.execution_options.get(ALL_ORGANIZATIONS):
        return
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            with_loader_criteria(
                OrganizationScoped,
                lambda cls: cls.organization_id == organization,
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _file_new_rows(session, flush_context, instances):
    organization = session.info.get(_SESSION_KEY) or DEFAULT_ORGANIZATION_ID
    for row in session.new:
        if (
            isinstance(row, OrganizationScoped)
            and not row.organization_optional
            and row.organization_id is None
        ):
            row.organization_id = organization
