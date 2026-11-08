"""工单附件接口。

路由挂在 /api/tickets/{ticket_id}/attachments 下，复用工单的存在性与租户校验逻辑。

安全要点（对应 issue #15）：
- 上传时校验扩展名 + 魔数，改扩展名骗不过去
- 存储路径随机生成，杜绝路径穿越
- 下载强制 attachment + nosniff，上传的 HTML 不会被浏览器执行
- 所有操作都做租户隔离：跨租户访问返回 404
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import (
    ATTACHMENT_ALLOWED_TYPES,
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_MAX_FILES_PER_TICKET,
)
from ..db import get_db
from ..deps import get_current_user
from ..models import Ticket, TicketAttachment, User
from ..storage import (
    AttachmentError,
    check_count,
    check_size,
    delete_stored,
    detect_content_type,
    format_size,
    guess_download_type,
    resolve_extension,
    store_file,
    stored_path,
)

router = APIRouter(prefix="/api/tickets", tags=["attachments"])

# 允许的扩展名全集（用于错误提示）
_ALLOWED_EXTENSIONS = sorted(
    {ext for exts in ATTACHMENT_ALLOWED_TYPES.values() for ext in exts}
)


def _ascii_fallback(name: str) -> str:
    """
    生成 ASCII 回退文件名。

    老浏览器不认 RFC 5987 的 filename*，只认 filename=。
    中文名转不出来时用 "attachment" 兜底，绝不返回空。
    """
    # NFKD 分解后去掉重音，中文等非拉丁字符会变成空
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    # 清掉可能破坏 header 的字符
    ascii_only = ascii_only.replace('"', "").replace("\\", "").strip()
    ascii_only = ascii_only.replace(";", "_").replace(",", "_")
    # 有主体名就用它（主体不能只是前导点，如 ".png" 算没有主体）
    stem, _ = os.path.splitext(ascii_only)
    if stem and not stem.startswith("."):
        return ascii_only
    # 主体名被剥光（如「截图.png」→「.png」）→ 用 attachment + 扩展名
    _, ext = os.path.splitext(name)
    ext = ext if ext.isascii() and len(ext) <= 16 else ""
    return f"attachment{ext}"


def _get_ticket_or_404(ticket_id: int, company_id: int, db: Session) -> Ticket:
    """取工单；不存在或不属于当前租户都返回 404（不泄露存在性）。"""
    ticket = db.scalar(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.company_id == company_id)
    )
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    return ticket


def _to_dict(att: TicketAttachment) -> dict:
    return {
        "id": att.id,
        "ticket_id": att.ticket_id,
        "original_name": att.original_name,
        "content_type": att.content_type,
        "size": att.size,
        "size_display": format_size(att.size),
        "sha256": att.sha256,
        "uploader_name": att.uploader.name if att.uploader else "未知",
        "created_at": att.created_at.isoformat() if att.created_at else None,
        "download_url": f"/api/tickets/{att.ticket_id}/attachments/{att.id}/download",
    }


@router.get("/{ticket_id}/attachments")
def list_attachments(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出工单的附件。"""
    ticket = _get_ticket_or_404(ticket_id, user.company_id, db)
    rows = db.scalars(
        select(TicketAttachment)
        .where(TicketAttachment.ticket_id == ticket.id)
        .order_by(TicketAttachment.id)
    ).all()
    return {
        "total": len(rows),
        "max_files": ATTACHMENT_MAX_FILES_PER_TICKET,
        "max_bytes": ATTACHMENT_MAX_BYTES,
        "allowed_extensions": _ALLOWED_EXTENSIONS,
        "items": [_to_dict(a) for a in rows],
    }


