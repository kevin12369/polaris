<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ticketApi } from '../api'
import { fmtMinutes, fmtRemaining, PRIORITY_TONE, STATUS_TONE } from '../utils'
import { t, catLabel, statusLabel, priLabel } from '../i18n'

const router = useRouter()

const tickets = ref([])
const total = ref(0)
const meta = ref({ categories: [], priorities: [], statuses: [] })
const loading = ref(false)
const showCreate = ref(false)
const error = ref('')
const created = ref(null) // 创建后的返回（分类结果 + 知识库建议）

const filters = ref({ status: 'all', priority: 'all', category: 'all', q: '' })

const newTicket = ref({ title: '', content: '', requester_name: '', requester_email: '' })

const statusOptions = computed(() => [
  { code: 'all', label: '全部状态' },
  ...meta.value.statuses.map((s) => ({ code: s.code, label: s.label })),
])
const priorityOptions = computed(() => [
  { code: 'all', label: '全部优先级' },
  ...meta.value.priorities.map((p) => ({ code: p.code, label: `${p.code} · ${p.label}` })),
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await ticketApi.list({ ...filters.value, limit: 100 })
    tickets.value = res.items
    total.value = res.total
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function submitTicket() {
  error.value = ''
  try {
    const res = await ticketApi.create({ ...newTicket.value, channel: 'portal' })
    created.value = res
    showCreate.value = false
    newTicket.value = { title: '', content: '', requester_name: '', requester_email: '' }
    await load()
  } catch (e) {
    error.value = e.message
  }
}

function openDetail(t) {
  router.push(`/tickets/${t.id}`)
}

function resetFilters() {
  filters.value = { status: 'all', priority: 'all', category: 'all', q: '' }
  load()
}

onMounted(async () => {
  try {
    meta.value = await ticketApi.meta()
  } catch (e) {
    /* 字典加载失败不阻断主流程 */
  }
  load()
})
</script>

<template>
  <div class="tickets-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <input
        v-model="filters.q"
        class="search"
        :placeholder="t('tickets.searchPlaceholder')"
        @keyup.enter="load"
      />
      <select v-model="filters.status" @change="load">
        <option v-for="s in statusOptions" :key="s.code" :value="s.code">{{ s.label }}</option>
      </select>
      <select v-model="filters.priority" @change="load">
        <option v-for="p in priorityOptions" :key="p.code" :value="p.code">{{ p.label }}</option>
      </select>
      <select v-model="filters.category" @change="load">
        <option value="all">{{ t('tickets.allCategory') }}</option>
        <option v-for="c in meta.categories" :key="c" :value="c">{{ c }}</option>
      </select>
      <button class="btn" @click="resetFilters">{{ t('tickets.reset') }}</button>
      <div class="grow"></div>
      <span class="muted total">{{ t('tickets.count', { n: total }) }}</span>
      <button class="btn btn-primary" @click="showCreate = true">＋ {{ t('tickets.new') }}</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <!-- 创建结果提示 -->
    <div v-if="created" class="result-banner fade-in">
      <div class="grow">
        <strong>{{ t('tickets.createdSuccess') }}</strong>
        <span class="dim"> — AI 判定为「{{ created.ticket.category }}」/ {{ created.ticket.priority }}，
          置信度 {{ Math.round(created.ticket.confidence * 100) }}%</span>
        <div v-if="created.suggestions.length" class="suggest-line">
          {{ t('tickets.suggestedKb') }}
          <span v-for="s in created.suggestions" :key="s.id" class="badge badge-info">{{ s.title }}</span>
        </div>
      </div>
      <button class="btn btn-sm" @click="openDetail(created.ticket)">{{ t('tickets.viewBtn') }}</button>
      <button class="btn btn-ghost btn-sm" @click="created = null">✕</button>
    </div>

    <!-- 列表 -->
    <div class="card table-wrap">
      <div v-if="loading" class="empty">{{ t('common.loading') }}</div>
      <div v-else-if="!tickets.length" class="empty">
        <div class="empty-icon">▤</div>
        {{ t('tickets.empty') }}
      </div>
      <div v-else class="table-scroll">
        <table class="data">
          <thead>
            <tr>
              <th style="width: 92px">{{ t('tickets.col.code') }}</th>
              <th>{{ t('tickets.col.title') }}</th>
              <th style="width: 96px">{{ t('tickets.col.priority') }}</th>
              <th style="width: 104px">{{ t('tickets.col.category') }}</th>
              <th style="width: 92px">{{ t('tickets.col.status') }}</th>
              <th style="width: 118px">{{ t('tickets.col.sla') }}</th>
              <th style="width: 84px">{{ t('tickets.col.created') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tk in tickets" :key="tk.id" @click="openDetail(tk)">
              <td class="mono muted">{{ tk.code }}</td>
              <td>
                <div class="row" style="gap: 7px">
                  <span class="truncate">{{ tk.title }}</span>
                  <span v-if="tk.kb_hit" class="badge badge-info" title="已关联知识库">◫</span>
                </div>
                <div class="requester muted">{{ tk.requester_name || '—' }}</div>
              </td>
              <td>
                <span class="badge" :class="`badge-${PRIORITY_TONE[tk.priority]}`">{{ tk.priority }}</span>
              </td>
              <td class="dim">{{ catLabel(tk.category) }}</td>
              <td>
                <span class="badge" :class="`badge-${STATUS_TONE[tk.status]}`">{{ statusLabel(tk.status, tk.status_label) }}</span>
              </td>
              <td>
                <span
                  class="mono"
                  :class="tk.sla_resolve_breached ? 'overdue' : tk.sla_resolve_remaining < 120 ? 'soon' : 'muted'"
                >
                  {{ fmtRemaining(tk.sla_resolve_remaining) }}
                </span>
                <div class="muted tiny">{{ t('tickets.responseTime', { t: fmtMinutes(tk.response_minutes) }) }}</div>
              </td>
              <td class="muted tiny">{{ tk.created_at?.slice(5, 10) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新建工单弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal fade-in">
        <div class="modal-head">
          <h3>{{ t('tickets.form.title') }}</h3>
          <button class="btn btn-ghost btn-sm" @click="showCreate = false">✕</button>
        </div>
        <form class="modal-body" @submit.prevent="submitTicket">
          <div class="field">
            <label>{{ t('tickets.form.titleLabel') }}</label>
            <input
              v-model="newTicket.title"
              placeholder="一句话描述问题，例如：导出报表得到 0 行"
              required
              minlength="3"
            />
            <div class="hint">{{ t('tickets.form.hint') }}</div>
          </div>
          <div class="field">
            <label>{{ t('tickets.form.detail') }}</label>
            <textarea
              v-model="newTicket.content"
              rows="5"
              placeholder="现象、报错信息、复现步骤、影响范围"
            ></textarea>
          </div>
          <div class="two-col">
            <div class="field">
              <label>{{ t('tickets.form.requester') }}</label>
              <input v-model="newTicket.requester_name" placeholder="选填" />
            </div>
            <div class="field">
              <label>{{ t('tickets.form.requesterEmail') }}</label>
              <input v-model="newTicket.requester_email" type="email" placeholder="选填" />
            </div>
          </div>
          <div class="modal-foot">
            <button type="button" class="btn" @click="showCreate = false">{{ t('common.cancel') }}</button>
            <button type="submit" class="btn btn-primary">{{ t('tickets.form.submit') }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.total {
  font-size: 12.5px;
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
.result-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
  padding: 11px 14px;
  border-radius: var(--radius);
  background: rgba(63, 185, 80, 0.07);
  border: 1px solid rgba(63, 185, 80, 0.28);
  font-size: 13px;
}
.suggest-line {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-dim);
}
.requester {
  font-size: 11.5px;
  margin-top: 2px;
}
.tiny {
  font-size: 11.5px;
}
.overdue {
  color: var(--danger);
  font-weight: 500;
}
.soon {
  color: var(--warn);
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
/* 窄屏时表格横向滚动，避免列被裁切 */
.table-scroll {
  overflow-x: auto;
}
.table-scroll table.data {
  min-width: 780px;
}
@media (max-width: 640px) {
  .two-col {
    grid-template-columns: 1fr;
  }
  .search {
    width: 100%;
  }
}
</style>
