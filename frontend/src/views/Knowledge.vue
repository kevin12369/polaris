<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { kbApi } from '../api'
import { fmtTime } from '../utils'

const route = useRoute()

const items = ref([])
const categories = ref([])
const total = ref(0)
const mode = ref('list')
const loading = ref(false)
const error = ref('')
const showCreate = ref(false)
const focusId = ref(null)

const query = ref('')
const filterCategory = ref('all')
const filterSource = ref('all')

const form = ref({ title: '', content: '', summary: '', category: '咨询其他', tags: '' })
const detail = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await kbApi.list({
      q: query.value,
      category: filterCategory.value,
      source: filterSource.value,
      limit: 100,
    })
    items.value = res.items
    total.value = res.total
    mode.value = res.mode
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    categories.value = await kbApi.categories()
  } catch (e) {
    categories.value = []
  }
}

async function openItem(id) {
  try {
    detail.value = await kbApi.get(id)
    focusId.value = id
  } catch (e) {
    error.value = e.message
  }
}

async function createArticle() {
  error.value = ''
  try {
    const payload = {
      ...form.value,
      tags: form.value.tags
        .split(/[,，\s]+/)
        .map((t) => t.trim())
        .filter(Boolean),
    }
    const res = await kbApi.create(payload)
    showCreate.value = false
    form.value = { title: '', content: '', summary: '', category: '咨询其他', tags: '' }
    await load()
    await loadCategories()
    openItem(res.id)
  } catch (e) {
    error.value = e.message
  }
}

async function markHelpful() {
  if (!detail.value) return
  await kbApi.helpful(detail.value.id)
  detail.value.helpful += 1
}

async function removeArticle() {
  if (!detail.value) return
  if (!confirm(`确认删除知识库条目「${detail.value.title}」？`)) return
  await kbApi.remove(detail.value.id)
  detail.value = null
  focusId.value = null
  await load()
  await loadCategories()
}

watch([query, filterCategory, filterSource], load)

onMounted(async () => {
  await load()
  await loadCategories()
  if (route.query.focus) openItem(Number(route.query.focus))
})
</script>

