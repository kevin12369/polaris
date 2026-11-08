"""ORM 模型：多租户（公司）+ 用户 + 工单 + 工单事件 + 知识库 + 检索日志。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Company(Base):
    """租户：一家小公司 = 一个独立空间，数据完全隔离。"""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(60))
    seats: Mapped[int] = mapped_column(Integer, default=5)
    plan: Mapped[str] = mapped_column(String(20), default="trial")
    # 该企业的工作时间表（覆盖全局默认），见 config.py 说明
    work_schedule: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    articles: Mapped[list["KbArticle"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class User(Base):
    """坐席账号。role=admin 可管理成员，其余为普通坐席。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(160), index=True)
    name: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="agent")  # admin / agent
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="users")


class Ticket(Base):
    """工单主表。"""

    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_ticket_company_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)  # TK-0001
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    requester_name: Mapped[str] = mapped_column(String(60), default="")
    requester_email: Mapped[str] = mapped_column(String(160), default="")
    channel: Mapped[str] = mapped_column(String(20), default="portal")  # portal/email/chat/phone/api

    category: Mapped[str] = mapped_column(String(30), default="咨询其他", index=True)
    priority: Mapped[str] = mapped_column(String(4), default="P3", index=True)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    # 分类来源：ai=模型判定，manual=人工覆盖
    category_source: Mapped[str] = mapped_column(String(10), default="ai")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    tags: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    first_response_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    # SLA：截止时间在创建时按优先级固化
    sla_response_due: Mapped[dt.datetime | None] = mapped_column(DateTime)
    sla_resolve_due: Mapped[dt.datetime | None] = mapped_column(DateTime)
    sla_response_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_resolve_breached: Mapped[bool] = mapped_column(Boolean, default=False)

    # 知识库关联：命中过知识库 = kb_hit
    kb_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_kb_ids: Mapped[list] = mapped_column(JSON, default=list)
    resolution_note: Mapped[str] = mapped_column(Text, default="")

    company: Mapped[Company] = relationship(back_populates="tickets")
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketEvent.id"
    )
    attachments: Mapped[list["TicketAttachment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketAttachment.id"
    )


class TicketAttachment(Base):
    """工单附件。

    文件本体存在磁盘（见 app/storage.py），这里只存元数据。
    stored_name 是随机生成的，不含用户输入 —— 这是路径穿越防御的关键。
    """

    __tablename__ = "ticket_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # 磁盘上的随机文件名（唯一，下载时用它定位）
    stored_name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # 用户上传时的原始文件名，仅作展示
    original_name: Mapped[str] = mapped_column(String(255))
    # 校验后的真实 MIME（不是浏览器声称的）
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    ticket: Mapped["Ticket"] = relationship(back_populates="attachments")
    uploader: Mapped["User"] = relationship()


class TicketEvent(Base):
    """工单事件流：状态流转 / 备注 / SLA 提醒 / 知识库沉淀，全量留痕。"""

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_name: Mapped[str] = mapped_column(String(60), default="系统")
    type: Mapped[str] = mapped_column(String(30))  # created/classified/status/comment/sla/kb
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    ticket: Mapped[Ticket] = relationship(back_populates="events")


class KbArticle(Base):
    """知识库条目。可由工单一键沉淀而来。"""

    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(30), default="咨询其他", index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    # 来源：manual=手写，ticket=工单沉淀
    source: Mapped[str] = mapped_column(String(20), default="manual")
    source_ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"))
    source_ticket_code: Mapped[str | None] = mapped_column(String(20))
    # 排查步骤（AI 排障助手优先复用；JSON 数组，每项 {title, detail}）
    steps: Mapped[list] = mapped_column(JSON, default=list)

    views: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)  # 被检索命中次数
    helpful: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship(back_populates="articles")


class RetrievalLog(Base):
    """检索日志：用于统计知识库命中率、沉淀高频问题。"""

    __tablename__ = "retrieval_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20), default="assistant")  # assistant / ticket_suggest
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"))
    query: Mapped[str] = mapped_column(Text, default="")
    matched_ids: Mapped[list] = mapped_column(JSON, default=list)
    hit: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
