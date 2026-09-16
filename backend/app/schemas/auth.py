# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import AliasChoices, BaseModel, EmailStr, Field

from app.core.passwords import AcceptablePassword


class LoginRequest(BaseModel):
    # `email_address` is the name every other schema uses. `email` is still
    # read, deprecated, until 0.15 removes it.
    email_address: EmailStr = Field(validation_alias=AliasChoices("email_address", "email"))
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str
    initial_login_state: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: AcceptablePassword


class ChangePasswordResponse(BaseModel):
    message: str
    # The change deletes every refresh token the account held, including the
    # one belonging to the browser that asked for it. This is its replacement:
    # without it that browser is signed out at its next refresh, which is not
    # what anyone means by changing their password.
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str