@router.post("/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    上传附件。

    单个文件一个请求。类型与大小校验失败返回 400。
    """
    ticket = _get_ticket_or_404(ticket_id, user.company_id, db)

    # 数量上限
    current = db.scalar(
        select(func.count(TicketAttachment.id)).where(TicketAttachment.ticket_id == ticket.id)
    ) or 0
    try:
        check_count(current)
    except AttachmentError as e:
        raise HTTPException(e.status_code, e.message) from e

    original_name = (file.filename or "").strip() or "unnamed"
    extension = resolve_extension(original_name)

    # 扩展名先过一道
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"不支持的文件类型「{extension or '无扩展名'}」。"
            f"允许的类型：{', '.join(_ALLOWED_EXTENSIONS)}",
        )

    # 落到临时文件再校验内容 —— 不信任任何客户端声明
    tmp_dir = Path(tempfile.mkdtemp(prefix="polaris-upload-"))
    tmp_path = tmp_dir / "upload.bin"
    try:
        # 表单解析后文件指针已在末尾，必须先归零，否则读出来是空的
        await file.seek(0)
        written = 0
        with tmp_path.open("wb") as out:
            while chunk := await file.read(1024 * 64):
                written += len(chunk)
                # 边写边判大小，避免超大文件把磁盘写满
                if written > ATTACHMENT_MAX_BYTES:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"文件超过 {ATTACHMENT_MAX_BYTES / 1024 / 1024:.0f} MB 上限",
                    )
                out.write(chunk)

        try:
            check_size(written)
        except AttachmentError as e:
            raise HTTPException(e.status_code, e.message) from e

        # 魔数校验：扩展名说的和内容说的必须一致
        actual_type = detect_content_type(tmp_path, extension)
        if actual_type is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"文件内容与扩展名「{extension}」不匹配，已拒绝。"
                f"请确认文件确实是声明的类型。",
            )

        stored = store_file(tmp_path, original_name)
    except HTTPException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except AttachmentError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(e.status_code, e.message) from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    att = TicketAttachment(
        ticket_id=ticket.id,
        company_id=user.company_id,
        uploader_id=user.id,
        stored_name=stored.stored_name,
        original_name=original_name[:255],
        content_type=stored.content_type,
        size=stored.size,
        sha256=stored.sha256,
    )
    db.add(att)
    db.flush()

    return _to_dict(att)


@router.get("/{ticket_id}/attachments/{attachment_id}/download")
def download_attachment(
    ticket_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    下载附件。

    强制以附件形式返回：即使上传的是 HTML 或 SVG，浏览器也不会执行其中的脚本。
    """
    _get_ticket_or_404(ticket_id, user.company_id, db)
    att = db.scalar(
        select(TicketAttachment).where(
            TicketAttachment.id == attachment_id,
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == user.company_id,
        )
    )
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "附件不存在")

    path = stored_path(att.stored_name)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "附件文件已丢失")

    # HTTP header 只能用 latin-1 编码，中文文件名会直接抛 UnicodeEncodeError。
    # 正确做法是 RFC 5987：filename 放 ASCII 回退名，filename* 放 UTF-8 编码的完整名。
    safe_name = att.original_name.replace("\r", "").replace("\n", "")
    ascii_fallback = _ascii_fallback(safe_name)
    encoded = quote(safe_name, safe="")
    disposition = (
        f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
    )

    return FileResponse(
        path,
        media_type=guess_download_type(att.stored_name, att.content_type),
        headers={
            # attachment：强制下载，不在浏览器内渲染
            "Content-Disposition": disposition,
            # 禁止浏览器嗅探类型
            "X-Content-Type-Options": "nosniff",
            # 附件是用户上传的内容，禁止被当作活动内容
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/{ticket_id}/attachments/{attachment_id}")
def delete_attachment(
    ticket_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除附件（同时删除磁盘文件）。"""
    _get_ticket_or_404(ticket_id, user.company_id, db)
    att = db.scalar(
        select(TicketAttachment).where(
            TicketAttachment.id == attachment_id,
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.company_id == user.company_id,
        )
    )
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "附件不存在")

    delete_stored(att.stored_name)
    db.delete(att)
    db.flush()
    return {"ok": True, "deleted_id": attachment_id}
