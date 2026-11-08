"""统一测试入口。

用法：
    python tests/run_all.py

包含四组测试：
- test_sla.py         SLA 工作时间计算（30 项）
- test_retrieval.py   检索质量与相关性判据（24 项）
- test_attachments.py 附件安全校验（20 项）
- test_e2e.py         端到端主流程（49 项）

e2e 需要后端已启动：
    python -m uvicorn app.main:app --port 8100
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
PY = sys.executable


def run(name: str, script: str) -> bool:
    print(f"\n{'=' * 60}\n▶ {name}\n{'=' * 60}")
    r = subprocess.run([PY, str(HERE / script)], cwd=BACKEND)
    return r.returncode == 0


def main() -> int:
    os.chdir(BACKEND)
    results = [
        ("SLA 工作时间计算", "test_sla.py"),
        ("检索质量", "test_retrieval.py"),
        ("附件安全", "test_attachments.py"),
        ("端到端主流程", "test_e2e.py"),
    ]

    passed = []
    failed = []
    for name, script in results:
        ok = run(name, script)
        (passed if ok else failed).append(name)

    print(f"\n{'=' * 60}")
    print("汇总")
    print("=" * 60)
    for p in passed:
        print(f"  ✅ {p}")
    for f in failed:
        print(f"  ❌ {f}")
    print()
    if failed:
        print(f"失败 {len(failed)} / {len(results)} 组")
        return 1
    print(f"全部通过 ({len(passed)}/{len(results)} 组)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
