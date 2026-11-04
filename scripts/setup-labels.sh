#!/usr/bin/env bash
# 初始化 / 更新仓库标签与 Discussions 分类。
#
# 幂等：重复执行安全。GitHub 默认标签对中文用户不友好，
# 这里换成一套贴合项目实际结构的中英双语标签。
#
# 用法：
#   bash scripts/setup-labels.sh
#
# 需要 gh CLI 且已认证（gh auth status）。

set -euo pipefail

REPO="${REPO:-kevin12369/polaris}"

if ! command -v gh >/dev/null 2>&1; then
  echo "错误：需要 gh CLI（https://cli.github.com）" >&2
  exit 1
fi

echo "==> 配置仓库：$REPO"

# ---------- 标签 ----------
# 格式：名称|颜色|描述
LABELS=(
  "type: feature|d4c5f9|新功能"
  "type: fix|1d76db|问题修复"
  "type: docs|c5def5|文档更新"
  "type: code|bfd4f2|代码重构或非功能性改动"
  "type: test|d4c5f9|测试相关"
  "type: ci|c5def5|CI / 自动化"
  "type: breaking|b60205|破坏性变更，升级前必读"

  "module: ticket|5319e7|工单模块（提交、分类、SLA、状态机）"
  "module: engine|0e8a16|引擎模块（检索、分类、排障）"
  "module: sla|5319e7|SLA 与工作时间计算"
  "module: data|0e8a16|数据模型与迁移"

  "area: sla|f9d0c4|SLA 倒计时、工作时间表"
  "area: security|b60205|认证、权限、租户隔离"
  "area: knowledge|1d76db|知识库与检索质量"
  "area: i18n|c2e0c6|中英文国际化"
  "area: deployment|c5def5|部署、Docker、运维"

  "backend|1d76db|后端（FastAPI / Python）"
  "frontend|0e8a16|前端（Vue 3 / Vite）"
  "documentation|0075ca|仅文档改动"
  "dependencies|0366d6|依赖更新"
  "deployment|f9d0c4|部署与运维"
  "demo|c2e0c6|演示页（GitHub Pages）"
  "ci|c5def5|CI / GitHub Actions"

  "good first issue|7057ff|适合第一次参与开源的新手"
  "help wanted|008672|需要外部协助"
  "roadmap|1d76db|已列入路线图"
  "pinned|0052cc|置顶，不会被自动关闭"
  "security|b60205|安全问题，请勿公开讨论"
  "skip-changelog|cfd3d7|不计入发布说明"
  "stale|cfd3d7|长期无活动，已自动标记"
)

echo "==> 写入标签（$(( ${#LABELS[@]} )) 个）"
for entry in "${LABELS[@]}"; do
  name="${entry%%|*}"
  rest="${entry#*|}"
  color="${rest%%|*}"
  desc="${rest#*|}"
  # 已存在则更新描述与颜色
  if gh label list --repo "$REPO" --limit 200 --json name -q '.[].name' | grep -qxF "$name"; then
    gh label edit "$name" --repo "$REPO" --color "$color" --description "$desc" >/dev/null 2>&1 || true
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" >/dev/null
  fi
  printf "  · %s\n" "$name"
done

# 删除 GitHub 默认的不适用标签（保留 question，它对中文用户也有用）
echo "==> 清理默认标签"
for name in invalid wontfix duplicate; do
  gh label delete "$name" --repo "$REPO" --yes >/dev/null 2>&1 && printf "  - %s（已删除）\n" "$name" || true
done

# ---------- Discussions 分类 ----------
# 说明：Discussions 分类目前只能用 REST API 创建（GraphQL 无对应 mutation），
# 且部分仓库环境下该接口会返回 404（如刚开启 Discussions 时）。
# 这里尽力而为，失败不影响整体流程 —— GitHub 默认的
# Q&A / Ideas / Announcements / Show and tell / General / Polls 已经够用。
echo "==> 配置 Discussions 分类"
ensure_discussion_category() {
  local name="$1" desc="$2" emoji="$3"
  if gh api "repos/$REPO/discussions/categories" --jq '.[].name' 2>/dev/null | grep -qxF "$name"; then
    printf "  · %s（已存在）\n" "$name"
    return 0
  fi
  if gh api "repos/$REPO/discussions/categories" --method POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -f name="$name" -f description="$desc" -f emoji="$emoji" >/dev/null 2>&1; then
    printf "  · %s（已创建）\n" "$name"
  else
    printf "  · %s（跳过：接口暂不可用，使用 GitHub 默认分类即可）\n" "$name"
  fi
}

ensure_discussion_category "答疑 Q&A" "使用问题、配置疑问、报错求助" "❓"
ensure_discussion_category "想法 Ideas" "功能设想与改进建议" "💡"
ensure_discussion_category "公告 Announcements" "版本发布、维护计划、重要变更" "📣"
ensure_discussion_category "展示 Show and tell" "晒一下你的部署、集成方案或二次开发" "🎉"

echo
echo "==> 完成。接下来建议："
echo "   1. 创建里程碑：bash scripts/create-milestone.sh v1.1.0 \"描述\""
echo "   2. 把路线图写进 README 的 Roadmap 章节"
echo "   3. 发布版本：bash scripts/release.sh v1.1.0"
