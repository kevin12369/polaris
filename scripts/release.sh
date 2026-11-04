#!/usr/bin/env bash
# 发布一个版本。
#
# 用法：
#   bash scripts/release.sh v1.1.0
#   bash scripts/release.sh v1.1.0 --notes "本次发布的重点"
#
# 流程：
#   1. 检查工作区干净、测试通过
#   2. 打标签并推送
#   3. 生成 CHANGELOG 段落并创建 GitHub Release
#   4. 上传源码包附件
#
# 幂等性：标签已存在时会中止并提示，避免覆盖已发布版本。

set -euo pipefail

REPO="${REPO:-kevin12369/polaris}"
VERSION="${1:-}"
NOTES="${3:-}"

if [ -z "$VERSION" ]; then
  echo "用法：bash scripts/release.sh <版本号> [--notes \"发布说明\"]" >&2
  echo "示例：bash scripts/release.sh v1.1.0 --notes \"新增节假日日历支持\"" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "错误：需要 gh CLI" >&2
  exit 1
fi

echo "==> 准备发布 $VERSION 到 $REPO"

# ---------- 1. 前置检查 ----------
if [ -n "$(git status --porcelain)" ]; then
  echo "错误：工作区有未提交的改动" >&2
  git status --short >&2
  echo "请先提交或 stash。" >&2
  exit 1
fi

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  echo "错误：标签 $VERSION 已存在（本地）。如需重发请先删除标签。" >&2
  exit 1
fi

echo "==> 跑测试"
cd backend
if [ -x ./.venv/Scripts/python.exe ]; then
  PY=./.venv/Scripts/python.exe
elif [ -x ./.venv/bin/python ]; then
  PY=./.venv/bin/python
else
  PY=python3
fi
"$PY" tests/test_sla.py >/dev/null
"$PY" tests/test_retrieval.py >/dev/null
echo "  单元测试通过"
cd ..

echo "==> 构建前端"
cd frontend
npm ci --no-audit --no-fund >/dev/null 2>&1
npm run build >/dev/null 2>&1
echo "  构建通过"
cd ..

# ---------- 2. 打标签 ----------
echo "==> 打标签 $VERSION"
git tag -a "$VERSION" -m "Release $VERSION"
git push origin "$VERSION"

# ---------- 3. 生成发布说明 ----------
NOTES_FILE="$(mktemp)"
if [ -n "$NOTES" ]; then
  {
    echo "## $VERSION"
    echo
    echo "$NOTES"
    echo
    echo "---"
    echo
    echo "**在线演示**：https://kevin12369.github.io/polaris/"
    echo "**完整变更**：https://github.com/$REPO/compare/v$(echo "$VERSION" | sed 's/^v//')...$VERSION"
  } > "$NOTES_FILE"
else
  # 没给说明就从 CHANGELOG 里抓对应段落
  CHANGELOG_SECTION="$(awk "/^## \[$VERSION\]/,/^## \[/{print}" CHANGELOG.md 2>/dev/null | head -60 || true)"
  if [ -n "$CHANGELOG_SECTION" ]; then
    {
      echo "$CHANGELOG_SECTION"
      echo
      echo "---"
      echo
      echo "**在线演示**：https://kevin12369.github.io/polaris/"
    } > "$NOTES_FILE"
  else
    printf '## %s\n\n**在线演示**：https://kevin12369.github.io/polaris/\n' "$VERSION" > "$NOTES_FILE"
    echo "  提示：CHANGELOG 里没有 $VERSION 的段落，使用了最小发布说明。"
  fi
fi

# ---------- 4. 创建 Release ----------
echo "==> 创建 Release"
gh release create "$VERSION" --repo "$REPO" \
  --title "Polaris 北极星 $VERSION" \
  --notes-file "$NOTES_FILE"

# ---------- 5. 上传源码包 ----------
echo "==> 生成源码包"
ARCHIVE="/tmp/polaris-${VERSION}.zip"
git archive --format=zip --prefix="polaris-${VERSION}/" -o "$ARCHIVE" "$VERSION"
gh release upload "$VERSION" "$ARCHIVE" --repo "$REPO" --clobber

rm -f "$NOTES_FILE"

echo
echo "==> 发布完成"
gh release view "$VERSION" --repo "$REPO" --json url -q '"  " + .url'
