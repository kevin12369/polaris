"""AI 排障助手引擎：报错 → 检索知识库 → 输出排查步骤。

三层降级策略：
1. LLM + 知识库命中 → 最优：LLM 基于检索结果生成针对性步骤
2. 仅知识库命中 → 用条目自带的 steps + 摘要拼装结构化步骤
3. 完全未命中 → 输出通用诊断清单（按分类给出标准排查动作），保证永远有可用输出
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import KbArticle, RetrievalLog, utcnow
from . import llm as llm_svc
from .retrieval import search
from .tokenizer import keywords

# 通用兜底排查清单：按分类给出标准动作
FALLBACK_CHECKLISTS: dict[str, list[dict]] = {
    "账号登录": [
        {"title": "确认账号状态与是否被锁定", "detail": "在后台查询该账号的 status / locked 字段，若 locked 为 true，先执行解锁再让其重试登录。"},
        {"title": "重置密码或让用户走找回密码流程", "detail": "确认忘记密码链接可正常下发；重置后强制用户首次登录修改密码。"},
        {"title": "核对认证服务连通性", "detail": "检查认证服务的健康检查接口与日志，确认 token 签发服务无异常堆积。"},
        {"title": "检查浏览器与客户端环境", "detail": "确认客户端时间正确、Cookie 未被拦截；HTTPS 下确认未出现混合内容拦截。"},
    ],
    "接口API": [
        {"title": "拿到完整请求与响应", "detail": "记录请求 URL、方法、请求头、请求体与完整响应体（含状态码），确认错误发生在调用方还是服务端。"},
        {"title": "复现并定位错误层", "detail": "用同样的入参在测试环境复现，判断是参数校验、鉴权、业务逻辑还是依赖服务故障。"},
        {"title": "检查服务端错误日志", "detail": "按请求 traceId 在应用日志中检索异常栈，确认是否有 5xx 或超时。"},
        {"title": "验证依赖与配额", "detail": "检查下游依赖健康状态、限流配额是否被打满、连接池是否耗尽。"},
    ],
    "数据问题": [
        {"title": "确认影响范围", "detail": "统计受影响记录数、时间区间与具体租户/用户，判断是单条还是批量问题。"},
        {"title": "从备份或日志还原真实值", "detail": "对比备份快照与当前库表数据，确认是数据被改写、丢失还是从未写入。"},
        {"title": "检查写入链路", "detail": "排查消息队列积压、异步任务失败、定时任务未执行等写入侧问题。"},
        {"title": "修复前先做数据快照", "detail": "任何修复操作前先做表级快照，避免二次破坏。"},
    ],
    "性能卡顿": [
        {"title": "采集性能基线", "detail": "记录慢查询、接口 P95 延迟、CPU/内存/IO 使用率与连接数，定位瓶颈层。"},
        {"title": "定位慢查询或热点接口", "detail": "从 APM 或数据库慢日志中找出耗时最长的 SQL 与接口，检查索引命中与执行计划。"},
        {"title": "检查容量与并发", "detail": "确认流量是否出现突增，缓存是否失效、连接池与线程池是否被占满。"},
        {"title": "确认是否与近期变更相关", "detail": "对比发布时间点与性能劣化时间点，回滚或灰度验证。"},
    ],
    "部署运维": [
        {"title": "确认发布版本与变更内容", "detail": "核对当前运行的版本/commit 与最近的发布记录，确认是否为已知问题版本。"},
        {"title": "检查服务健康与日志", "detail": "查看容器/进程状态、健康检查结果、重启次数与最近错误日志。"},
        {"title": "检查配置与依赖连通", "detail": "核对环境变量、密钥、证书有效期、域名解析与下游服务连通性。"},
        {"title": "准备回滚方案", "detail": "若问题由本次发布引入，按预案回滚到上一个稳定版本并观察。"},
    ],
    "功能缺陷": [
        {"title": "稳定复现路径", "detail": "记录完整复现步骤：账号类型、操作路径、输入数据、环境版本与浏览器。"},
        {"title": "确认是否已知问题", "detail": "检索知识库与历史工单，确认是否为已记录并已修复的缺陷。"},
        {"title": "界定影响范围", "detail": "确认是仅当前用户还是所有用户，判断严重级别与是否需要临时规避方案。"},
        {"title": "转研发并跟踪", "detail": "附复现材料提交研发，跟踪修复版本并在回归时通知客户。"},
    ],
    "支付账单": [
        {"title": "核对订单与支付流水", "detail": "比对业务订单号与第三方支付流水号，确认是否已扣款但业务侧未入账。"},
        {"title": "检查金额与优惠叠加规则", "detail": "确认订单金额、优惠券、税费计算是否与规则一致。"},
        {"title": "确认对账文件", "detail": "拉取渠道对账文件，核对差异记录，判断是渠道延迟还是金额错误。"},
    ],
    "咨询其他": [
        {"title": "明确需求边界", "detail": "与客户确认具体想要达成的目标、当前卡在哪一步、期望的时间点。"},
        {"title": "检索文档与已有方案", "detail": "查找产品文档与知识库中的标准操作流程，避免重复答疑。"},
        {"title": "给出结论并确认理解", "detail": "用客户能懂的话说明做法，并请对方复述确认理解一致。"},
    ],
}

GENERIC_CHECKLIST = [
    {"title": "完整复现一次", "detail": "拿到与客户完全一致的环境、账号、输入数据，把问题稳定复现出来。"},
    {"title": "确认影响范围", "detail": "明确是单用户、单环境还是全部用户，单点还是持续发生。"},
    {"title": "核对近期变更", "detail": "对比问题出现时间与最近的代码发布、配置变更、数据迁移时间点。"},
    {"title": "分层定位", "detail": "按 前端→接口→服务→数据库→依赖 的顺序逐层排除，不要跳步。"},
    {"title": "临时规避 + 根因修复", "detail": "先给客户可用的临时方案止血，同时推进根因修复与回归验证。"},
]


def _article_payload(article: KbArticle, score: float, terms: list[str]) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "category": article.category,
        "summary": article.summary,
        "content": article.content,
        "steps": article.steps or [],
        "score": score,
        "matched_terms": terms,
        "source_ticket_code": article.source_ticket_code,
    }


def troubleshoot(
    db: Session,
    company_id: int,
    error_text: str,
    ticket_id: int | None = None,
    top_k: int = 5,
) -> dict:
    """核心入口：检索知识库 → 生成排查步骤 → 记录检索日志。"""
    # min_score=3.0 / min_coverage=0.15 由实测标定：
    # 相关报错得分 >= 6.4，不相关报错最高仅 1.9
    scored = search(db, company_id, error_text, limit=top_k, min_score=3.0, min_coverage=0.15)
    articles = [_article_payload(s.article, s.score, s.matched_terms) for s in scored]

    hit = len(articles) > 0
    engine = "rules"
    summary = ""
    steps: list[dict] = []

    # ---- 第 1 层：LLM 生成 ----
    if hit and llm_svc.llm_available():
        result = llm_svc.generate_steps(error_text, articles)
        if result:
            summary = result["summary"]
            steps = result["steps"]
            engine = "llm+kb"

    # ---- 第 2 层：知识库自带步骤 ----
    if not steps and hit:
        summary_parts = []
        for a in articles:
            if a["summary"]:
                summary_parts.append(f"《{a['title']}》：{a['summary']}")
            elif a["content"]:
                summary_parts.append(f"《{a['title']}》：{a['content'][:160]}")
        summary = "匹配到 " + str(len(articles)) + " 条知识库条目，按下列步骤排查。" + (
            " ".join(summary_parts[:3])
        )
        for a in articles:
            for st in a["steps"]:
                steps.append(
                    {
                        "title": st.get("title", "检查项"),
                        "detail": st.get("detail", ""),
                        "source": a["title"],
                    }
                )
            if not a["steps"] and a["content"]:
                steps.append(
                    {
                        "title": f"参照《{a['title']}》",
                        "detail": a["content"][:500],
                        "source": a["title"],
                    }
                )
        # 限制步骤总数，保留前 10 条
        steps = steps[:10]
        engine = "kb" if steps else "rules"

    # ---- 第 3 层：通用兜底 ----
    if not steps:
        from .classifier import classify_by_rules

        cls = classify_by_rules(error_text[:200], error_text)
        checklist = FALLBACK_CHECKLISTS.get(cls.category, GENERIC_CHECKLIST)
        steps = [dict(s) for s in checklist]
        summary = (
            f"知识库中暂未找到完全匹配的条目。根据问题特征判定为「{cls.category}」，"
            f"先按以下标准流程排查，同时建议把结论沉淀回知识库。"
        )
        engine = "fallback"
        hit = False

    # ---- 记录检索日志 ----
    log = RetrievalLog(
        company_id=company_id,
        source="assistant",
        ticket_id=ticket_id,
        query=error_text[:2000],
        matched_ids=[a["id"] for a in articles],
        hit=hit,
        score=articles[0]["score"] if articles else 0.0,
    )
    db.add(log)
    db.flush()
    log_id = log.id

    # ---- 命中计数 +1 ----
    if articles:
        for a in articles:
            art = db.get(KbArticle, a["id"])
            if art is not None:
                art.hits = (art.hits or 0) + 1

    confidence = 0.0
    if articles and hit:
        top = articles[0]["score"]
        # 置信度同时参考得分与命中词数量，避免"高 IDF 撞词"造成虚高
        term_count = len(articles[0]["matched_terms"])
        confidence = min(0.95, 0.3 + top / 14 + min(term_count, 6) * 0.04)

    return {
        "summary": summary,
        "steps": steps,
        "matched_articles": [
            {
                "id": a["id"],
                "title": a["title"],
                "category": a["category"],
                "summary": a["summary"],
                "score": a["score"],
                "matched_terms": a["matched_terms"],
                "source_ticket_code": a["source_ticket_code"],
            }
            for a in articles
        ],
        "hit": hit,
        "confidence": round(confidence, 3),
        "engine": engine,
        "keywords": keywords(error_text),
        "log_id": log_id,
        "created_at": utcnow().isoformat(),
    }
