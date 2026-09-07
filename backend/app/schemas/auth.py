# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel, EmailStr


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
    new_password: str


class RefreshRequest(BaseModel):
    refresh_token: str
