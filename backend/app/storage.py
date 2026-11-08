"""附件存储：落盘、类型校验、路径生成。

安全设计（对应 issue #15 的要求）：

1. **类型白名单不靠扩展名**。上传时同时检查：
   - 扩展名是否在白名单内
   - 文件头的魔数（magic number）是否与该类型匹配
   两者都通过才接受。改扩展名骗不过去 —— 把 `.exe` 改名成 `.png` 会被魔数检查拦下。

2. **存储路径不可预测**。文件名用 `secrets.token_hex(16)` 生成随机串，
   不含用户输入的任何字符，从根本上排除路径穿越（`../`）的可能。
   原始文件名只作为元数据存在数据库里，永远不参与路径拼接。

3. **下载不执行**。下载接口固定返回 `Content-Disposition: attachment`
   与 `X-Content-Type-Options: nosniff`，浏览器不会把上传的 HTML/SVG
   当作页面渲染，避免存储型 XSS。

4. **原子写入**。先写临时文件再 `os.replace`，避免写入中断留下半截文件。

允许的类型刻意保守 —— 排障场景真正需要的是截图和日志。
SVG 刻意不放开：SVG 是 XML，可以内嵌脚本，浏览器直接打开会执行。
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from .config import (
    ATTACHMENT_DIR,
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_MAX_FILES_PER_TICKET,
    ATTACHMENT_ALLOWED_TYPES,
)

# 魔数签名：(前缀字节, 偏移) —— 取前缀比对
_MAGIC_SIGNATURES: dict[str, list[tuple[bytes, int]]] = {
    "image/png": [(b"\x89PNG\r\n\x1a\n", 0)],
    "image/jpeg": [(b"\xff\xd8\xff", 0)],
    "image/gif": [(b"GIF87a", 0), (b"GIF89a", 0)],
    "image/webp": [(b"RIFF", 0)],  # 还需 WEBP 标记，见 _matches_webp
    "application/pdf": [(b"%PDF-", 0)],
    "text/plain": [],  # 纯文本无魔数，靠「不是二进制」判断
    "application/zip": [(b"PK\x03\x04", 0), (b"PK\x05\x06", 0), (b"PK\x07\x08", 0)],
}

# ZIP 容器里的办公文档（本质是 zip，但用户期望用 docx/xlsx 的扩展名）
_ZIP_BASED_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".odt", ".ods"}


class AttachmentError(Exception):
    """附件校验或存储失败。message 会直接返回给客户端。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class StoredFile:
    """落盘结果。"""

    stored_name: str  # 磁盘上的随机文件名
    original_name: str  # 用户上传时的文件名
    content_type: str  # 校验后的 MIME
    size: int
    sha256: str


def _read_head(path: Path, size: int = 32) -> bytes:
    """读取文件头，用于魔数嗅探。"""
    try:
        with path.open("rb") as f:
            return f.read(size)
    except OSError:
        return b""


def _matches_webp(head: bytes) -> bool:
    """WebP 是 RIFF 容器，需额外检查 8-12 字节处的 WEBP 标记。"""
    return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def _looks_like_text(head: bytes) -> bool:
    """粗判是否为文本：不含 NUL 字节，且可解码为 UTF-8。"""
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def detect_content_type(path: Path, extension: str) -> str | None:
    """
    根据文件内容判断真实类型，与扩展名声明的类型比对。

    返回校验通过的类型；不匹配则返回 None。
    """
    allowed = ATTACHMENT_ALLOWED_TYPES
    head = _read_head(path)

    # 先按扩展名找到期望的类型
    expected: str | None = None
    for mime, exts in allowed.items():
        if extension in exts:
            expected = mime
            break
    if expected is None:
        return None

    # 声明为 text/plain：检查是否像文本
    if expected == "text/plain":
        return expected if _looks_like_text(head) else None

    # ZIP 系：docx/xlsx/pptx 本质是 zip
    if expected == "application/zip" or extension in _ZIP_BASED_EXTENSIONS:
        is_zip = any(head.startswith(sig, off) for sig, off in _MAGIC_SIGNATURES["application/zip"])
        if not is_zip:
            return None
        if extension in _ZIP_BASED_EXTENSIONS:
            # 扩展名声称是 office 文档，内容需确实是 zip
            return expected if expected == "application/zip" else expected
        return "application/zip"

    # WebP 特殊处理
    if expected == "image/webp":
        return expected if _matches_webp(head) else None

    # 其余按魔数比对
    signatures = _MAGIC_SIGNATURES.get(expected, [])
    if not signatures:
        return None
    for sig, off in signatures:
        if head[off : off + len(sig)] == sig:
            return expected
    return None


