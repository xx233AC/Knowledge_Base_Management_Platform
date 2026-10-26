from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

EntityId = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]


class Input(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class Login(Input):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class Ids(Input):
    ids: list[EntityId] = Field(min_length=1, max_length=100)


class Grant(Input):
    type: Literal['global', 'department', 'role', 'user']
    id: EntityId | None = None


class Grants(Input):
    permissions: list[Grant] = Field(max_length=500)


class UserInput(Input):
    username: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[\w.@-]+$")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: EntityId | Literal[''] | None = None
    role_ids: list[EntityId] | None = Field(default=None, max_length=100)
    status: Literal['active', 'disabled'] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class Password(Input):
    password: str = Field(min_length=8, max_length=128)


class RoleInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-zA-Z][\w.-]*$")
    description: str | None = Field(default=None, max_length=2000)
    permissions: list[str] | None = Field(default=None, max_length=100)


class RolePermissions(Input):
    permissions: list[str] = Field(max_length=100)


class DepartmentInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: EntityId | Literal[''] | None = None
    leader_id: EntityId | Literal[''] | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)


class UnitInput(Input):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=2_000_000)
    summary: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=30)
    attachments: list[dict] | None = Field(default=None, max_length=100)
    status: Literal['draft', 'published'] | None = None
    acl: list[Grant] | None = Field(default=None, max_length=500)
    gap_id: EntityId | None = None

    @field_validator('tags')
    @classmethod
    def bounded_tags(cls, value):
        if value is not None and any(not x.strip() or len(x) > 64 for x in value):
            raise ValueError('标签须为 1–64 个字符')
        return list(dict.fromkeys(value)) if value is not None else None


class PermissionCheck(Input):
    user_id: EntityId = Field(alias='user_id')
    unit_ids: list[EntityId] = Field(alias='unit_ids', max_length=100)


class ChatInput(Input):
    question: str = Field(min_length=1, max_length=2000)
    session_id: EntityId | None = Field(default=None, alias='session_id')


class FaqInput(Input):
    question: str | None = Field(default=None, min_length=1, max_length=2000)
    answer: str | None = Field(default=None, min_length=1, max_length=20000)
    unit_id: EntityId | None = None
    category: str | None = Field(default=None, max_length=100)
    status: Literal['pending_review', 'published', 'rejected'] | None = None
    cache: bool | None = None


class FaqReview(Input):
    action: Literal['approve', 'reject']
    edited_answer: str = Field(default='', alias='edited_answer', max_length=20000)


class GapInput(Input):
    status: Literal['unresolved', 'resolved', 'ignored']
    unit_id: EntityId | None = None


class IntegrationInput(Input):
    enabled: bool = False
    base_url: str = Field(default='', max_length=2000)
    api_key: str | None = Field(default=None, max_length=4000)
    model: str = Field(default='', max_length=200)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    timeout_seconds: int = Field(default=120, ge=5, le=300)
    thinking_enabled: bool = False
    reasoning_effort: Literal['low', 'high', 'max'] = 'high'
    vision_enabled: bool = False
    vision_model: str = Field(default='deepseek-flash', max_length=200)
    vision_max_images: int = Field(default=100, ge=1, le=300)
    login_url: str = Field(default='', max_length=2000)
    username: str = Field(default='', max_length=200)
    password: str | None = Field(default=None, max_length=4000)
    callback_url: str = Field(default='', max_length=2000)
