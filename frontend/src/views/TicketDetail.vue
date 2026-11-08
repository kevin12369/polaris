<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assistantApi, attachmentApi, kbApi, ticketApi } from '../api'
import { fmtMinutes, fmtRemaining, fmtTime, PRIORITY_TONE, STATUS_TONE } from '../utils'
import { t, catLabel, statusLabel, priLabel } from '../i18n'

const route = useRoute()
const router = useRouter()

const ticket = ref(null)
const events = ref([])
const meta = ref({ categories: [], priorities: [], statuses: [], transitions: {} })
const loading = ref(false)
const error = ref('')

const note = ref('')
const showPromote = ref(false)
const promoteForm = ref({ title: '', summary: '', category: '', steps: [] })
const promoteResult = ref(null)
const suggestions = ref([])
const aiResult = ref(null)
const aiLoading = ref(false)
const aiText = ref('')
const showAi = ref(false)

// ---- 附件 ----
const attachments = ref([])
const attMeta = ref({ max_files: 10, max_bytes: 10485760, allowed_extensions: [] })
const uploading = ref(false)
const attError = ref('')
const fileInput = ref(null)

/** 文件图标：按扩展名选，纯 CSS 字符不引入图标库 */
function attIcon(name = '') {
  const ext = (name.split('.').pop() || '').toLowerCase()
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return '🖼'
  if (ext === 'pdf') return '📕'
  if (['zip', 'docx', 'xlsx', 'pptx'].includes(ext)) return '🗜'
  if (['txt', 'log', 'md', 'csv', 'json'].includes(ext)) return '📄'
  return '📎'
}

/** 字节数转可读体积 */
function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function loadAttachments() {
  if (!ticket.value) return
  try {
    const res = await attachmentApi.list(ticket.value.id)
    attachments.value = res.items || []
    attMeta.value = {
      max_files: res.max_files,
      max_bytes: res.max_bytes,
      allowed_extensions: res.allowed_extensions || [],
    }
  } catch (e) {
    // 附件加载失败不应阻塞详情页
    console.warn('附件列表加载失败:', e.message)
  }
}

function pickFile() {
  fileInput.value?.click()
}

/**
 * 处理文件选择。
 *
 * 两个坑：
 * 1. 清空 input.value 会触发 change 事件，导致递归上传（FormData 为空）。
 *    用 uploading 标志位防重入。
 * 2. 不能提前清空 input，也不能克隆 File —— 浏览器会释放原 File 的关联，
 *    克隆出来的 File 同样可能内容为空（后端会报「文件为空」）。
 *    所以：先上传，用完再清空。
 */
async function onFilePicked(e) {
  const input = e.target
  if (uploading.value) return

  const file = input.files?.[0]
  if (!file) return
  attError.value = ''

  if (attachments.value.length >= attMeta.value.max_files) {
    attError.value = t('att.maxFiles', { n: attMeta.value.max_files })
    input.value = ''
    return
  }
  if (file.size > attMeta.value.max_bytes) {
    attError.value = t('att.tooLarge', { n: fmtSize(attMeta.value.max_bytes) })
    input.value = ''
    return
  }

  uploading.value = true
  try {
    await attachmentApi.upload(ticket.value.id, file)
    await loadAttachments()
  } catch (err) {
    attError.value = err.message
  } finally {
    uploading.value = false
    // 上传结束才清空：让「连续选同一个文件」也能触发 change 事件。
    // 此时 uploading 已为 false，清空触发的 change 会被上面的守卫拦下。
    input.value = ''
  }
}

async function downloadAtt(att) {
  try {
    await attachmentApi.download(ticket.value.id, att.id, att.original_name)
  } catch (e) {
    attError.value = e.message
  }
}

async function removeAtt(att) {
  if (!window.confirm(t('att.deleteConfirm', { name: att.original_name }))) return
  attError.value = ''
  try {
    await attachmentApi.remove(ticket.value.id, att.id)
    await loadAttachments()
  } catch (e) {
    attError.value = e.message
  }
}

