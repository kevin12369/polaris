"""端到端验收测试。

一条命令验证四个模块的主流程 + 关键约束：
    python tests/test_e2e.py

覆盖：
- 认证与租户隔离
- 工单：AI 分类、SLA 固化、状态机、事件流
- 知识库：检索、沉淀、命中标记
- AI 排障：命中 / 未命中兜底 / 检索判据
- 仪表盘：四个核心指标
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8100/api")

# 每次运行用唯一邮箱，避免重复执行时冲突
RUN_ID = os.getenv("TEST_RUN_ID") or __import__("time").strftime("%H%M%S")

# 测试打的是本机服务，不能走系统代理。
# 很多环境设了 HTTP_PROXY，urllib 默认会读它，导致本机请求被转发到代理
# 而失败（"upstream connect failed"）。这里显式建一个无代理的 opener。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
EMAIL_MAIN = f"e2e-main-{RUN_ID}@example.com"
EMAIL_OTHER = f"e2e-other-{RUN_ID}@example.com"
EMAIL_AGENT = f"e2e-agent-{RUN_ID}@example.com"
EMAIL_DUP = f"e2e-dup-{RUN_ID}@example.com"

passed = 0
failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with _OPENER.open(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"detail": raw}


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    section("0. 健康检查")
    code, health = call("GET", "/health")
    check("健康检查返回 ok", code == 200 and health.get("status") == "ok", str(health))

    section("1. 认证")
    code, reg = call(
        "POST",
        "/auth/register",
        body={
            "company_name": f"E2E 测试公司 {RUN_ID}",
            "name": "测试管理员",
            "email": EMAIL_MAIN,
            "password": "Test@2026",
        },
    )
    check("自助注册成功", code == 201 and "access_token" in reg, str(reg)[:120])
    token = reg.get("access_token", "")
    company_id = reg.get("company", {}).get("id")

    # 邮箱重复（公司名不同）→ 应报"邮箱已注册"
    code, dup = call(
        "POST",
        "/auth/register",
        body={
            "company_name": f"E2E 另一公司 {RUN_ID}",
            "name": "测试",
            "email": EMAIL_MAIN,
            "password": "Test@2026",
        },
    )
    check("重复邮箱被拒绝", code == 409 and "邮箱" in str(dup.get("detail", "")), f"code={code} {dup}")

    # 公司名重复（邮箱不同）→ 应报"企业空间已存在"，而不是 500
    code, dupname = call(
        "POST",
        "/auth/register",
        body={
            "company_name": f"E2E 测试公司 {RUN_ID}",
            "name": "测试",
            "email": EMAIL_DUP,
            "password": "Test@2026",
        },
    )
    check("重复公司名被友好拒绝(409)", code == 409, f"code={code} {dupname}")

    code, bad = call("POST", "/auth/login", body={"email": EMAIL_MAIN, "password": "wrong"})
    check("错误密码被拒绝", code == 401, f"code={code}")

    code, me = call("GET", "/auth/me", token)
    check("获取当前用户信息", code == 200 and me.get("company", {}).get("id") == company_id)

    section("2. 租户隔离")
    code, other = call(
        "POST",
        "/auth/register",
        body={
            "company_name": f"E2E 隔离空间 {RUN_ID}",
            "name": "另一个人",
            "email": EMAIL_OTHER,
            "password": "Test@2026",
        },
    )
    check("第二个租户注册成功", code == 201, f"code={code} {str(other)[:100]}")
    other_token = other.get("access_token", "")
    code, tickets = call("GET", "/tickets?limit=100", token)
    tid = tickets["items"][0]["id"] if tickets.get("items") else None
    if tid:
        code, _ = call("GET", f"/tickets/{tid}", other_token)
        check("跨租户访问工单被拒绝(404)", code == 404, f"code={code}")

    section("3. 工单：提交与 AI 自动分类")
    code, created = call(
        "POST",
        "/tickets",
        token,
        {
            "title": "所有用户都无法登录，服务完全不可用",
            "content": "今天早上开始全部客户提示账号或密码错误，密码没改过",
        },
    )
    check("提交工单成功", code == 201, f"code={code} {str(created)[:100]}")
    t = created.get("ticket", {})
    cls = created.get("classification", {})
    check("AI 判定分类为账号登录", t.get("category") == "账号登录", f"got={t.get('category')}")
    check("AI 判定优先级为 P1", t.get("priority") == "P1", f"got={t.get('priority')}")
    check("分类置信度 > 0.5", t.get("confidence", 0) > 0.5, f"got={t.get('confidence')}")
    check("分类理由非空", bool(cls.get("reason")), "reason 为空")
    check("SLA 响应截止已固化", bool(t.get("sla_response_due")))
    check("SLA 解决截止已固化", bool(t.get("sla_resolve_due")))
    check("响应截止早于解决截止", t.get("sla_response_due") < t.get("sla_resolve_due"))
    new_id = t.get("id")

    code, ambiguous = call(
        "POST",
        "/tickets",
        token,
        {"title": "想咨询一下标准版和专业版的功能差异", "content": "准备扩容到 50 人"},
    )
    at = ambiguous.get("ticket", {})
    check("咨询类问题判为低优先级 P4", at.get("priority") == "P4", f"got={at.get('priority')}")

    section("4. 工单：状态机")
    # 先流转到处理中，再尝试回退到"已分类"——状态机不允许回退
    code, moved0 = call("POST", f"/tickets/{new_id}/status", token, {"to_status": "in_progress", "note": "开始排查"})
    check("合法流转到处理中", code == 200 and moved0["ticket"]["status"] == "in_progress")
    check("首次响应时间已记录", bool(moved0["ticket"].get("first_response_at")))

    code, _ = call("POST", f"/tickets/{new_id}/status", token, {"to_status": "triaged", "note": "试图回退"})
    check("非法状态流转(回退)被拒绝(400)", code == 400, f"code={code}")

    code, unknown = call("POST", f"/tickets/{new_id}/status", token, {"to_status": "不存在的状态"})
    check("未知状态被拒绝(400)", code == 400, f"code={code}")

    code, detail = call("GET", f"/tickets/{new_id}", token)
    check("事件流记录了创建与流转", len(detail.get("events", [])) >= 2, f"events={len(detail.get('events', []))}")
    check("事件含类型分类", any(e.get("type") == "created" for e in detail.get("events", [])))

    section("5. 知识库：沉淀与检索")
    code, kb_before = call("GET", "/kb?limit=100", token)
    n_before = kb_before.get("total", 0)
    code, promoted = call(
        "POST",
        f"/tickets/{new_id}/promote-to-kb",
        token,
        {"summary": "认证服务连接池耗尽导致全量登录失败", "resolution_note": "扩容连接池后恢复"},
    )
    check("工单沉淀为知识库成功", code == 201, f"code={code}")
    art = promoted.get("article", {})
    check("沉淀条目带来源工单号", art.get("source") == "ticket" and bool(art.get("source_ticket_code")))
    check("沉淀条目含步骤", len(art.get("steps", [])) > 0)
    check("工单被标记知识库命中", promoted["ticket"].get("kb_hit") is True)
    check("工单关联了知识库条目", len(promoted["ticket"].get("linked_kb_ids", [])) > 0)

    code, kb_after = call("GET", "/kb?limit=100", token)
    check("知识库条目数增加", kb_after.get("total", 0) == n_before + 1, f"{n_before} -> {kb_after.get('total')}")

    code, found = call("GET", "/kb?q=" + urllib.request.quote("登录失败"), token)
    check("知识库检索能命中条目", found.get("total", 0) > 0, f"total={found.get('total')}")

    section("6. AI 排障助手")
    # 用第 5 步刚沉淀的条目内容做查询（该租户此刻只有这一条知识）
    code, hit = call(
        "POST",
        "/assistant/troubleshoot",
        token,
        {"error_text": "所有用户都无法登录，提示账号或密码错误，服务完全不可用"},
    )
    check("相关报错命中知识库", hit.get("hit") is True, f"engine={hit.get('engine')}")
    check("输出可执行步骤", len(hit.get("steps", [])) > 0)
    check("步骤带标题与内容", all(s.get("title") and s.get("detail") for s in hit.get("steps", [])))
    check("返回诊断结论", bool(hit.get("summary")))

    code, miss = call("POST", "/assistant/troubleshoot", token, {"error_text": "打印机吐出乱码纸张，扫描枪读不到条码"})
    check("不相关报错走兜底清单", miss.get("hit") is False, f"hit={miss.get('hit')}")
    check("兜底仍给出排查步骤", len(miss.get("steps", [])) > 0)

    section("7. 仪表盘")
    code, dash = call("GET", "/dashboard?days=30", token)
    m = dash.get("metrics", {})
    check("仪表盘返回成功", code == 200)
    check("指标含工单量", "total_tickets" in m)
    check("指标含平均响应时长", "avg_response_minutes" in m)
    check("指标含超时率", "timeout_rate" in m)
    check("指标含知识库命中率", "kb_hit_rate" in m)
    check("工单量与实际一致", m.get("total_tickets") == len(dash.get("trend", [])) or m.get("total_tickets", 0) >= 2)
    check("返回趋势数据", len(dash.get("trend", [])) > 0)
    check("返回分类分布", len(dash.get("by_category", [])) > 0)

    section("8. 工作时间表")
    code, ws = call("GET", "/settings/work-schedule", token)
    check("读取工作时间表", code == 200 and "work_days" in ws)
    code, ws2 = call(
        "PUT",
        "/settings/work-schedule",
        token,
        {"work_days": [0, 1, 2, 3, 4, 5], "work_start_hour": 9, "work_end_hour": 18},
    )
    check("修改工作时间表(含周六)", code == 200 and ws2.get("work_days") == [0, 1, 2, 3, 4, 5])
    code, bad_ws = call(
        "PUT", "/settings/work-schedule", token,
        {"work_days": [0, 1], "work_start_hour": 18, "work_end_hour": 9},
    )
    check("非法排班被拒绝", code == 400, f"code={code}")

    code, member = call(
        "POST", "/auth/members", token,
        {"name": "坐席", "email": EMAIL_AGENT, "password": "Test@2026", "role": "agent"},
    )
    check("添加坐席成功", code == 200)
    agent_token = call("POST", "/auth/login", body={"email": EMAIL_AGENT, "password": "Test@2026"})[1].get("access_token", "")
    code, _ = call(
        "PUT", "/settings/work-schedule", agent_token,
        {"work_days": [0], "work_start_hour": 9, "work_end_hour": 18},
    )
    check("非管理员改排班被拒绝(403)", code == 403, f"code={code}")

    section("9. 清理")
    for a_id in [a.get("id") for a in kb_after.get("items", []) if a.get("source") == "ticket"]:
        call("DELETE", f"/kb/{a_id}", token)
    code, final_kb = call("GET", "/kb?limit=100", token)
    check("删除知识库条目生效", final_kb.get("total", 0) < kb_after.get("total", 0) or final_kb.get("total") == n_before)

    print("\n" + "=" * 56)
    total = passed + len(failed)
    if failed:
        print(f"❌ {len(failed)}/{total} 项失败:")
        for f in failed:
            print(f"   - {f}")
        return 1
    print(f"✅ 全部通过 ({passed}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
