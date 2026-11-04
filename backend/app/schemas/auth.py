import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProjectMemberCreate(BaseModel):
    email: str
    role: str = "viewer"  # owner | analyst | viewer


class ProjectMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    email: str | None = None
    full_name: str | None = None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    ip_address: str | None
    created_at: datetime
