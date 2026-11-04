# PR 模板

<!--
填写提示（提交前请删除本段）：
- 一个 PR 只做一件事。小改动直接提，大改动请先开 Issue 讨论。
- 提交信息用 Conventional Commits 格式，例如：feat(kb): 知识库条目支持按标签过滤
- 必跑检查：cd backend && ./.venv/Scripts/python tests/run_all.py
            cd frontend && npm run build
-->

## 变更类型

勾选本次 PR 的类型（可多选）：

- [ ] 🐛 **修复** —— 修 bug
- [ ] ✨ **新功能** —— 新增功能或模块
- [ ] 📖 **文档** —— 只改文档（README、部署指南、注释）
- [ ] ♻️ **重构** —— 不改变外部行为的代码重构
- [ ] 🧪 **测试** —— 只新增或修改测试
- [ ] 🔧 **CI / 构建** —— 改 CI 配置、Dockerfile、依赖
- [ ] 🌐 **国际化** —— 补充或修正中英文案

## 关联 Issue

<!-- 填了 Closes #123，PR 合并后会自动关闭对应 Issue；一个 PR 关多个用 Closes #1, #2 -->

Closes #

<!-- 如果暂时没有关联 Issue，写「无」并简述原因（如：纯 typo 修复） -->

## 变更说明

<!--
说清楚两件事：
1. 做了什么 —— 具体到功能点，不要写「优化了代码」
2. 为什么这么做 —— 解决了什么问题 / 为什么要这么改
-->

### 做了什么

-

### 为什么这么做

-

<!--
如果有截图或界面变更，把图片拖进来（会直接显示在 diff 里）。
UI 变更必填。
-->

### 界面变更截图

<!-- 无界面变更则写「无」 -->

## 测试情况

- [ ] 后端测试通过 —— `cd backend && ./.venv/Scripts/python tests/run_all.py`
- [ ] 前端构建通过 —— `cd frontend && npm run build`
- [ ] 手动验证了以下内容（请在下方说明你实际点了什么、看到了什么）

<!--
单组测试也可以单独跑：
  ./.venv/Scripts/python tests/test_sla.py
  ./.venv/Scripts/python tests/test_retrieval.py
  ./.venv/Scripts/python tests/test_e2e.py
-->

### 手动验证说明

<!-- 写清楚你实际做了什么、预期是什么、实际看到了什么。写「已测试」等于没写。 -->

-

## 检查清单

- [ ] 提交信息符合 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范
- [ ] 分支名符合约定（`feat/`、`fix/`、`docs/`、`refactor/`、`test/`、`chore/`、`ci/`）
- [ ] **没有引入新依赖** —— 或已在下方说明引入理由
- [ ] **更新了对应语言版本的文档** —— 涉及 README / 部署指南时，中英文都已更新
- [ ] 后端代码有类型注解，注释为中文
- [ ] 前端使用 `<script setup>` + Composition API，未直接使用 `fetch`
- [ ] 新增界面文案已补全中英文（`frontend/src/i18n.js`，格式 `中文|English`）
- [ ] 所有数据库查询都带 `company_id` 租户过滤
- [ ] 新增环境变量已同步更新 `.env.example`
- [ ] 本 PR 只做了一件事（没有夹带无关改动）

<!--
如果引入了新依赖，在这里说明：
依赖名 / 版本 / 为什么需要 / 有没有更轻量的替代方案
-->

### 新增依赖说明

<!-- 无则写「无」 -->

## 其他需要说明的

<!--
风险提示、已知限制、后续计划、需要维护者特别关注的地方。
没有就写「无」。
-->

-
