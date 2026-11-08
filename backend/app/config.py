"""全局配置：全部通过环境变量注入，密钥不进代码库。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---- 基础 ----
APP_NAME = "Polaris 北极星 · 客服工单管理平台"
APP_VERSION = "1.2.0"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-in-production")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "72"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# ---- 数据库 ----
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'support.db').as_posix()}")

# ---- LLM（可选，OpenAI 兼容协议；未配置则自动降级为本地规则引擎）----
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
# 供应商关键字白名单：命中则启用 LLM
LLM_ENABLED = bool(LLM_BASE_URL and LLM_API_KEY)

# ---- SLA 策略（按优先级，单位：工作分钟）----
# 工作时间：周一至周五 09:00-18:00（每天 9 个工作小时）
# 注意：这里是"默认"值。每家企业可通过环境变量覆盖，以适配不同排班
# （例如周六也上班的团队）。
WORK_START_HOUR = 9
WORK_END_HOUR = 18
WORK_DAYS = {0, 1, 2, 3, 4}  # 周一=0

# 每租户可覆盖的工作时间表，存于 Company.work_schedule，格式：
# {
#   "work_days": [0,1,2,3,4,5],      # 周一=0
#   "work_start_hour": 9,
#   "work_end_hour": 18
# }
# 为空时回落到上面的全局默认值。

SLA_POLICY: dict[str, dict[str, int]] = {
    "P1": {"response": 30, "resolve": 240, "label": "致命中断"},
    "P2": {"response": 120, "resolve": 960, "label": "严重"},
    "P3": {"response": 480, "resolve": 2880, "label": "一般"},
    "P4": {"response": 1440, "resolve": 6720, "label": "低"},
}
DEFAULT_PRIORITY = "P3"

# ---- 附件上传 ----
# 存储目录：默认在 DATA_DIR 下，可用环境变量单独指定
ATTACHMENT_DIR = Path(os.getenv("ATTACHMENT_DIR", str(DATA_DIR / "attachments")))
ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)

# 单文件大小上限（默认 10 MB）
ATTACHMENT_MAX_BYTES = int(os.getenv("ATTACHMENT_MAX_BYTES", str(10 * 1024 * 1024)))
# 单工单附件数量上限
ATTACHMENT_MAX_FILES_PER_TICKET = int(os.getenv("ATTACHMENT_MAX_FILES_PER_TICKET", "10"))

# 类型白名单：MIME -> 允许的扩展名
# 刻意保守 —— 排障真正需要的是截图和日志。
# 不含 SVG：SVG 是 XML，可内嵌脚本，浏览器直接打开会执行（存储型 XSS）。
ATTACHMENT_ALLOWED_TYPES: dict[str, set[str]] = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
    "text/plain": {".txt", ".log", ".md", ".csv", ".json", ".yaml", ".yml", ".xml"},
    "application/zip": {".zip", ".docx", ".xlsx", ".pptx", ".odt", ".ods"},
}

# ---- 工单分类字典 ----
TICKET_CATEGORIES = [
    "账号登录",
    "支付账单",
    "接口API",
    "数据问题",
    "性能卡顿",
    "部署运维",
    "功能缺陷",
    "咨询其他",
]

# ---- 工单状态机 ----
TICKET_STATUSES = ["new", "triaged", "in_progress", "pending", "resolved", "closed"]
STATUS_LABELS = {
    "new": "待受理",
    "triaged": "已分类",
    "in_progress": "处理中",
    "pending": "待客户",
    "resolved": "已解决",
    "closed": "已关闭",
}
# 允许的状态流转
STATUS_TRANSITIONS: dict[str, list[str]] = {
    "new": ["triaged", "in_progress", "pending", "resolved", "closed"],
    "triaged": ["in_progress", "pending", "resolved", "closed"],
    "in_progress": ["pending", "resolved", "closed"],
    "pending": ["in_progress", "resolved", "closed"],
    "resolved": ["closed", "in_progress"],  # 允许重新打开
    "closed": ["in_progress"],  # 允许重开
}
