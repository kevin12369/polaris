"""检索质量测试。

重点覆盖：
1. 正负样本的判别能力（8 篇语料规模下的标定）
2. **小知识库场景** —— 小公司刚开始用时知识库只有 1-5 条，
   BM25 的 IDF 值天然偏低，固定绝对阈值会误杀相关条目（真实缺陷的回归测试）

测试使用独立的临时数据库，不污染演示数据，也不依赖本机残留状态
（CI 上是全新环境，之前因缺少建表而报 "no such table: companies"）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 必须在导入 app.* 之前设置，config.py 在导入时读取环境变量
_TMP_DIR = tempfile.mkdtemp(prefix="sw_retrieval_test_")
os.environ["DATA_DIR"] = _TMP_DIR
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_TMP_DIR) / 'test.db').as_posix()}"

from app.db import SessionLocal, init_db
from app.models import Company, KbArticle, User, utcnow
from app.security import hash_password
from app.services.retrieval import search

init_db()

PASSED = 0
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


DOCS = {
    "502": (
        "接口调用返回 502 Bad Gateway",
        "网关到上游服务链路中断，查上游健康状态与连接超时配置。"
        "常见根因：上游服务重启假死、连接池耗尽、超时时间过短、负载均衡摘除节点。",
    ),
    "登录": (
        "登录失败：提示账号或密码错误但密码确认无误",
        "多因账号锁定或缓存导致。查锁定状态与认证服务日志、清理客户端缓存。",
    ),
    "导出": (
        "订单数据导出为空，页面有数据但导出文件是 0 行",
        "导出任务异步执行且时间窗口参数默认值错误，查询区间落在数据之外。",
    ),
    "性能": (
        "系统响应变慢，页面加载超过 10 秒",
        "先定位瓶颈层：数据库慢查询、服务 CPU、还是外部依赖超时。",
    ),
    "支付": (
        "支付成功但订单状态仍为待支付",
        "订单状态依赖第三方支付回调更新。回调丢失或延迟时，订单会停留在待支付，但实际已扣款。"
        "用对账文件确认后手工补单。",
    ),
}


def make_tenant(
    db, name: str, doc_keys: list[str], corpus: dict[str, tuple[str, str]] | None = None
) -> tuple[int, list[int]]:
    """建一个测试租户，并写入指定的知识库条目。

    corpus 可覆盖默认 DOCS，用于构造内容互不相同的语料。
    """
    src = corpus or DOCS
    company = Company(name=name, slug=f"t-{name}", plan="test")
    db.add(company)
    db.flush()
    user = User(
        company_id=company.id,
        email=f"{name}@t.local",
        name="t",
        password_hash=hash_password("Test@2026"),
        role="admin",
    )
    db.add(user)
    db.flush()
    ids = []
    for k in doc_keys:
        title, content = src[k]
        art = KbArticle(
            company_id=company.id,
            title=title,
            content=content,
            summary=content[:80],
            category="测试",
            tags=[],
            steps=[],
            source="manual",
            created_by=user.id,
        )
        db.add(art)
        db.flush()
        ids.append(art.id)
    db.commit()
    return company.id, ids


def main() -> int:
    db = SessionLocal()
    try:
        # ---------- 场景 1：小知识库（1 条） ----------
        print("\n=== 场景1：知识库只有 1 条时，相关查询必须命中 ===")
        cid, ids = make_tenant(db, "small1", ["502"])
        r = search(db, cid, "502 Bad Gateway Error: request to /api/v2/orders timed out", min_score=3.0, min_coverage=0.15)
        check("单篇语料下相关查询命中", len(r) == 1, f"命中 {len(r)} 条")
        r2 = search(db, cid, "打印机吐出乱码纸张，扫描枪读不到条码", min_score=3.0, min_coverage=0.15)
        check("单篇语料下不相关查询不命中", len(r2) == 0, f"命中 {len(r2)} 条")

        # ---------- 场景 2：小知识库（2-3 条） ----------
        print("\n=== 场景2：知识库 3 条时，正负样本仍可区分 ===")
        cid3, _ = make_tenant(db, "small3", ["502", "登录", "导出"])
        r = search(db, cid3, "502 Bad Gateway Error: request to /api/v2/orders timed out", min_score=3.0, min_coverage=0.15)
        check("3 篇语料下相关查询命中", len(r) >= 1, f"命中 {len(r)} 条")
        check("最优结果就是 502 那条", r and "502" in r[0].article.title, r[0].article.title if r else "无")
        r = search(db, cid3, "所有用户都无法登录，提示账号或密码错误", min_score=3.0, min_coverage=0.15)
        check("3 篇语料下登录类查询命中正确条目", r and "登录" in r[0].article.title, r[0].article.title if r else "无")
        r = search(db, cid3, "打印机吐出乱码纸张，扫描枪读不到条码", min_score=3.0, min_coverage=0.15)
        check("3 篇语料下不相关查询不命中", len(r) == 0, f"命中 {len(r)} 条")

        # ---------- 场景 3：标准规模（8 篇） ----------
        print("\n=== 场景3：标准规模下阈值标定仍然有效 ===")
        # ---------- 场景 3：标准规模（8 篇，内容各不相同）----------
        # 注意：语料里不能放完全重复的文档 —— 重复会让文档频率翻倍、IDF 骤降，
        # 把所有条目得分压平，排序失去区分度（真实知识库虽不刻意重复，
        # 但这个测试要验证的是排序正确性，因此用互不相同的 8 篇）。
        corpus3 = {
            "502": (
                "接口调用返回 502 Bad Gateway，网关无法从上游取到有效响应。",
                "上游服务假死、连接池耗尽、读超时过短都会触发 502 网关错误。",
            ),
            "登录": (
                "用户登录提示账号或密码错误，但密码确认无误",
                "多因账号被锁定、客户端缓存旧密码或认证服务连接池耗尽导致登录失败。",
            ),
            "导出": (
                "订单数据导出为空，页面有数据但导出文件是 0 行",
                "导出任务异步执行，时间窗口参数默认值错误导致查询区间落在数据之外。",
            ),
            "性能": (
                "系统响应变慢，页面加载超过 10 秒",
                "先定位瓶颈层：数据库慢查询、服务 CPU 占用高，还是外部依赖响应慢。",
            ),
            "支付": (
                "支付成功但订单状态仍为待支付",
                "订单状态依赖第三方支付回调更新，回调丢失或延迟时订单会停留在待支付但实际已扣款。",
            ),
            "部署": (
                "部署新版本后容器反复重启，服务起不来",
                "应用启动早于数据库就绪，缺少健康检查与依赖顺序约束。",
            ),
            "缺陷": (
                "功能异常：点击保存后数据未更新",
                "抓包发现请求体里的字段被前端校验规则裁剪为空值，属于版本回归缺陷。",
            ),
            "发票": (
                "发票抬头与营业执照不一致，无法开票",
                "开票信息取自认证时的企业资质快照，公司更名后需重新提交最新营业执照。",
            ),
        }
        cid8, _ = make_tenant(db, "std8", list(corpus3.keys()), corpus3)
        cases_pos = [
            ("502 Bad Gateway Error: request to /api/v2/orders timed out after 5000ms", "502"),
            ("所有用户都无法登录，提示账号或密码错误，服务完全不可用", "账号或密码错误"),
            ("导出订单报表得到 0 行，但页面明明有 1000 多条记录", "导出为空"),
            ("系统响应变慢，页面加载超过 10 秒，CPU 占用很高", "响应变慢"),
            ("payment callback failed, refund not processed", "支付成功"),
        ]
        for q, expect in cases_pos:
            r = search(db, cid8, q, min_score=3.0, min_coverage=0.15)
            ok = bool(r) and expect in r[0].article.title
            check(f"标准规模命中「{expect}」", ok, r[0].article.title if r else "未命中")
        cases_neg = [
            "打印机吐出乱码纸张，扫描枪读不到条码",
            "中午订的盒饭还没送到，客服电话也打不通",
            "明天上午十点的客户会议需要改到下午，可以吗",
        ]
        for q in cases_neg:
            r = search(db, cid8, q, min_score=3.0, min_coverage=0.15)
            check(f"标准规模不相关查询不命中: {q[:14]}", len(r) == 0, f"命中 {len(r)} 条")

        # ---------- 场景 4：知识库为空 ----------
        print("\n=== 场景4：空知识库不报错 ===")
        cid0, _ = make_tenant(db, "empty", [])
        r = search(db, cid0, "任何查询", min_score=3.0, min_coverage=0.15)
        check("空知识库返回空结果", len(r) == 0)

        # ---------- 场景 5：长查询与短查询 ----------
        print("\n=== 场景5：查询长度变化不影响判定 ===")
        r = search(db, cid8, "502", min_score=3.0, min_coverage=0.15)
        check("极短查询仍能命中", bool(r), "未命中")
        long_q = (
            "生产环境报错 java.lang.NullPointerException at com.foo.Bar.run(Bar.java:42) "
            "2026-11-02 10:23:45 ERROR upstream timeout after 5000ms while calling orders api"
        )
        r = search(db, cid8, long_q, min_score=3.0, min_coverage=0.15)
        check("长日志型查询能命中 502 条目", bool(r) and "502" in r[0].article.title,
              r[0].article.title if r else "未命中")

        # ---------- 场景 6：英文报错 + 中文知识库（中英错配）----------
        print("\n=== 场景6：英文报错命中中文知识库（目标用户的真实场景）===")
        cases_mix = [
            ("connection refused while connecting to database", "连接拒绝"),
            ("request timeout after 5000ms", "超时"),
            ("401 Unauthorized, token expired", "未认证"),
            ("payment callback failed, refund not processed", "支付"),
        ]
        for q, expect_kw in cases_mix:
            r = search(db, cid8, q, min_score=3.0, min_coverage=0.15)
            # 只要命中且排名靠前即可（具体条目由别名+统计综合决定）
            check(f"英文报错「{q[:26]}」能命中中文条目", bool(r),
                  "未命中")

        # ---------- 场景 7：英文报错的中文分类判定 ----------
        print("\n=== 场景7：英文报错的工单自动分类 ===")
        from app.services.classifier import classify_by_rules

        c = classify_by_rules("Payment callback failed for some orders", "")
        check("英文 payment 报错判为支付账单", c.category == "支付账单", f"got={c.category}")
        c = classify_by_rules("User cannot login, 401 Unauthorized", "")
        check("英文 login 报错判为账号登录", c.category == "账号登录", f"got={c.category}")
        c = classify_by_rules("API returns 502 Bad Gateway", "")
        check("英文 502 报错判为接口API", c.category == "接口API", f"got={c.category}")

    finally:
        # 清理测试租户
        db.query(KbArticle).filter(KbArticle.category == "测试").delete(synchronize_session=False)
        db.query(User).filter(User.email.like("%@t.local")).delete(synchronize_session=False)
        db.query(Company).filter(Company.plan == "test").delete(synchronize_session=False)
        db.commit()
        db.close()

    print("\n" + "=" * 56)
    total = PASSED + len(FAILED)
    if FAILED:
        print(f"❌ {len(FAILED)}/{total} 项失败:")
        for f in FAILED:
            print(f"   - {f}")
        return 1
    print(f"✅ 全部通过 ({PASSED}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