const sla = computed(() => {
  if (!ticket.value) return null
  const t = ticket.value
  const respDone = !!t.first_response_at
  const respBreach = t.sla_response_breached
  const resolveBreach = t.sla_resolve_breached
  const closed = t.status === 'closed' || t.status === 'resolved'
  return {
    respState: respBreach ? 'danger' : respDone ? 'ok' : t.sla_response_remaining < 60 ? 'warn' : 'ok',
    respLabel: respBreach
      ? '响应超时'
      : respDone
        ? '已响应'
        : t.sla_response_remaining < 60
          ? '即将超时'
          : '待响应',
    respRemaining: respDone ? null : t.sla_response_remaining,
    resolveState: resolveBreach ? 'danger' : closed ? 'ok' : t.sla_resolve_remaining < 120 ? 'warn' : 'ok',
    resolveLabel: resolveBreach
      ? '解决超时'
      : closed
        ? '已达标'
        : t.sla_resolve_remaining < 120
          ? '即将超时'
          : '正常',
    resolveRemaining: closed ? null : t.sla_resolve_remaining,
  }
})

const nextStatuses = computed(() => {
  if (!ticket.value) return []
  const allowed = meta.value.transitions?.[ticket.value.status] || []
  return allowed
    .map((code) => meta.value.statuses.find((s) => s.code === code))
    .filter(Boolean)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await ticketApi.get(route.params.id)
    ticket.value = res.ticket
    events.value = res.events
    // 附件独立加载：失败也不该影响详情页主体
    await loadAttachments()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function changeStatus(to) {
  error.value = ''
  try {
    await ticketApi.changeStatus(ticket.value.id, to, note.value, note.value)
    note.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function addComment() {
  if (!note.value.trim()) return
  error.value = ''
  try {
    await ticketApi.comment(ticket.value.id, note.value.trim())
    note.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function loadSuggestions() {
  try {
    const res = await ticketApi.suggest(ticket.value.id, '')
    suggestions.value = res.items
  } catch (e) {
    suggestions.value = []
  }
}

async function openPromote() {
  promoteForm.value = {
    title: ticket.value.title,
    summary: '',
    category: ticket.value.category,
    steps: [],
  }
  promoteResult.value = null
  showPromote.value = true
}

async function doPromote() {
  error.value = ''
  try {
    const res = await ticketApi.promoteToKb(ticket.value.id, promoteForm.value)
    promoteResult.value = res.article
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function runAi() {
  if (!aiText.value.trim()) return
  aiLoading.value = true
  try {
    aiResult.value = await assistantApi.troubleshoot(
      `${ticket.value.title}\n${aiText.value}`,
      ticket.value.id
    )
  } catch (e) {
    error.value = e.message
  } finally {
    aiLoading.value = false
  }
}

function openKb(id) {
  router.push(`/kb?focus=${id}`)
}

onMounted(async () => {
  try {
    meta.value = await ticketApi.meta()
  } catch (e) {
    /* 忽略 */
  }
  await load()
  loadSuggestions()
})
</script>

<template>
  <div v-if="loading" class="empty">{{ t('common.loading') }}</div>
  <div v-else-if="!ticket" class="empty">{{ t('td.notFound') }}</div>
  <div v-else class="detail">
    <div class="row-between" style="margin-bottom: 14px">
      <div class="row" style="gap: 10px">
        <button class="btn btn-ghost btn-sm" @click="router.back()">{{ t('td.back') }}</button>
        <span class="mono muted">{{ ticket.code }}</span>
        <span class="badge" :class="`badge-${PRIORITY_TONE[ticket.priority]}`">
          {{ ticket.priority }} · {{ priLabel(ticket.priority, ticket.priority_label) }}
        </span>
        <span class="badge" :class="`badge-${STATUS_TONE[ticket.status]}`">{{ statusLabel(ticket.status, ticket.status_label) }}</span>
        <span class="badge badge-mute">{{ catLabel(ticket.category) }}</span>
        <span
          v-if="ticket.category_source === 'ai'"
          class="badge badge-info"
          title="由 AI 自动判定"
        >AI 判定 {{ Math.round(ticket.confidence * 100) }}%</span>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="grid">
      <!-- 左：主体 -->
      <div class="col-main">
        <div class="card">
          <div class="card-body">
            <h1 class="title">{{ ticket.title }}</h1>
            <div class="meta-line muted">
              {{ ticket.requester_name || '匿名' }}
              <template v-if="ticket.requester_email"> · {{ ticket.requester_email }}</template>
              · 来源 {{ ticket.channel }} · 创建于 {{ fmtTime(ticket.created_at) }}
            </div>
            <div v-if="ticket.content" class="content-body">{{ ticket.content }}</div>
            <div v-if="ticket.resolution_note" class="resolution">
              <div class="res-label">处理记录</div>
              {{ ticket.resolution_note }}
            </div>
          </div>
        </div>

        <!-- 附件 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head">
            <h3>{{ t('att.title') }}</h3>
            <span class="muted tiny">
              {{ attachments.length }} / {{ attMeta.max_files }}
            </span>
          </div>
          <div class="card-body">
            <!-- 文件列表 -->
            <div v-if="attachments.length" class="att-list">
              <div v-for="att in attachments" :key="att.id" class="att-item">
                <span class="att-icon">{{ attIcon(att.original_name) }}</span>
                <div class="att-info">
                  <div class="att-name truncate" :title="att.original_name">
                    {{ att.original_name }}
                  </div>
                  <div class="att-meta">
                    {{ fmtSize(att.size) }} · {{ att.uploader_name }} ·
                    {{ fmtTime(att.created_at) }}
                  </div>
                </div>
                <button class="btn btn-ghost btn-sm" :title="t('att.download')" @click="downloadAtt(att)">
                  ↓
                </button>
                <button class="btn btn-ghost btn-sm danger" :title="t('att.delete')" @click="removeAtt(att)">
                  ×
                </button>
              </div>
            </div>
            <div v-else class="empty">{{ t('att.empty') }}</div>

            <!-- 上传 -->
            <div class="att-upload">
              <input
                ref="fileInput"
                type="file"
                class="att-input"
                :accept="attMeta.allowed_extensions.join(',')"
                @change="onFilePicked"
              />
              <button
                class="btn btn-sm"
                :disabled="uploading || attachments.length >= attMeta.max_files"
                @click="pickFile"
              >
                {{ uploading ? t('att.uploading') : t('att.upload') }}
              </button>
              <span class="muted tiny">
                {{ t('att.hint', { max: fmtSize(attMeta.max_bytes) }) }}
              </span>
            </div>
            <div v-if="attError" class="msg error" style="margin-top: 8px">{{ attError }}</div>
          </div>
        </div>

        <!-- 知识库建议 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head">
            <h3>知识库建议</h3>
            <button class="btn btn-ghost btn-sm" @click="loadSuggestions">刷新</button>
          </div>
          <div class="card-body">
            <div v-if="!suggestions.length" class="muted" style="font-size: 12.5px">
              没有匹配到相关条目。可在下方「AI 排障」中生成排查步骤。
            </div>
            <div v-for="s in suggestions" :key="s.id" class="kb-suggest">
              <div class="grow">
                <div class="row" style="gap: 8px">
                  <span class="kb-title">{{ s.title }}</span>
                  <span class="badge badge-mute">{{ s.category }}</span>
                </div>
                <div v-if="s.summary" class="muted" style="font-size: 12px; margin-top: 3px">
                  {{ s.summary }}
                </div>
              </div>
              <button class="btn btn-sm" @click="openKb(s.id)">查看</button>
            </div>
          </div>
        </div>

        <!-- 事件流 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head"><h3>处理记录</h3></div>
          <div class="card-body">
            <div v-for="e in events" :key="e.id" class="event">
              <div class="event-dot" :class="`ev-${e.type}`"></div>
              <div class="grow">
                <div class="row" style="gap: 8px">
                  <strong style="font-size: 12.5px">{{ e.actor_name }}</strong>
                  <span class="muted tiny">{{ fmtTime(e.created_at) }}</span>
                </div>
                <div class="event-note">{{ e.note }}</div>
              </div>
            </div>
            <div v-if="!events.length" class="muted">暂无记录</div>
          </div>
        </div>
      </div>

      <!-- 右：侧栏 -->
      <div class="col-side">
        <!-- SLA -->
        <div class="card">
          <div class="card-head"><h3>SLA 倒计时</h3></div>
          <div class="card-body">
            <div class="sla-item">
              <div class="row-between">
                <span class="dim">首次响应</span>
                <span class="badge" :class="`badge-${sla.respState}`">{{ sla.respLabel }}</span>
              </div>
              <div class="sla-value mono" :class="`st-${sla.respState}`">
                {{ sla.respRemaining !== null ? fmtRemaining(sla.respRemaining) : '已响应' }}
              </div>
              <div class="muted tiny">目标 {{ fmtMinutes(ticket.sla_response_total) }} · 截止 {{ fmtTime(ticket.sla_response_due) }}</div>
            </div>
            <div class="sla-item">
              <div class="row-between">
                <span class="dim">解决时限</span>
                <span class="badge" :class="`badge-${sla.resolveState}`">{{ sla.resolveLabel }}</span>
              </div>
              <div class="sla-value mono" :class="`st-${sla.resolveState}`">
                {{ sla.resolveRemaining !== null ? fmtRemaining(sla.resolveRemaining) : '已完成' }}
              </div>
              <div class="muted tiny">目标 {{ fmtMinutes(ticket.sla_resolve_total) }} · 截止 {{ fmtTime(ticket.sla_resolve_due) }}</div>
            </div>
            <div class="sla-stats">
              <div>
                <div class="muted tiny">已响应耗时</div>
                <div class="mono">{{ fmtMinutes(ticket.response_minutes) }}</div>
              </div>
              <div>
                <div class="muted tiny">解决耗时</div>
                <div class="mono">{{ ticket.resolve_minutes !== null ? fmtMinutes(ticket.resolve_minutes) : '—' }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 状态流转 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head"><h3>状态流转</h3></div>
          <div class="card-body">
            <textarea
              v-model="note"
              rows="3"
              placeholder="备注（将记入处理记录）"
              style="margin-bottom: 10px"
            ></textarea>
            <div class="btn-col">
              <button
                v-for="s in nextStatuses"
                :key="s.code"
                class="btn btn-sm"
                :class="s.code === 'resolved' || s.code === 'closed' ? 'btn-primary' : ''"
                @click="changeStatus(s.code)"
              >
                → {{ s.label }}
              </button>
              <button class="btn btn-sm" @click="addComment">仅添加备注</button>
            </div>
          </div>
        </div>

        <!-- 沉淀知识库 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head"><h3>知识沉淀</h3></div>
          <div class="card-body">
            <p class="muted" style="font-size: 12.5px; margin: 0 0 10px">
              关单时把这次的处理过程存成知识库条目，下次同样的问题 AI 可直接给出答案。
            </p>
            <button class="btn btn-block" @click="openPromote">◫ 沉淀为知识库</button>
            <div v-if="ticket.linked_kb_ids?.length" class="linked-kb">
              <div class="muted tiny" style="margin-top: 10px">已关联条目</div>
              <div v-for="id in ticket.linked_kb_ids" :key="id" class="badge badge-info" style="margin-top: 4px">
                KB #{{ id }}
              </div>
            </div>
          </div>
        </div>

        <!-- AI 排障 -->
        <div class="card" style="margin-top: 14px">
          <div class="card-head">
            <h3>AI 排障</h3>
            <button class="btn btn-ghost btn-sm" @click="showAi = !showAi">
              {{ showAi ? '收起' : '展开' }}
            </button>
          </div>
          <div v-if="showAi" class="card-body">
            <textarea
              v-model="aiText"
              rows="3"
              placeholder="粘贴报错信息或日志片段"
              style="margin-bottom: 9px"
            ></textarea>
            <button class="btn btn-primary btn-block" :disabled="aiLoading" @click="runAi">
              {{ aiLoading ? '分析中…' : '生成排查步骤' }}
            </button>
            <div v-if="aiResult" class="ai-out fade-in">
              <div class="ai-summary">{{ aiResult.summary }}</div>
              <ol class="ai-steps">
                <li v-for="(s, i) in aiResult.steps" :key="i">
                  <strong>{{ s.title }}</strong>
                  <div class="muted">{{ s.detail }}</div>
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 沉淀弹窗 -->
    <div v-if="showPromote" class="modal-mask" @click.self="showPromote = false">
      <div class="modal fade-in">
        <div class="modal-head">
          <h3>沉淀为知识库条目</h3>
          <button class="btn btn-ghost btn-sm" @click="showPromote = false">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="promoteResult" class="success-box">
            已创建知识库条目「{{ promoteResult.title }}」，后续可在知识库中查看。
            <button class="btn btn-sm" style="margin-top: 8px" @click="openKb(promoteResult.id)">
              打开条目
            </button>
          </div>
          <template v-else>
            <div class="field">
              <label>标题</label>
              <input v-model="promoteForm.title" />
            </div>
            <div class="field">
              <label>摘要</label>
              <input v-model="promoteForm.summary" placeholder="留空则自动生成" />
            </div>
            <div class="field">
              <label>分类</label>
              <select v-model="promoteForm.category">
                <option v-for="c in meta.categories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div class="hint" style="margin-top: -4px">
              未填写摘要时会调用 AI 自动生成摘要与通用化排查步骤（未配置大模型时使用内置模板）。
            </div>
          </template>
        </div>
        <div class="modal-foot">
          <button class="btn" @click="showPromote = false">关闭</button>
          <button v-if="!promoteResult" class="btn btn-primary" @click="doPromote">创建条目</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------- 附件 ---------- */
.att-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.att-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 10px;
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.att-icon {
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
}
.att-info {
  flex: 1;
  min-width: 0;
}
.att-name {
  font-size: 12.5px;
  color: var(--text);
}
.att-meta {
  font-size: 11px;
  color: var(--text-mute);
  margin-top: 1px;
}
/* 下载 / 删除按钮：固定宽度，避免换行 */
.att-item .btn {
  flex-shrink: 0;
  min-width: 30px;
  padding: 0 8px;
}
.att-upload {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
/* 隐藏原生 file input，由按钮触发 */
.att-input {
  display: none;
}
.btn.danger:hover {
  color: var(--danger);
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 316px;
  gap: 14px;
  align-items: start;
}
.title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.4;
}
.meta-line {
  font-size: 12px;
}
.content-body {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 13.5px;
}
.resolution {
  margin-top: 14px;
  padding: 11px 13px;
  border-radius: var(--radius-sm);
  background: rgba(63, 185, 80, 0.07);
  border: 1px solid rgba(63, 185, 80, 0.25);
  font-size: 13px;
  white-space: pre-wrap;
}
.res-label {
  font-size: 11.5px;
  color: var(--ok);
  font-weight: 600;
  margin-bottom: 4px;
}
.kb-suggest {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
}
.kb-suggest:last-child {
  border-bottom: none;
}
.kb-title {
  font-size: 13px;
  font-weight: 500;
}
.event {
  display: flex;
  gap: 11px;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
}
.event:last-child {
  border-bottom: none;
}
.event-dot {
  width: 7px;
  height: 7px;
  flex-shrink: 0;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--text-mute);
}
.ev-created { background: var(--accent); }
.ev-status { background: var(--ok); }
.ev-kb { background: #a371f7; }
.ev-comment { background: var(--warn); }
.event-note {
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--text-dim);
  line-height: 1.55;
}
.tiny { font-size: 11.5px; }

.sla-item {
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.sla-value {
  margin: 5px 0 3px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.st-ok { color: var(--ok); }
.st-warn { color: var(--warn); }
.st-danger { color: var(--danger); }
.sla-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.btn-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.linked-kb {
  margin-top: 4px;
}
.ai-out {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.ai-summary {
  font-size: 12.5px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 9px;
}
.ai-steps {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
}
.ai-steps li {
  margin-bottom: 8px;
  line-height: 1.55;
}
.error-box {
  margin-bottom: 12px;
  padding: 8px 11px;
  border-radius: var(--radius-sm);
  background: rgba(242, 85, 90, 0.1);
  border: 1px solid rgba(242, 85, 90, 0.3);
  color: #ff9ea1;
  font-size: 12.5px;
}
.success-box {
  padding: 12px;
  border-radius: var(--radius-sm);
  background: rgba(63, 185, 80, 0.08);
  border: 1px solid rgba(63, 185, 80, 0.28);
  font-size: 13px;
}
@media (max-width: 1024px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