<template>
  <div class="kb-page">
    <div class="toolbar">
      <input v-model="query" class="search" placeholder="搜索知识库…（支持 BM25 全文检索）" />
      <select v-model="filterCategory">
        <option value="all">全部分类</option>
        <option v-for="c in categories" :key="c.category" :value="c.category">
          {{ c.category }} ({{ c.count }})
        </option>
      </select>
      <select v-model="filterSource">
        <option value="all">全部来源</option>
        <option value="manual">手写</option>
        <option value="ticket">工单沉淀</option>
      </select>
      <div class="grow"></div>
      <span class="muted total">{{ total }} 条</span>
      <button class="btn btn-primary" @click="showCreate = true">＋ 新建条目</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="kb-grid">
      <!-- 列表 -->
      <div class="kb-list card">
        <div v-if="loading" class="empty">加载中…</div>
        <div v-else-if="!items.length" class="empty">
          <div class="empty-icon">◫</div>
          {{ query ? '没有匹配的条目' : '知识库还是空的' }}
        </div>
        <div
          v-for="it in items"
          :key="it.id"
          class="kb-row"
          :class="{ active: focusId === it.id }"
          @click="openItem(it.id)"
        >
          <div class="grow">
            <div class="kb-row-title truncate">{{ it.title }}</div>
            <div class="kb-row-meta">
              <span class="badge badge-mute">{{ it.category }}</span>
              <span v-if="it.source === 'ticket'" class="badge badge-info" title="由工单沉淀">
                ◫ {{ it.source_ticket_code }}
              </span>
              <span class="muted tiny">命中 {{ it.hits }} · 浏览 {{ it.views }}</span>
            </div>
            <div v-if="it.snippet || it.summary" class="kb-row-sum truncate">
              {{ it.snippet || it.summary }}
            </div>
          </div>
        </div>
      </div>

      <!-- 详情 -->
      <div class="kb-detail card">
        <div v-if="!detail" class="empty">
          <div class="empty-icon">←</div>
          从左侧选择一个条目查看详情
        </div>
        <template v-else>
          <div class="card-head">
            <h3 class="grow truncate">{{ detail.title }}</h3>
            <button class="btn btn-sm" @click="markHelpful">👍 有用 {{ detail.helpful }}</button>
            <button class="btn btn-danger btn-sm" @click="removeArticle">删除</button>
          </div>
          <div class="card-body">
            <div class="row" style="gap: 6px; margin-bottom: 12px">
              <span class="badge badge-mute">{{ detail.category }}</span>
              <span class="badge badge-mute">{{ detail.source === 'ticket' ? '工单沉淀' : '手写' }}</span>
              <span v-for="t in detail.tags" :key="t" class="badge badge-info">{{ t }}</span>
            </div>
            <div v-if="detail.summary" class="kb-summary">{{ detail.summary }}</div>

            <div v-if="detail.steps?.length" class="steps">
              <div class="steps-label">排查步骤</div>
              <ol>
                <li v-for="(s, i) in detail.steps" :key="i">
                  <strong>{{ s.title }}</strong>
                  <div class="muted">{{ s.detail }}</div>
                </li>
              </ol>
            </div>

            <div v-if="detail.content" class="kb-content">{{ detail.content }}</div>

            <div class="kb-foot muted">
              更新于 {{ fmtTime(detail.updated_at) }} · 命中 {{ detail.hits }} 次 · 浏览 {{ detail.views }} 次
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 新建条目 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal fade-in">
        <div class="modal-head">
          <h3>新建知识库条目</h3>
          <button class="btn btn-ghost btn-sm" @click="showCreate = false">✕</button>
        </div>
        <form class="modal-body" @submit.prevent="createArticle">
          <div class="field">
            <label>标题 *</label>
            <input v-model="form.title" required minlength="3" placeholder="例如：502 网关错误的排查路径" />
          </div>
          <div class="field">
            <label>分类</label>
            <select v-model="form.category">
              <option v-for="c in ['账号登录','支付账单','接口API','数据问题','性能卡顿','部署运维','功能缺陷','咨询其他']" :key="c" :value="c">
                {{ c }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>摘要</label>
            <input v-model="form.summary" placeholder="留空则自动生成" />
          </div>
          <div class="field">
            <label>标签</label>
            <input v-model="form.tags" placeholder="逗号分隔，如：登录, 高频" />
          </div>
          <div class="field">
            <label>内容</label>
            <textarea v-model="form.content" rows="6" placeholder="根因、现象、处理方法" />
          </div>
          <div class="modal-foot">
            <button type="button" class="btn" @click="showCreate = false">取消</button>
            <button type="submit" class="btn btn-primary">创建</button>
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
.total { font-size: 12.5px; }
.kb-grid {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}
.kb-list { overflow-y: auto; max-height: calc(100vh - 130px); }
.kb-row {
  display: flex;
  gap: 10px;
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.12s ease;
}
.kb-row:hover { background: var(--bg-elev-2); }
.kb-row.active { background: var(--accent-dim); }
.kb-row-title { font-size: 13px; font-weight: 500; }
.kb-row-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 5px;
  flex-wrap: wrap;
}
.kb-row-sum { margin-top: 4px; font-size: 11.5px; color: var(--text-mute); }
.tiny { font-size: 11px; }
.kb-summary {
  padding: 10px 12px;
  margin-bottom: 14px;
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  border-left: 2px solid var(--accent);
  font-size: 12.5px;
  color: var(--text-dim);
  line-height: 1.6;
}
.steps-label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-mute);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}
.steps ol { margin: 0; padding-left: 20px; font-size: 13px; }
.steps li { margin-bottom: 9px; line-height: 1.6; }
.kb-content {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.65;
}
.kb-foot { margin-top: 18px; font-size: 11.5px; }
.error-box {
  margin-bottom: 12px;
  padding: 8px 11px;
  border-radius: var(--radius-sm);
  background: rgba(242, 85, 90, 0.1);
  border: 1px solid rgba(242, 85, 90, 0.3);
  color: #ff9ea1;
  font-size: 12.5px;
}
@media (max-width: 980px) {
  .kb-grid { grid-template-columns: 1fr; }
  .kb-list { max-height: 380px; }
  .search { width: 100%; }
}
</style>
