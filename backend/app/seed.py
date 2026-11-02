"""种子数据：一条命令生成一套可演示的小公司数据。

用法：
    python -m app.seed            # 生成默认演示数据
    python -m app.seed --reset    # 清空并重建
"""
from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import delete, select

from .db import SessionLocal, init_db
from .models import Company, KbArticle, Ticket, TicketEvent, User, utcnow
from .security import hash_password
from .sla import sla_deadlines

DEMO_EMAIL = "demo@acme.com"
DEMO_PASSWORD = "demo1234"


def _kb_rows() -> list[dict]:
    return [
        {
            "title": "登录失败：提示「账号或密码错误」但密码确认无误",
            "category": "账号登录",
            "tags": ["登录", "密码", "高频"],
            "summary": "多因账号锁定或缓存导致，优先查锁定状态与认证服务日志。",
            "content": "常见根因有三类：\n1. 账号被锁定（连续失败 5 次触发），需在后台解锁；\n2. 密码策略已更新但客户端缓存旧密码；\n3. 认证服务连接池耗尽，返回统一错误。",
            "steps": [
                {"title": "查询账号锁定状态", "detail": "后台用户详情页查看 status 字段，若 locked=true 执行解锁并重置失败计数。"},
                {"title": "清除客户端缓存", "detail": "让用户在隐私窗口重新登录，排除旧 Cookie 与旧密码缓存。"},
                {"title": "检查认证服务日志", "detail": "按用户名检索 auth 服务日志，确认是否出现连接池或鉴权服务异常。"},
                {"title": "验证修复", "detail": "让用户重试登录，确认进入系统且后续操作正常。"},
            ],
        },
        {
            "title": "接口调用返回 502 Bad Gateway",
            "category": "接口API",
            "tags": ["502", "网关", "高频"],
            "summary": "网关到上游服务链路中断，查上游健康状态与连接超时配置。",
            "content": "502 表示网关能收到请求但从上游拿不到有效响应。\n典型原因：上游服务重启/假死、连接池耗尽、超时时间过短、负载均衡摘除节点。",
            "steps": [
                {"title": "确认上游健康状态", "detail": "直接 curl 上游服务健康检查接口，判断是服务挂了还是网关配置问题。"},
                {"title": "检查连接池与超时", "detail": "查看网关/上游的连接池占用与 read timeout 配置，必要时上调超时。"},
                {"title": "查看负载均衡节点", "detail": "确认是否有节点被摘除或正在重启，必要时手动摘除异常节点。"},
                {"title": "复测并观察", "detail": "恢复后用真实请求复测，并在监控中观察 5xx 曲线回落。"},
            ],
        },
        {
            "title": "订单数据导出为空，页面有数据但导出文件是 0 行",
            "category": "数据问题",
            "tags": ["导出", "报表"],
            "summary": "导出任务异步执行且时间窗口参数默认值错误，导致查询区间落在数据之外。",
            "content": "导出走异步队列，导出条件中的时间区间默认取「当月 1 日至当前」，\n若筛选器残留了上次的自定义区间（如去年），会导出 0 行。",
            "steps": [
                {"title": "复现导出条件", "detail": "在相同筛选条件下查看页面显示的记录数，确认页面与导出参数是否一致。"},
                {"title": "检查时间区间参数", "detail": "打开浏览器 Network 面板，查看导出请求的 start/end 参数是否合理。"},
                {"title": "重置筛选后重试", "detail": "清空自定义时间区间，点击重置后重新导出。"},
                {"title": "检查导出队列", "detail": "确认异步导出任务队列无积压，导出中心可看到任务状态。"},
            ],
        },
        {
            "title": "系统响应变慢，页面加载超过 10 秒",
            "category": "性能卡顿",
            "tags": ["性能", "慢"],
            "summary": "先定位瓶颈层：数据库慢查询、服务 CPU、还是外部依赖超时。",
            "content": "性能问题按「前端→接口→服务→数据库→外部依赖」顺序逐层排除。\n最常见根因是慢查询缺少索引，以及外部接口同步调用阻塞主线程。",
            "steps": [
                {"title": "采集基线", "detail": "记录接口 P95 延迟、CPU/内存/IO、数据库连接数，定位瓶颈层。"},
                {"title": "查慢查询日志", "detail": "在数据库慢日志中找出耗时最长的 SQL，检查索引命中与执行计划。"},
                {"title": "排查外部依赖", "detail": "确认是否有第三方接口同步阻塞；必要时加超时与熔断降级。"},
                {"title": "验证优化效果", "detail": "优化后对比 P95 延迟是否回落到目标区间。"},
            ],
        },
        {
            "title": "部署后服务无法访问：容器反复重启",
            "category": "部署运维",
            "tags": ["部署", "docker"],
            "summary": "多为配置缺失或密钥未注入导致启动即崩，看容器日志首屏错误。",
            "content": "容器反复重启（CrashLoopBackOff）几乎都发生在启动阶段：\n环境变量缺失、数据库连不上、端口占用、证书路径错误。",
            "steps": [
                {"title": "看容器日志首屏", "detail": "执行 docker logs <容器> --tail 50，定位第一处异常堆栈。"},
                {"title": "核对配置与密钥", "detail": "检查 compose 中的环境变量、密钥挂载路径与数据库连接串是否正确。"},
                {"title": "确认依赖就绪", "detail": "确认数据库/缓存等依赖容器已健康（healthy），应用在依赖就绪后再启动。"},
                {"title": "验证并回滚", "detail": "重启后确认健康检查通过；异常则回滚到上一个稳定镜像。"},
            ],
        },
        {
            "title": "发票抬头与营业执照不一致，无法开票",
            "category": "支付账单",
            "tags": ["发票", "财务"],
            "summary": "开票信息取自认证时的企业资质快照，需在企业设置中更新。",
            "content": "开票信息来自企业认证时提交的资质快照，\n若公司更名或变更税号，需在「企业设置 - 开票信息」中重新提交并等待审核。",
            "steps": [
                {"title": "核对当前开票信息", "detail": "在企业设置-开票信息中查看抬头、税号、地址电话。"},
                {"title": "提交变更申请", "detail": "上传最新营业执照，提交修改并等待审核（1 个工作日内）。"},
                {"title": "告知客户影响", "detail": "说明审核期间的补开流程，避免客户重复提交。"},
            ],
        },
        {
            "title": "支付成功但订单状态仍为「待支付」",
            "category": "支付账单",
            "tags": ["支付", "对账", "高频"],
            "summary": "支付回调延迟或丢失，用对账文件确认后手工补单。",
            "content": "订单状态依赖第三方支付回调更新。\n回调丢失或延迟时，订单会停留在「待支付」，但实际已扣款。",
            "steps": [
                {"title": "核对支付流水", "detail": "用订单号在第三方支付后台查流水，确认是否已实际扣款。"},
                {"title": "等待回调重试", "detail": "支付平台通常会重试回调，可等待 5-10 分钟后重新查询订单。"},
                {"title": "手工补单", "detail": "确认扣款成功但订单未更新，走后台「支付对账 - 手工补单」操作。"},
                {"title": "根因排查", "detail": "检查回调接口是否可达（公网可访问）、签名校验是否通过、有无异步任务堆积。"},
            ],
        },
        {
            "title": "功能异常：点击「保存」后数据未更新",
            "category": "功能缺陷",
            "tags": ["保存", "缺陷"],
            "summary": "先看是否命中表单校验的静默拦截，再看接口实际返回。",
            "content": "「点了没反应」类问题，多数是前端校验拦截（字段红字提示被忽略）\n或接口返回业务错误但未在界面呈现。",
            "steps": [
                {"title": "检查字段校验", "detail": "确认必填项是否填满，注意红字与必填星号提示。"},
                {"title": "抓取接口响应", "detail": "F12 Network 找到保存请求，看状态码与响应体中的错误信息。"},
                {"title": "确认提交值", "detail": "检查请求体中实际提交的字段值，确认是否被前端逻辑裁剪。"},
                {"title": "转研发", "detail": "附复现步骤与抓包信息提交研发，登记缺陷单。"},
            ],
        },
    ]