def build_stored_name(extension: str) -> str:
    """
    生成不可预测的存储文件名。

    用随机十六进制串，绝不包含用户输入 —— 从根本上排除路径穿越。
    文件名格式：<32位随机hex><扩展名>
    """
    return f"{secrets.token_hex(16)}{extension}"


def resolve_extension(filename: str) -> str:
    """取扩展名并小写化；无扩展名返回空串。"""
    ext = os.path.splitext(filename or "")[1].lower()
    # 限制长度，避免超长扩展名
    return ext[:16]


def check_size(size: int) -> None:
    """大小超限则抛错。"""
    if size <= 0:
        raise AttachmentError("文件为空，无法上传")
    if size > ATTACHMENT_MAX_BYTES:
        mb = ATTACHMENT_MAX_BYTES / 1024 / 1024
        raise AttachmentError(f"文件超过 {mb:.0f} MB 上限")


def check_count(current: int) -> None:
    """单工单附件数量超限则抛错。"""
    if current >= ATTACHMENT_MAX_FILES_PER_TICKET:
        raise AttachmentError(
            f"单个工单最多 {ATTACHMENT_MAX_FILES_PER_TICKET} 个附件", status_code=409
        )


def ensure_dir() -> Path:
    """确保存储目录存在并返回。"""
    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    return ATTACHMENT_DIR


def store_file(source_path: Path, original_name: str) -> StoredFile:
    """
    把已落地的临时文件转存为正式附件。

    调用前应已通过 detect_content_type 校验。
    """
    extension = resolve_extension(original_name)
    stored_name = build_stored_name(extension)
    target = ensure_dir() / stored_name

    size = source_path.stat().st_size
    check_size(size)

    digest = hashlib.sha256()
    with source_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 64), b""):
            digest.update(chunk)

    # 原子替换：先写临时文件再改名，避免留下半截文件
    tmp_target = target.with_suffix(target.suffix + ".part")
    os.replace(source_path, tmp_target)
    os.replace(tmp_target, target)

    content_type = detect_content_type(target, extension) or "application/octet-stream"
    return StoredFile(
        stored_name=stored_name,
        original_name=original_name,
        content_type=content_type,
        size=size,
        sha256=digest.hexdigest(),
    )


def delete_stored(stored_name: str) -> bool:
    """删除磁盘上的文件。返回是否实际删除。"""
    # 只接受我们生成的格式，防止传入路径
    if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
        return False
    path = ATTACHMENT_DIR / stored_name
    try:
        path.unlink()
        return True
    except OSError:
        return False


def stored_path(stored_name: str) -> Path | None:
    """取存储路径；文件名不合法或文件不存在则返回 None。"""
    if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
        return None
    path = ATTACHMENT_DIR / stored_name
    # 双保险：确保最终路径确实在存储目录内
    try:
        path.resolve().relative_to(ATTACHMENT_DIR.resolve())
    except (ValueError, OSError):
        return None
    return path if path.exists() else None


def guess_download_type(stored_name: str, content_type: str) -> str:
    """
    下载时使用的 MIME。

    对可能被浏览器渲染的类型，统一降级为 application/octet-stream，
    配合 Content-Disposition: attachment 强制下载。
    """
    if content_type in ("image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"):
        return content_type
    ext = os.path.splitext(stored_name)[1].lower()
    guessed = mimetypes.guess_type(f"x{ext}")[0]
    if guessed in ("image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"):
        return guessed
    return "application/octet-stream"


def format_size(size: int) -> str:
    """人类可读的体积。"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
