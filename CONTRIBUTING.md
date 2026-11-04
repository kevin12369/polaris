# 贡献指南

感谢你愿意为 **Polaris 北极星 · 客服工单管理平台** 花时间。

Polaris 是一个给中小企业用的轻量级客服工单系统：工单、知识库、AI 排障助手、仪表盘四个模块，
装在客户自己的服务器上，数据不出门。这个仓库很小，一个人维护，所以**每一份贡献我都亲手看**——
也正因如此，你的 PR 越清晰、越聚焦，我review 起来越快。

- 仓库：<https://github.com/kevin12369/polaris>
- 在线演示（零依赖单文件，含模拟数据）：<https://kevin12369.github.io/polaris/>
- 许可：[MIT](LICENSE)

**先读这一条**：如果你要做的是**比较大的改动**（新模块、数据库结构调整、依赖变更、API 大改），
请**先开一个 Issue 讨论**，不要直接写 PR。原因很简单——我不想让你花一周写完 500 行代码，
最后因为方向和现有设计冲突而全部推翻。先聊 20 分钟，能省你几天。

---

## 目录

- [两种贡献方式](#两种贡献方式)
- [快速开始](#快速开始)
- [提交信息规范](#提交信息规范)
- [分支命名约定](#分支命名约定)
- [PR 流程](#pr-流程)
- [必须跑通的检查](#必须跑通的检查)
- [代码风格约定](#代码风格约定)
- [什么算好的 PR](#什么算好的-pr)
- [文档与国际化](#文档与国际化)
- [其他](#其他)

---

## 两种贡献方式

### 方式一：提 Issue

Issue 用来**提 bug、提需求、提疑问**。仓库已经内置了表单模板：

| 表单 | 什么时候用 |
|---|---|
| [Bug 报告](.github/ISSUE_TEMPLATE/bug_report.yml) | 某处功能与预期不符、报错、行为异常 |
| [功能建议](.github/ISSUE_TEMPLATE/feature_request.yml) | 新功能、新模块、体验改进 |

> **提 bug 前请先搜一遍已有 Issue**，包括已关闭的。重复的 Issue 只会让修复进度更难追踪。
> 找不到重名的，用 Issue 模板提交即可。

提 Issue 时请注意：

- **中文或英文都可以**，但同一个 Issue 内请保持一致。
- **描述要具体**：「点了保存没反应」帮不了我，「在工单详情页点状态流转按钮，页面卡住 3 秒后
  报 500，日志里是 `KeyError: 'status_label'`」能帮大忙。
- **日志请脱敏**后再贴。日志里可能出现客户的真实邮箱、手机号、报错原文（含业务数据）、
  甚至 token。贴之前先替换掉。

### 方式二：提 Pull Request

PR 用来**提交代码**。无论改动大小，流程都一样（见 [PR 流程](#pr-流程)）。

- 修 typo、改文案、补测试，都欢迎。**小 PR 通常比大 PR 更快被合并**。
- 如果你想顺手做很多事，请拆成多个 PR。

---

## 快速开始

### 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | CI 用 3.12；3.13 也能跑（`backend/requirements.txt` 注明 3.12+ / 3.13） |
| Node.js | 22 | CI 用 Node 22（`.github/workflows/ci.yml`） |
| Docker / Compose | 20.10+ / v2 | 可选，仅在跑完整部署时需要 |

### 1. 拉代码

```bash
git clone https://github.com/kevin12369/polaris.git
cd polaris
```

### 2. 起后端

```bash
cd backend
python -m venv .venv

# Windows
./.venv/Scripts/pip install -r requirements.txt
# macOS / Linux
# ./.venv/bin/pip install -r requirements.txt

./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
# macOS / Linux: ./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

后端跑在 `http://localhost:8000`，交互式 API 文档在 `http://localhost:8000/docs`。

### 3. 起前端（另开一个终端）

```bash
cd frontend
npm install
npm run dev
```

前端跑在 `http://localhost:5173`。Vite 已配好 `/api` 代理，默认指向
`http://127.0.0.1:8000`（见 `frontend/vite.config.js`）。**如果你改了后端端口**，
用环境变量覆盖：

```bash
# Windows（PowerShell）
$env:VITE_API_TARGET="http://127.0.0.1:8100"; npm run dev
# macOS / Linux
VITE_API_TARGET=http://127.0.0.1:8100 npm run dev
```

### 4. 灌演示数据（可选，但强烈建议）

空库不好验证功能。种子脚本会生成一套可演示的小公司数据：

```bash
cd backend
./.venv/Scripts/python -m app.seed --reset
# macOS / Linux: ./.venv/bin/python -m app.seed --reset
```

演示账号：`demo@acme.com` / `demo1234`

> 注意：`--reset` 会**清空现有数据**。只在你自己的开发库上用，不要对着别人的部署跑。

### 5. 顺便看一眼 Docker 部署（可选）

```bash
cp .env.example .env

# 生成一个随机 SECRET_KEY，填进 .env
python -c "import secrets;print(secrets.token_urlsafe(48))"

docker compose up -d --build
```

打开 `http://localhost:8080`。数据库在 Docker 卷 `polaris-data` 里。

---

## 提交信息规范

用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 允许的 type

| type | 用途 | 例子 |
|---|---|---|
| `feat` | 新功能 | `feat(kb): 知识库条目支持按标签过滤` |
| `fix` | 修 bug | `fix(sla): 修复跨周末时 SLA 截止时间计算错误` |
| `docs` | 只改文档 | `docs(readme): 补充 SQLite 备份与恢复步骤` |
| `refactor` | 不改变外部行为的重构 | `refactor(retrieval): 把 BM25 打分抽成独立函数` |
| `test` | 只加/改测试 | `test(e2e): 补充跨租户访问越权用例` |
| `ci` | 改 CI 配置 | `ci: 在前端构建后校验 dist 产物存在` |
| `chore` | 杂项，不影响源码和测试 | `chore(deps): 升级 fastapi 到 0.115.x` |
| `perf` | 性能优化 | `perf(retrieval): 检索前过滤低频词，缩短大知识库查询耗时` |
| `revert` | 回滚之前的提交 | `revert: 回退 "feat(kb): 知识库导出 CSV"` |

### scope 建议

用模块名：`tickets` / `kb` / `assistant` / `dashboard` / `auth` / `settings` / `sla` /
`retrieval` / `i18n` / `demo` / `docs` / `deps`。后端代码在 `backend/app/`，
前端在 `frontend/src/`。

### subject 怎么写

- **中文即可**，英文也可以，同一仓库里保持一致就好。
- 结尾**不加句号**。
- 用祈使句、描述「做了什么」，不是「我做了什么」。
- 长度控制在 50 个字符以内（中文字符算 1个）。

### 示例

```
feat(kb): 知识库列表支持按分类筛选

在 Knowledge.vue 的筛选栏加入分类下拉框，选项复用后端的
TICKET_CATEGORIES 字典，避免中英文两处硬编码。

Closes #42
```

```
fix(sla): 修复周五 18:00 后创建工单响应时限少算一天

working_minutes_between 在跨天时未考虑周末非工作日，
导致周五晚上创建的 P3 工单响应时限提前到第二天早上。

新增回归用例覆盖"周五 20:00 创建"的场景。
```

```
docs(deploy): 补充 Nginx 反向代理的 HTTPS 配置示例
```

**破坏性变更**要在 footer 里写明：

```
feat(tickets): 工单状态码从中文改为英文枚举

BREAKING CHANGE: 状态字段值由「待受理」等中文改为 new/triaged/... 
原有数据库中已存的中文状态值需要执行迁移脚本。
```

---

## 分支命名约定

从 `main` 切分支，格式：`<type>/<简短描述>`，用小写字母和短横线。

```
feat/kb-tag-filter
fix/sla-weekend-calc
docs/deployment-nginx
refactor/retrieval-bm25-extract
chore/bump-fastapi
```

- 一条分支只做一件事。分支名和 PR 标题保持一致，方便追溯。
- **不要直接推 `main`。**
- 如果你的分支要活很久，建议定期 rebase 到最新的 `main`，避免合并时冲突堆积。

---

## PR 流程

1. **先开 Issue 讨论**（大改动必做）。在 Issue 里说清楚你想解决什么问题，
   顺便问一句「这个方向有人做过吗」，避免重复劳动。
2. **Fork 仓库**，把 fork 克隆到本地：

   ```bash
   git clone https://github.com/<你的用户名>/polaris.git
   cd polaris
   git remote add upstream https://github.com/kevin12369/polaris.git
   ```

3. **从最新 `main` 切分支**：

   ```bash
   git fetch upstream
   git checkout -b feat/你的描述 upstream/main
   ```

4. **写代码 + 写测试**，同时更新对应文档（见 [文档与国际化](#文档与国际化)）。
5. **本地跑一遍[必须跑通的检查](#必须跑通的检查)**。别让 CI 教你它哪步挂了。
6. **提交并推送**：

   ```bash
   git add -A
   git commit -m "feat(kb): 知识库列表支持按分类筛选"
   git push -u origin feat/你的描述
   ```

7. **提 PR**。用 PR 模板填好，「变更说明」写清楚**做了什么**和**为什么**。
   如果关联 Issue，在描述里写 `Closes #42`，合并后会自动关掉它。
8. **等 CI 通过**。CI 有三个 job：后端测试、前端构建、Docker 镜像构建。
   红的必须修——**我不合并 CI 不绿的 PR**。
9. **等 review**。我会尽量在 3 天内给出意见。如果超过一周没动静，
   在 PR 里 ping 一下就好，别不好意思。

---

## 必须跑通的检查

### 后端测试

e2e 测试需要后端服务先起来，**用 8100 端口**（测试脚本默认打这个端口，
可用 `TEST_BASE_URL` 覆盖）：

```bash
# 终端 1 —— 启动测试用后端
cd backend
./.venv/Scripts/python -m uvicorn app.main:app --port 8100
# macOS / Linux: ./.venv/bin/python -m uvicorn app.main:app --port 8100

# 终端 2 —— 跑全部测试
cd backend
./.venv/Scripts/python tests/run_all.py
```

> ⚠️ **别用开发库跑 e2e。** 测试会在当前 `DATABASE_URL` 指向的库里创建
> `E2E 测试公司`、`E2E 隔离空间` 这样的租户和测试工单（脚本只清理知识库条目，
> 租户和工单会留在库里）。跑之前先用一个独立测试库，和 CI 保持一致：
>
> ```bash
> # Windows（PowerShell）
> $env:DATABASE_URL="sqlite:///./test_run.db"; $env:DATA_DIR="./test_run_data"
> ./.venv/Scripts/python -m uvicorn app.main:app --port 8100
>
> # macOS / Linux
> DATABASE_URL="sqlite:///./test_run.db" DATA_DIR="./test_run_data" \
>   ./.venv/bin/python -m uvicorn app.main:app --port 8100
> ```
>
> 测完把 `test_run.db` 和 `test_run_data/` 删掉即可。**CI 就是这么做的**——
> `.github/workflows/ci.yml` 里设了 `DATABASE_URL: sqlite:////tmp/sw-ci-test.db`
> 和 `DATA_DIR: /tmp/sw-ci-data`，完全不碰真实数据。

`run_all.py` 会依次跑三组，共 93 项断言：

| 测试 | 项数 | 覆盖 |
|---|---|---|
| `tests/test_sla.py` | 20 | 工作时间计算、跨周末、跨下班、自定义排班、超时判定 |
| `tests/test_retrieval.py` | 24 | 检索判据、正负样本区分、中英错配、长日志 |
| `tests/test_e2e.py` | 49 | 四模块主流程、租户隔离、状态机、权限控制 |

期望输出结尾是：

```
全部通过 (3/3 组)
```

想单独跑某一组：

```bash
./.venv/Scripts/python tests/test_sla.py
./.venv/Scripts/python tests/test_retrieval.py
./.venv/Scripts/python tests/test_e2e.py
```

> e2e 每次运行用唯一标识（`e2e-main-<时间戳>@example.com`）造数据，
> 所以**可以重复运行、不会互相冲突**。但数据会留在库里 —— 所以要按上面的提示
> 用独立的 `DATABASE_URL`，别直接跑在开发库上。

**改了 `backend/app/` 下的任何代码，都必须跑这个。**

### 前端构建

```bash
cd frontend
npm ci        # 首次或依赖有变动时用 npm install
npm run build
```

必须无报错退出，并生成 `frontend/dist/index.html`。**CI 里也会检查这个产物是否存在**，
所以本地构建失败 = CI 必然失败。

### Docker 镜像构建（改了 Dockerfile / compose 时）

```bash
docker compose build backend
docker compose build frontend
docker compose config --quiet
```

### 一条命令跑完检查

```bash
# 后端
cd backend && ./.venv/Scripts/python tests/run_all.py
# 前端
cd ../frontend && npm run build
```

---

## 代码风格约定

### Python（`backend/app/`）

**核心要求：类型注解 + 中文注释。** 这个项目的代码是给中文团队读的，注释写中文。

```python
# ✅ 好的写法
from __future__ import annotations


def working_minutes_between(
    start: dt.datetime,
    end: dt.datetime,
    schedule: dict | None = None,
) -> int:
    """计算两个时间点之间的工作分钟数。

    工作时间表未指定时回落到全局默认（周一至周五 09:00-18:00）。
    """
    work_days = (schedule or {}).get("work_days", WORK_DAYS)
    ...
```

约定细则：

- **每个文件开头写模块级 docstring**，说明这个模块负责什么。
- **所有函数加类型注解**：参数和返回值都要。复杂类型用 `from __future__ import annotations`
  + 内置泛型写法（`list[str]`、`dict | None`）。
- **注释和 docstring 写中文**，解释「为什么这么做」，不要翻译代码本身。
  ```python
  # ❌ 浪费一行：# 计数加一
  # ✅ 有价值：# 考虑历史删除，用 max 序号兜底
  ```
- **SQLAlchemy 2.0 风格**：用 `select()` + `db.execute()`，不要用旧的 `query()` API。
  过滤条件带租户隔离 —— 所有查询都要有 `company_id` 约束。
- **业务逻辑放 `services/`**，路由放 `routers/`，请求模型放 `schemas.py`，
  配置放 `config.py`。别把业务逻辑塞进路由函数里。
- **新增配置项一律走环境变量**，在 `config.py` 里读，且必须同步更新 `.env.example`。
- **新表/新字段要写迁移**（`backend/app/migrations.py`），因为 SQLite 的 `create_all`
  不会给已有表补字段。

### Vue（`frontend/src/`）

**核心要求：`<script setup>` + Composition API。** 现有全部视图都是这个写法，别混用 Options API。

```vue
<script setup>
import { ref, computed } from 'vue'
import { t } from '../i18n'

const keyword = ref('')
const filtered = computed(() => {
  /* ... */
})

function handleSave() {
  /* ... */
}
</script>
```

约定细则：

- 一律用 `<script setup>`，不用 `export default {}`。
- 状态用 `ref` / `reactive`，派生数据用 `computed`，副作用用 `watch`。
- **API 调用统一走 `frontend/src/api.js`**，别在组件里直接 `fetch`。
- **样式写在组件的 `<style scoped>` 里**，共用样式加到 `frontend/src/styles.css`。
- 主题色、圆角、间距尽量复用现有 CSS 变量，别硬编码颜色值。

### 国际化（`frontend/src/i18n.js`）

项目**不引入 vue-i18n**，用的是一个轻量自研字典。两种写法：

```js
// 1) 查字典（DICT 里查 key）
import { t } from '../i18n'
t('nav.dashboard')          // → '仪表盘' / 'Dashboard'

// 2) 直接解析双语串（适合后端返回的枚举值）
import { L } from '../i18n'
L('账号登录 | Account login')
```

**新增任何界面文案，都必须同时补上中文和英文**，格式是 `中文|English`，
竖线前后不要有多余空格。英文缺失会导致英文界面直接显示中文，这是明确的 bug。

---

## 什么算好的 PR

一个好的 PR，对维护者来说应该**读一遍就知道它做了什么、为什么这么做、有没有风险**。

具体来说：

- ✅ **小而聚焦** —— 一个 PR 只做一件事。想同时改三个模块？拆成三个 PR。
- ✅ **单一目的** —— 标题说清楚做了什么，描述说清楚为什么。
- ✅ **附带测试** —— 修 bug 就补一条能复现这个 bug 的用例；加功能就在
  `backend/tests/` 里加对应断言；改界面就在 PR 里贴前后对比截图。
- ✅ **更新文档** —— 改了配置项就更新 `.env.example` 和 `docs/部署指南.md`；
  改了接口就更新 README 的 API 一览；改了用法就同时更新中英文 README。
- ✅ **可回滚** —— 改动足够小，出问题能干净地 revert 掉。
- ✅ **CI 全绿** —— 后端测试、前端构建、镜像构建三个 job 都过。

反过来说，这些 PR 很可能被要求返工：

- ❌ 一个 PR 塞了功能 + 重构 + 格式化全库（diff 一屏看不完）
- ❌ 引入新依赖但不说明理由（当前依赖只有 8 个，都是刚需，加之前先聊）
- ❌ 改了代码但不更新文档，导致 README 和实际行为对不上
- ❌ 「顺手」改了无关的代码（让 reviewer 难以确认你的真实意图）
- ❌ 提交信息写成 `fix bug`、`update`、`改了一下`

---

## 文档与国际化

这个项目是**中英双语**的，改动时记得两边都改：

| 中文 | English |
|---|---|
| `README.md` | `README.en.md` |
| `docs/部署指南.md` | `docs/DEPLOYMENT.en.md` |

规则：

- **界面文案** → 改 `frontend/src/i18n.js`，中英都要有。
- **README 内容** → 中英文 README 都要改，保持结构对应。
- **部署相关** → 中英文部署指南都要改，包括 `.env.example` 里的变量说明。

如果你只懂中文，也完全没问题——**先改中文版，然后开一个 Issue 告诉我哪几段需要英文版**，
我来补。反过来也一样。

---

## 其他

### 提交 Issue 前的准备

- 搜一遍已有 Issue。
- 准备复现步骤。
- 收集环境信息：Polaris 版本、部署方式（Docker / 本地）、浏览器、Python / Node 版本。
- **日志脱敏**：贴之前把客户邮箱、手机号、报错原文里的业务数据、token 全替换掉。

### 想聊点别的？

- **功能讨论、实现思路、想找人一起做** → [Discussions](https://github.com/kevin12369/polaris/discussions)
- **Bug 和需求** → [Issues](https://github.com/kevin12369/polaris/issues)
- **安全漏洞** → **不要开公开 Issue**，看 [SECURITY.md](SECURITY.md)

### 社区行为准则

参与本项目即表示同意 [行为准则](CODE_OF_CONDUCT.md)。请假设对方是善意的，
技术分歧对事不对人。

### 许可

提交贡献即表示你同意你的代码以 [MIT 许可](LICENSE) 发布。

---

## 有疑问？

直接开 Issue，或者在 Discussions 里问。这个项目规模不大，
我基本都会回——只是有时候要慢一点，别催。