def _work_datetime(days_ago: int, hour: int, minute: int) -> dt.datetime:
    """
    生成"days_ago 个工作日前的某个工作时间"。

    为什么要落在工作时段内：SLA 与响应耗时都按工作分钟计算，
    若工单创建于凌晨，演示时会看到一堆 0，掩盖了算法的真实表现。
    """
    from .config import WORK_DAYS

    now = utcnow()
    cursor = now - dt.timedelta(days=days_ago)
    # 向前回溯到最近的工作日
    while cursor.weekday() not in WORK_DAYS:
        cursor -= dt.timedelta(days=1)
    target = dt.datetime.combine(cursor.date(), dt.time(hour, minute))
    # 若落在未来（今天还没到那个点），退回到当前时刻之前
    if target > now:
        target = now - dt.timedelta(minutes=30)
    return target


def _ticket_rows() -> list[dict]:
    now = utcnow()
    return [
        {
            "title": "所有用户登录时提示「账号或密码错误」，昨天还正常",
            "content": "今天上午开始，客户反馈全部账号无法登录，密码确认没改过。已尝试让两个不同客户在隐私窗口重试，问题依旧。",
            "category": "账号登录",
            "priority": "P1",
            "status": "in_progress",
            "days_ago": 0,
            "requester_name": "张明",
            "requester_email": "zhangming@acme.com",
            "resolution_note": "",
        },
        {
            "title": "导出订单报表得到 0 行，但页面明明有 1000 多条",
            "content": "点击导出后文件里只有表头，筛选条件是本月。页面显示 1200 条记录。",
            "category": "数据问题",
            "priority": "P2",
            "status": "pending",
            "days_ago": 1,
            "requester_name": "李伟",
            "requester_email": "liwei@acme.com",
            "resolution_note": "已定位为导出任务时间区间参数残留，提示客户重置筛选后重新导出，等待客户确认。",
        },
        {
            "title": "调用订单查询接口返回 502 Bad Gateway",
            "content": "我们服务端调用 /api/v2/orders 查询订单，昨天开始约三成请求返回 502。自己的服务日志里没有异常。",
            "category": "接口API",
            "priority": "P1",
            "status": "resolved",
            "days_ago": 2,
            "requester_name": "王芳",
            "requester_email": "wangfang@acme.com",
            "resolution_note": "上游订单服务节点假死导致网关 502。将异常节点从负载均衡摘除，并把网关 read timeout 从 5s 调到 15s，问题消失。",
        },
        {
            "title": "支付成功但订单状态一直显示待支付",
            "content": "客户付款成功，银行流水有记录，但后台订单还是待支付状态。已经影响客户对账。",
            "category": "支付账单",
            "priority": "P1",
            "status": "resolved",
            "days_ago": 3,
            "requester_name": "张明",
            "requester_email": "zhangming@acme.com",
            "resolution_note": "第三方支付回调地址被防火墙拦截，回调丢失。对账确认后手工补单 37 笔，并申请开通回调 IP 白名单。",
        },
        {
            "title": "后台首页加载特别慢，要 15 秒以上",
            "content": "上午开始后台首页打开很慢，其他页面正常。客户数量大概 3 万。",
            "category": "性能卡顿",
            "priority": "P2",
            "status": "resolved",
            "days_ago": 4,
            "requester_name": "刘洋",
            "requester_email": "liuyang@acme.com",
            "resolution_note": "慢查询定位到客户列表接口缺 status 索引，补索引后 P95 从 14s 降到 480ms。",
        },
        {
            "title": "请问怎么把企业开票信息改成新的营业执照？",
            "content": "公司上个月更名了，抬头还是旧的。开不了票。",
            "category": "支付账单",
            "priority": "P4",
            "status": "closed",
            "days_ago": 5,
            "requester_name": "陈静",
            "requester_email": "chenjing@acme.com",
            "resolution_note": "指导客户在企业设置-开票信息重新提交最新营业执照，1 个工作日审核通过。",
        },
        {
            "title": "部署新版本后容器一直重启，服务起不来",
            "content": "CI 流水线部署到测试环境，容器起来就挂，日志里报 database connection refused。",
            "category": "部署运维",
            "priority": "P1",
            "status": "closed",
            "days_ago": 6,
            "requester_name": "李伟",
            "requester_email": "liwei@acme.com",
            "resolution_note": "应用启动早于数据库就绪。给 db 服务加 healthcheck，应用加 depends_on condition=service_healthy，问题解决。",
        },
        {
            "title": "保存客户资料后刷新页面，内容又变回原来的",
            "content": "编辑客户联系人电话，点保存没报错，但刷新后还是旧号码。",
            "category": "功能缺陷",
            "priority": "P3",
            "status": "closed",
            "days_ago": 8,
            "requester_name": "王芳",
            "requester_email": "wangfang@acme.com",
            "resolution_note": "抓包发现请求体里 phone 字段被前端校验规则裁剪为空值，是版本回归缺陷。已提交研发修复。",
        },
        {
            "title": "发票抬头和营业执照对不上，开发票报错",
            "content": "抬头是旧公司名。",
            "category": "支付账单",
            "priority": "P3",
            "status": "closed",
            "days_ago": 9,
            "requester_name": "陈静",
            "requester_email": "chenjing@acme.com",
            "resolution_note": "资质快照未更新，指导在企业设置重新提交。",
        },
        {
            "title": "想咨询一下标准版和专业版的功能差异",
            "content": "准备扩容到 50 人，问下两个版本在工单数、附件大小上有什么限制。",
            "category": "咨询其他",
            "priority": "P4",
            "status": "closed",
            "days_ago": 11,
            "requester_name": "刘洋",
            "requester_email": "liuyang@acme.com",
            "resolution_note": "已发送对比说明文档。",
        },
        {
            "title": "订单导出偶发 0 行，昨天又出现一次",
            "content": "和上次类似，但这次时间筛选是清空状态。",
            "category": "数据问题",
            "priority": "P2",
            "status": "resolved",
            "days_ago": 12,
            "requester_name": "李伟",
            "requester_email": "liwei@acme.com",
            "resolution_note": "确认为异步导出任务读取的是提交时刻的筛选快照缓存，修复缓存失效时机。",
        },
        {
            "title": "用户登录偶尔提示密码错误，输入的密码确认是对的",
            "content": "大概每十次有一次，失败后立刻重试又能进。",
            "category": "账号登录",
            "priority": "P2",
            "status": "resolved",
            "days_ago": 13,
            "requester_name": "张明",
            "requester_email": "zhangming@acme.com",
            "resolution_note": "多节点密码策略配置不一致，部分节点仍用旧哈希算法。统一配置后恢复。",
        },
        {
            "title": "线上支付回调大面积失败，客户已扣款但订单未更新",
            "content": "从昨晚开始支付回调失败率飙升，超过一半订单状态没更新，客服那边投诉已经几十个了。",
            "category": "支付账单",
            "priority": "P1",
            "status": "in_progress",
            "days_ago": 0,
            "requester_name": "王芳",
            "requester_email": "wangfang@acme.com",
            "resolution_note": "",
        },
        {
            "title": "导出报表超时，用户等 5 分钟还没出结果",
            "content": "客户反馈大客户导出要等很久，经常超时失败。",
            "category": "性能卡顿",
            "priority": "P2",
            "status": "in_progress",
            "days_ago": 1,
            "requester_name": "刘洋",
            "requester_email": "liuyang@acme.com",
            "resolution_note": "",
        },
    ]


