#!/usr/bin/env bash
# 创建里程碑。
#
# 用法：
#   bash scripts/create-milestone.sh v1.1.0 "描述文字"
#   bash scripts/create-milestone.sh v1.1.0 "描述" --due 2026-12-31

set -euo pipefail

REPO="${REPO:-kevin12369/polaris}"
TITLE="${1:-}"
DESCRIPTION="${2:-}"
DUE=""

if [ -z "$TITLE" ]; then
  echo "用法：bash scripts/create-milestone.sh <标题> [描述] [--due YYYY-MM-DD]" >&2
  exit 1
fi

if [ "${3:-}" = "--due" ] && [ -n "${4:-}" ]; then
  DUE="$4"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "错误：需要 gh CLI" >&2
  exit 1
fi

echo "==> 创建里程碑 $TITLE"

ARGS=(--method POST -f "title=$TITLE" -f "description=${DESCRIPTION:-}")
if [ -n "$DUE" ]; then
  ARGS+=(-f "due_on=${DUE}T00:00:00Z")
fi

gh api "repos/$REPO/milestones" "${ARGS[@]}" --jq '"  ✓ #\(.number) \(.title)  (\(.open_issues) 个 open issue)"'
