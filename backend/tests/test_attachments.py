"""附件安全测试。

重点验证「改扩展名骗不过去」这条核心防线，以及路径穿越、跨租户隔离。

跑法：python tests/test_attachments.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 必须在导入 app.* 之前设置 —— config.py 在导入时读取环境变量
_TMP_DIR = tempfile.mkdtemp(prefix="sw_att_test_")
os.environ["DATA_DIR"] = _TMP_DIR
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_TMP_DIR) / 'test.db').as_posix()}"
os.environ["ATTACHMENT_DIR"] = str(Path(_TMP_DIR) / "attachments")

from app.db import SessionLocal, init_db
from app.models import Company, Ticket, TicketAttachment, User, utcnow
from app.security import hash_password
from app.storage import (
    AttachmentError,
    build_stored_name,
    check_count,
    check_size,
    delete_stored,
    detect_content_type,
    guess_download_type,
    resolve_extension,
    store_file,
    stored_path,
)

init_db()

# ---------- 测试用的假文件内容 ----------

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF_BYTES = b"GIF89a" + b"\x00" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"\x00" * 64
ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 64
TEXT_BYTES = "订单导出报错\nTraceback...\n".encode("utf-8")
# 可执行文件的真实魔数（PE 头）
EXE_BYTES = b"MZ\x90\x00" + b"\x00" * 64
# HTML 里带脚本
HTML_BYTES = b"<html><script>alert(1)</script></html>"


def _write(name: str, data: bytes) -> Path:
    """写一个临时文件返回路径。"""
    p = Path(_TMP_DIR) / name
    p.write_bytes(data)
    return p


# ---------- 测试用例 ----------


def test_detect_png_by_magic():
    """PNG 用魔数识别。"""
    p = _write("a.png", PNG_BYTES)
    assert detect_content_type(p, ".png") == "image/png"


def test_detect_jpeg_by_magic():
    """JPEG 用魔数识别。"""
    p = _write("a.jpg", JPEG_BYTES)
    assert detect_content_type(p, ".jpg") == "image/jpeg"


def test_detect_pdf_by_magic():
    """PDF 用魔数识别。"""
    p = _write("a.pdf", PDF_BYTES)
    assert detect_content_type(p, ".pdf") == "application/pdf"


def test_detect_zip_by_magic():
    """ZIP 用魔数识别。"""
    p = _write("a.zip", ZIP_BYTES)
    assert detect_content_type(p, ".zip") == "application/zip"


def test_detect_text():
    """纯文本按内容判断（无魔数）。"""
    p = _write("a.txt", TEXT_BYTES)
    assert detect_content_type(p, ".txt") == "text/plain"


def test_reject_renamed_exe_as_png():
    """核心防线：把 exe 改名成 png 必须被拒。"""
    p = _write("evil.png", EXE_BYTES)
    assert detect_content_type(p, ".png") is None


def test_reject_renamed_html_as_png():
    """HTML 改名成 png 必须被拒。"""
    p = _write("xss.png", HTML_BYTES)
    assert detect_content_type(p, ".png") is None


def test_reject_renamed_png_as_exe():
    """反向也不行：png 改名成 exe，扩展名白名单本身就拦住了。"""
    p = _write("fake.exe", PNG_BYTES)
    assert detect_content_type(p, ".exe") is None


def test_reject_svg():
    """SVG 不在白名单 —— SVG 可内嵌脚本，浏览器直接打开会执行。"""
    p = _write("a.svg", b"<svg onload='alert(1)'></svg>")
    assert detect_content_type(p, ".svg") is None


def test_reject_binary_as_text():
    """二进制内容不能伪装成 txt。"""
    p = _write("a.txt", EXE_BYTES)
    assert detect_content_type(p, ".txt") is None


def test_stored_name_is_random_and_safe():
    """存储文件名必须随机且不含路径分隔符。"""
    names = {build_stored_name(".png") for _ in range(50)}
    assert len(names) == 50, "文件名必须唯一"
    for n in names:
        assert "/" not in n and "\\" not in n and ".." not in n
        assert len(n) == 32 + 4  # 32 位 hex + 扩展名


def test_resolve_extension_limits():
    """扩展名提取与长度限制。"""
    assert resolve_extension("a.PNG") == ".png"
    assert resolve_extension("noext") == ""
    # 超长扩展名被截断到 16 字符
    long_ext = resolve_extension("a." + "x" * 100)
    assert len(long_ext) == 16
    assert long_ext.startswith(".x")


def test_check_size_rejects_oversize():
    """超限文件被拒。"""
    try:
        check_size(100 * 1024 * 1024)
        raise AssertionError("超大文件应被拒绝")
    except AttachmentError as e:
        assert "上限" in e.message


def test_check_size_rejects_empty():
    """空文件被拒。"""
    try:
        check_size(0)
        raise AssertionError("空文件应被拒绝")
    except AttachmentError:
        pass


def test_check_count_limit():
    """单工单附件数量上限。"""
    try:
        check_count(10)
        raise AssertionError("超量应被拒绝")
    except AttachmentError as e:
        assert e.status_code == 409


def test_stored_path_blocks_traversal():
    """路径穿越必须被挡住。"""
    assert stored_path("../../etc/passwd") is None
    assert stored_path("..\\..\\windows\\system32") is None
    assert stored_path("subdir/file.png") is None
    assert stored_path("") is None


def test_delete_stored_blocks_traversal():
    """删除也要挡路径穿越。"""
    assert delete_stored("../../important.txt") is False
    assert delete_stored("a/b.png") is False


def test_store_and_delete_roundtrip():
    """存盘 → 元数据 → 删除 的完整流程。"""
    src = _write("roundtrip.png", PNG_BYTES)
    stored = store_file(src, "原始名称.png")
    assert stored.original_name == "原始名称.png"
    assert stored.content_type == "image/png"
    assert stored.size == len(PNG_BYTES)
    assert len(stored.sha256) == 64
    # 磁盘上的文件名与原始名无关
    assert "原始名称" not in stored.stored_name
    assert stored_path(stored.stored_name) is not None
    assert delete_stored(stored.stored_name) is True
    assert stored_path(stored.stored_name) is None


def test_download_type_forces_attachment_for_text():
    """文本类文件下载时降级为 octet-stream，配合 attachment 头强制下载。"""
    assert guess_download_type("x.txt", "text/plain") == "application/octet-stream"
    assert guess_download_type("x.log", "text/plain") == "application/octet-stream"
    # 图片和 PDF 保持原类型（浏览器可直接看）
    assert guess_download_type("x.png", "image/png") == "image/png"
    assert guess_download_type("x.pdf", "application/pdf") == "application/pdf"


def test_download_type_blocks_html_render():
    """HTML 即使内容类型是 text/html，下载时也必须是 octet-stream。"""
    assert guess_download_type("x.html", "text/html") == "application/octet-stream"


def test_tenant_isolation_on_attachment_query():
    """跨租户查不到附件。"""
    db = SessionLocal()
    try:
        c1 = Company(name="公司A", slug="a", plan="trial")
        c2 = Company(name="公司B", slug="b", plan="trial")
        db.add_all([c1, c2])
        db.flush()
        u1 = User(
            company_id=c1.id,
            name="A管理员",
            email="a@example.com",
            password_hash=hash_password("x123456"),
            role="admin",
        )
        db.add(u1)
        db.flush()
        t1 = Ticket(company_id=c1.id, code="TK-0001", title="A公司的工单")
        db.add(t1)
        db.flush()
        att = TicketAttachment(
            ticket_id=t1.id,
            company_id=c1.id,
            uploader_id=u1.id,
            stored_name="test_attachment_isolation.png",
            original_name="a.png",
            content_type="image/png",
            size=10,
        )
        db.add(att)
        db.commit()

        from sqlalchemy import select

        # 公司 B 查不到公司 A 的附件
        found = db.scalars(
            select(TicketAttachment).where(
                TicketAttachment.id == att.id, TicketAttachment.company_id == c2.id
            )
        ).all()
        assert len(found) == 0, "跨租户不应查到附件"
    finally:
        db.close()


if __name__ == "__main__":
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures.append(name)
                print(f"  FAIL  {name}: {e}")
            except Exception as e:  # noqa: BLE001
                failures.append(name)
                print(f"  ERROR {name}: {e}")
    print()
    if failures:
        print(f"❌ {len(failures)} 个用例失败: {', '.join(failures)}")
        sys.exit(1)
    print("✅ 全部通过")
