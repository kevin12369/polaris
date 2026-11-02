"""认证与租户管理路由。"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Company, KbArticle, Ticket, User, utcnow
from ..schemas import LoginIn, MemberCreateIn, RegisterIn, TokenOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slugify(name: str) -> str:
    """
    生成企业空间 slug。

    中文名转拼音不可靠，改用 hash 短码保证唯一。
    注意：不能只用秒级时间戳 —— 同一秒内注册两家公司会撞唯一约束。
    这里用 uuid 前 6 位，冲突概率可忽略。
    """
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    if not base:
        base = "company"
    return f"{base[:24]}-{uuid.uuid4().hex[:8]}"


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """
    自助注册 = 新建一个租户空间 + 第一个管理员。
    小公司点开链接即可开通，无需人工介入。
    """
    email = payload.email.lower().strip()
    exists = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    # 公司名唯一：不同公司可能重名，这里给出明确提示而不是让数据库约束抛 500
    company_name = payload.company_name.strip()
    name_exists = db.execute(
        select(Company).where(func.lower(Company.name) == company_name.lower())
    ).scalar_one_or_none()
    if name_exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"企业空间「{company_name}」已存在，请换一个名称或直接联系管理员加入现有空间",
        )

    company = Company(
        name=company_name,
        slug=_slugify(payload.company_name),
        industry=payload.industry,
        plan="trial",
        seats=10,
    )
    db.add(company)
    db.flush()

    try:
        pwd_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    user = User(
        company_id=company.id,
        email=email,
        name=payload.name.strip(),
        password_hash=pwd_hash,
        role="admin",
    )
    db.add(user)
    db.flush()

    token = create_access_token(user.id, company.id, user.role)
    return TokenOut(
        access_token=token,
        user=user,
        company=company,
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码不正确")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码不正确")
    token = create_access_token(user.id, user.company_id, user.role)
    return TokenOut(access_token=token, user=user, company=user.company)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
        "company": {
            "id": user.company.id,
            "name": user.company.name,
            "slug": user.company.slug,
            "industry": user.company.industry,
            "plan": user.company.plan,
        },
    }


@router.post("/members")
def create_member(payload: MemberCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员邀请坐席。"""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅管理员可添加成员")
    email = payload.email.lower().strip()
    exists = db.execute(
        select(User).where(func.lower(User.email) == email, User.company_id == user.company_id)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已是团队成员")
    try:
        pwd_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    member = User(
        company_id=user.company_id,
        email=email,
        name=payload.name.strip(),
        password_hash=pwd_hash,
        role=payload.role if payload.role in ("admin", "agent") else "agent",
    )
    db.add(member)
    db.flush()
    return {"id": member.id, "name": member.name, "email": member.email, "role": member.role}


@router.get("/members")
def list_members(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.execute(select(User).where(User.company_id == user.company_id)).scalars().all()
    return [
        {"id": m.id, "name": m.name, "email": m.email, "role": m.role, "active": m.active}
        for m in members
    ]


@router.get("/overview")
def trial_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """新租户落地引导页用的数据概览。"""
    cid = user.company_id
    tickets = db.execute(select(func.count(Ticket.id)).where(Ticket.company_id == cid)).scalar_one()
    articles = db.execute(
        select(func.count(KbArticle.id)).where(KbArticle.company_id == cid)
    ).scalar_one()
    return {"tickets": tickets, "articles": articles, "seats": user.company.seats, "plan": user.company.plan}
