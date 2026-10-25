from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

MAX_URL_LENGTH = 2000

# Allowlist, not a blocklist. A shared link is rendered as an anchor, so
# `javascript:` or `data:` would turn "share a useful link" into stored XSS,
# and blocklists of dangerous schemes are a game you lose eventually.
ALLOWED_SCHEMES = {"http", "https"}


def clean_title(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("Title cannot be empty")
    return stripped


def clean_description(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def clean_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("Links must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("That does not look like a valid link")
    return candidate


class ResourceUser(ORMModel):
    id: UUID
    first_name: str
    last_name: str
    email: str


class ResourceCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=MAX_URL_LENGTH)
    description: str | None = Field(default=None, max_length=1000)

    _title = field_validator("title")(clean_title)
    _url = field_validator("url")(clean_url)
    _description = field_validator("description")(clean_description)


class ResourceUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=MAX_URL_LENGTH)
    description: str | None = Field(default=None, max_length=1000)

    _title = field_validator("title")(clean_title)
    _url = field_validator("url")(clean_url)
    _description = field_validator("description")(clean_description)


class ResourceResponse(BaseModel):
    id: UUID
    group_id: UUID
    title: str
    url: str
    description: str | None
    created_by: UUID
    created_at: datetime
    creator: ResourceUser | None = None
    can_delete: bool = False