def seed(reset: bool = False) -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.execute(select(Company).where(Company.name == "Acme 演示科技")).scalar_one_or_none()
        if existing and not reset:
            print("演示数据已存在。使用 --reset 可重建。")
            return
        if existing and reset:
            db.execute(delete(KbArticle).where(KbArticle.company_id == existing.id))
            db.execute(delete(Ticket).where(Ticket.company_id == existing.id))
            db.execute(delete(User).where(User.company_id == existing.id))
            db.delete(existing)
            db.flush()

        company = Company(name="Acme 演示科技", slug="acme-demo", industry="企业软件", seats=10, plan="trial")
        db.add(company)
        db.flush()

        admin = User(
            company_id=company.id,
            email=DEMO_EMAIL,
            name="演示管理员",
            password_hash=hash_password(DEMO_PASSWORD),
            role="admin",
        )
        db.add(admin)
        db.flush()

        agent = User(
            company_id=company.id,
            email="agent@acme.com",
            name="客服小林",
            password_hash=hash_password(DEMO_PASSWORD),
            role="agent",
        )
        db.add(agent)
        db.flush()

        # 知识库
        kb_articles: list[KbArticle] = []
        for row in _kb_rows():
            art = KbArticle(
                company_id=company.id,
                title=row["title"],
                content=row["content"],
                summary=row["summary"],
                category=row["category"],
                tags=row["tags"],
                steps=row["steps"],
                source="manual",
                created_by=admin.id,
            )
            db.add(art)
            kb_articles.append(art)
        db.flush()

        # 工单与知识库的关联规则：标题关键词 -> 知识库标题关键词
        LINK_RULES = [
            ("登录", "登录失败"),
            ("502", "502"),
            ("导出", "导出为空"),
            ("慢", "响应变慢"),
            ("容器", "容器反复重启"),
            ("发票", "发票抬头"),
            ("支付成功", "支付成功"),
            ("保存", "保存"),
        ]

        def match_kb(title: str) -> KbArticle | None:
            for t_kw, kb_kw in LINK_RULES:
                if t_kw in title:
                    for art in kb_articles:
                        if kb_kw in art.title:
                            return art
            return None

        # 工单
        now = utcnow()
        for idx, row in enumerate(_ticket_rows()):
            # 创建时间落在工作时段内（10:00 ~ 14:20 交错），让 SLA 演示有真实感
            created = _work_datetime(row["days_ago"], 10 + (idx % 5), (idx * 7) % 60)
            resp_due, resolve_due = sla_deadlines(row["priority"], created)
            closed = row["status"] == "closed"
            resolved = row["status"] in ("resolved", "closed")
            # 首响：25 ~ 90 分钟；解决：3 ~ 9 小时（可能跨下班，由工作分钟算法正确折算）
            first_resp = created + dt.timedelta(minutes=25 + (idx * 11) % 65)
            resolved_at = created + dt.timedelta(hours=3 + (idx * 13) % 6)
            closed_at = resolved_at + dt.timedelta(hours=1 + idx % 4) if closed else None

            ticket = Ticket(
                company_id=company.id,
                code="",
                title=row["title"],
                content=row["content"],
                requester_name=row["requester_name"],
                requester_email=row["requester_email"],
                channel="email" if row["days_ago"] % 2 == 0 else "portal",
                category=row["category"],
                category_source="ai",
                priority=row["priority"],
                status=row["status"],
                confidence=0.78 + (row["days_ago"] % 3) * 0.05,
                assignee_id=admin.id if row["days_ago"] % 2 == 0 else agent.id,
                tags=[],
                created_at=created,
                first_response_at=first_resp,
                resolved_at=resolved_at if resolved else None,
                closed_at=closed_at,
                sla_response_due=resp_due,
                sla_resolve_due=resolve_due,
                resolution_note=row["resolution_note"],
            )
            db.add(ticket)
            db.flush()
            ticket.code = f"TK-{ticket.id:04d}"

            # 已解决/已关闭的工单关联对应知识库条目（真实反映"知识沉淀"效果）
            linked = match_kb(row["title"])
            if linked is not None and resolved:
                ticket.linked_kb_ids = [linked.id]
                ticket.kb_hit = True

            db.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    company_id=company.id,
                    actor_id=admin.id,
                    actor_name="演示管理员",
                    type="created",
                    note=f"工单创建（来源：{ticket.channel}），AI 分类为「{ticket.category}」，优先级 {ticket.priority}。",
                )
            )
            if resolved:
                db.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        company_id=company.id,
                        actor_id=admin.id,
                        actor_name="演示管理员",
                        type="status",
                        from_status="in_progress",
                        to_status=row["status"],
                        note=f"状态流转：处理中 → {row['status']}",
                    )
                )
            if linked is not None and resolved:
                db.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        company_id=company.id,
                        actor_id=admin.id,
                        actor_name="演示管理员",
                        type="kb",
                        note=f"处理过程中参考了知识库条目《{linked.title}》",
                    )
                )

        db.commit()
        print("=" * 56)
        print("演示数据已生成")
        print("=" * 56)
        print(f"  登录邮箱：{DEMO_EMAIL}")
        print(f"  登录密码：{DEMO_PASSWORD}")
        print(f"  坐席账号：agent@acme.com / {DEMO_PASSWORD}")
        print("=" * 56)
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
