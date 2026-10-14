# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel

from app.models.db import RequirementEnforcement


class OrganizationResponse(BaseModel):
    id: str
    name: str
    default_requirement_enforcement: RequirementEnforcement

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    """What an organization administrator may change about the organization.

    Only the enforcement a requirement follows when it does not say. The id and
    the name are set from the command line, and a field left out here is
    refused rather than ignored.
    """

    model_config = {"extra": "forbid"}

    default_requirement_enforcement: RequirementEnforcement
