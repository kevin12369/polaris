"""Pydantic 请求/响应模型。"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- 认证 ----------
class RegisterIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    industry: str | None = Field(default=None, max_length=60)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"
    company: "CompanyOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    industry: str | None = None
    plan: str = "trial"


class MemberCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = "agent"


# ---------- 工单 ----------
class TicketCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = ""
    requester_name: str = Field(default="", max_length=60)
    requester_email: str = Field(default="", max_length=160)
    channel: str = "portal"
    priority: str | None = None  # 留空则由 AI 判定
    category: str | None = None  # 留空则由 AI 判定


class TicketUpdateIn(BaseModel):
    title: str | None = None
    content: str | None = None
    priority: str | None = None
    category: str | None = None
    assignee_id: int | None = None
    tags: list[str] | None = None
    category_source: str | None = None


class StatusChangeIn(BaseModel):
    to_status: str
    note: str = ""
    resolution_note: str | None = None


class CommentIn(BaseModel):
    note: str = Field(min_length=1)


class KbPromoteIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None)
    summary: str | None = Field(default=None, max_length=300)
    category: str | None = Field(default=None, max_length=30)
    steps: list[dict] | None = None
    tags: list[str] | None = None


class SuggestIn(BaseModel):
    # content 允许为空：为空时后端自动使用工单自身的标题+描述作为检索词
    content: str = ""


# ---------- 知识库 ----------
class KbCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = ""
    summary: str = Field(default="", max_length=300)
    category: str = "咨询其他"
    tags: list[str] = Field(default_factory=list)
    steps: list[dict] = Field(default_factory=list)


class KbUpdateIn(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    steps: list[dict] | None = None


# ---------- AI 排障 ----------
class TroubleshootIn(BaseModel):
    error_text: str = Field(min_length=2)
    ticket_id: int | None = None


class TroubleshootOut(BaseModel):
    summary: str
    steps: list[dict]
    matched_articles: list[dict]
    hit: bool
    confidence: float
    engine: str
    log_id: int | None = None


TokenOut.model_rebuild()
