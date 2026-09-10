# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel, EmailStr

from app.core.passwords import AcceptablePassword


class LoginRequest(BaseModel):
    email: EmailStr
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
