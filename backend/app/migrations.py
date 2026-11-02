"""轻量数据库迁移。

SQLite + SQLAlchemy 的 `create_all` 只会建新表，不会给已有表加列。
本模块在应用启动时检查并补齐缺失的列（幂等，可重复执行）。

生产环境若表结构变化较大，建议改用 Alembic；当前规模用这个够用。
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .db import engine as default_engine

# 表名 -> [(列名, DDL 类型), ...]
EXPECTED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "companies": [
        ("work_schedule", "JSON"),
    ],
}


def _existing_columns(engine: Engine, table: str) -> set[str]:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def run_migrations(engine: Engine | None = None) -> list[str]:
    """检查并补齐缺失列，返回本次执行的变更说明列表。"""
    eng = engine or default_engine
    changes: list[str] = []
    with eng.begin() as conn:
        for table, columns in EXPECTED_COLUMNS.items():
            existing = _existing_columns(eng, table)
            if not existing:
                # 表不存在，说明是全新库，create_all 会按模型建好
                continue
            for col_name, col_type in columns:
                if col_name in existing:
                    continue
                ddl = f'ALTER TABLE {table} ADD COLUMN "{col_name}" {col_type}'
                conn.execute(text(ddl))
                changes.append(f"{table}.{col_name} ({col_type})")
    return changes


if __name__ == "__main__":
    from .db import init_db

    init_db()
    result = run_migrations()
    if result:
        print("已执行迁移：")
        for c in result:
            print("  +", c)
    else:
        print("数据库结构已是最新，无需迁移。")
