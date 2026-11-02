"""一键为某家公司开通空间。

部署完成后，给目标公司生成账号密码，比让对方自己注册摩擦小得多。

用法：
    python -m app.onboard "易宇通科技" --admin 张三 --email zs@kingtrans.net --password xxx
    python -m app.onboard "易宇通科技" --admin 张三 --email zs@kingtrans.net --password xxx --plan trial --industry 跨境物流软件
"""
from __future__ import annotations

import argparse
import re
import uuid

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Company, KbArticle, Ticket, User, utcnow
from .security import hash_password


def slugify(name: str) -> str:
    """同 auth._slugify：用 uuid 而非时间戳，避免同秒注册撞唯一约束。"""
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return f"{base[:24] or 'company'}-{uuid.uuid4().hex[:8]}"


def onboard(
    company_name: str,
    admin_name: str,
    admin_email: str,
    password: str,
    industry: str | None = None,
    plan: str = "trial",
    seats: int = 10,
    with_demo_kb: bool = True,
) -> dict:
    init_db()
    db = SessionLocal()
    try:
        email = admin_email.lower().strip()
        exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if exists:
            raise SystemExit(f"错误：邮箱 {email} 已被注册（公司：{exists.company.name}）")

        company = Company(
            name=company_name.strip(),
            slug=slugify(company_name),
            industry=industry,
            plan=plan,
            seats=seats,
        )
        db.add(company)
        db.flush()

        admin = User(
            company_id=company.id,
            email=email,
            name=admin_name.strip(),
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(admin)
        db.flush()

        kb_count = 0
        if with_demo_kb:
            # 灌入通用排查清单作为起步知识库，避免新租户面对空白
            from .services.troubleshooter import FALLBACK_CHECKLISTS

            for category, steps in FALLBACK_CHECKLISTS.items():
                db.add(
                    KbArticle(
                        company_id=company.id,
                        title=f"{category}｜标准排查清单",
                        content="\n".join(f"{i+1}. {s['title']}：{s['detail']}" for i, s in enumerate(steps)),
                        summary=f"{category}类问题的通用排查步骤，可按自身业务修改后使用。",
                        category=category,
                        tags=["起步模板"],
                        steps=steps,
                        source="manual",
                        created_by=admin.id,
                    )
                )
                kb_count += 1

        db.commit()
        return {
            "company_id": company.id,
            "company": company.name,
            "admin": admin.name,
            "email": admin.email,
            "kb_seeded": kb_count,
        }
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(description="一键开通企业空间")
    p.add_argument("company", help="公司/团队名称")
    p.add_argument("--admin", required=True, help="管理员姓名")
    p.add_argument("--email", required=True, help="管理员邮箱")
    p.add_argument("--password", required=True, help="初始密码（至少 6 位）")
    p.add_argument("--industry", default=None, help="行业")
    p.add_argument("--plan", default="trial", help="套餐：trial / standard")
    p.add_argument("--seats", type=int, default=10, help="席位数")
    p.add_argument("--no-kb", action="store_true", help="不预置起步知识库")
    args = p.parse_args()

    if len(args.password) < 6:
        raise SystemExit("错误：密码至少 6 位")

    result = onboard(
        company_name=args.company,
        admin_name=args.admin,
        admin_email=args.email,
        password=args.password,
        industry=args.industry,
        plan=args.plan,
        seats=args.seats,
        with_demo_kb=not args.no_kb,
    )

    print("=" * 56)
    print("开通成功 —— 把下面这段发给对方即可")
    print("=" * 56)
    print(f"  登录地址: http://<服务器IP>:8080")
    print(f"  企业空间: {result['company']}")
    print(f"  管理员  : {result['admin']}")
    print(f"  邮箱    : {result['email']}")
    print(f"  密码    : {args.password}")
    if result["kb_seeded"]:
        print(f"  已预置  : {result['kb_seeded']} 条起步排查清单")
    print("=" * 56)
    print("提示：首次登录后建议让对方立即修改密码，并添加自己的坐席账号。")


if __name__ == "__main__":
    main()
