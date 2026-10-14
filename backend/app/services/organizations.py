# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""A second organization, with the one administrator who can let anyone else in.

There is no HTTP route for this. An organization is a tenant of the whole
deployment, and nobody signed in to one organization should be able to make
another, so it comes from whoever runs the deployment:
`chronos-engine organization create` (app/standalone.py), and the tests.
Everything after that, the organization's people, resources and schedules,
its own administrator makes over the API as usual.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.emails import normalize_email
from app.core.organization import ALL_ORGANIZATIONS, ORGANIZATION_ID_LIMIT
from app.core.passwords import check_password
from app.core.security import hash_password


def create_organization(
    db: Session,
    organization_id: str,
    name: str,
    admin_id: str,
    admin_email: str,
    admin_password: str,
):
    """Add an organization and its first ORG_ADMIN. Returns the organization.

    Raises ValueError, with a sentence to show the operator, when the
    organization id is empty, too long or taken, when the password fails the
    deployment's policy, or when the administrator's id or email address is
    already used in any organization (both are unique across the deployment).
    The administrator signs in with the password given and has to change it
    first, as the seeded administrator does. Flushes; the caller commits.
    """
    from app.models.db import InstitutionalRole, Organization, User

    organization_id = organization_id.strip()
    if not organization_id or len(organization_id) > ORGANIZATION_ID_LIMIT:
        raise ValueError(f"An organization id is 1 to {ORGANIZATION_ID_LIMIT} characters")
    if not name.strip():
        raise ValueError("An organization needs a name")
    check_password(admin_password)
    email = normalize_email(admin_email)

    if db.get(Organization, organization_id) is not None:
        raise ValueError(f"There is already an organization '{organization_id}'")
    anywhere = {ALL_ORGANIZATIONS: True}
    if db.execute(select(User.id).where(User.id == admin_id).execution_options(**anywhere)).first():
        raise ValueError(f"User ID '{admin_id}' is already in use")
    taken = select(User.id).where(func.lower(User.email_address) == email)
    if db.execute(taken.execution_options(**anywhere)).first():
        raise ValueError(f"The email address '{email}' is already in use")

    organization = Organization(id=organization_id, name=name.strip())
    db.add(organization)
    db.flush()
    db.add(
        User(
            id=admin_id,
            full_name=f"{name.strip()} Administrator",
            email_address=email,
            credential_secure_hash=hash_password(admin_password),
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=True,
            organization_id=organization_id,
        )
    )
    db.flush()
    return organization
