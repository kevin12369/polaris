<script setup>
import { computed, onMounted, ref } from 'vue'
import { dashboardApi } from '../api'
import { fmtMinutes, fmtRemaining } from '../utils'

const data = ref(null)
const loading = ref(false)
const error = ref('')
const days = ref(30)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await dashboardApi.get(days.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ---- 折线图（纯 SVG）----
const chart = computed(() => {
  const trend = data.value?.trend || []
  if (trend.length < 2) return null
  const W = 720
  const H = 180
  const padL = 34
  const padB = 24
  const padT = 12
  const maxV = Math.max(1, ...trend.map((d) => Math.max(d.created, d.resolved)))
  const innerW = W - padL - 12
  const innerH = H - padT - padB
  const stepX = innerW / (trend.length - 1)
  const yOf = (v) => padT + innerH - (v / maxV) * innerH

  const build = (key) =>
    trend.map((d, i) => `${padL + i * stepX},${yOf(d[key])}`).join(' ')

  const areaPath = `M ${padL},${padT + innerH} L ${trend
    .map((d, i) => `${padL + i * stepX},${yOf(d.created)}`)
    .join(' L ')} L ${padL + (trend.length - 1) * stepX},${padT + innerH} Z`

  // x 轴标签：最多 6 个
  const labelIdx = []
  const step = Math.max(1, Math.floor(trend.length / 6))
  for (let i = 0; i < trend.length; i += step) labelIdx.push(i)

  return {
    W,
    H,
    maxV,
    createdLine: build('created'),
    resolvedLine: build('resolved'),
    areaPath,
    labelIdx,
    trend,
    yOf,
    xOf: (i) => padL + i * stepX,
  }
})

// ---- 横向条形图 ----
const catBars = computed(() => {
  const rows = data.value?.by_category || []
  const max = Math.max(1, ...rows.map((r) => r.count))
  return rows.map((r) => ({ ...r, pct: (r.count / max) * 100 }))
})

const statusBars = computed(() => {
  const rows = data.value?.by_status || []
  const max = Math.max(1, ...rows.map((r) => r.count))
  return rows.map((r) => ({ ...r, pct: (r.count / max) * 100 }))
})

const metrics = computed(() => data.value?.metrics || {})

const cards = computed(() => [
  {
    key: 'total',
    label: '工单量',
    value: metrics.value.total_tickets ?? 0,
    unit: '单',
    sub: `待处理 ${metrics.value.open_tickets ?? 0} · 已解决 ${metrics.value.resolved_tickets ?? 0}`,
    tone: 'accent',
  },
  {
    key: 'resp',
    label: '平均响应时长',
    value: fmtMinutes(metrics.value.avg_response_minutes ?? 0),
    unit: '',
    sub: `响应超时率 ${metrics.value.response_timeout_rate ?? 0}%`,
    tone: metrics.value.response_timeout_rate > 10 ? 'danger' : 'ok',
  },
  {
    key: 'timeout',
    label: '超时率',
    value: metrics.value.timeout_rate ?? 0,
    unit: '%',
    sub: `超时 ${metrics.value.response_timeout_count ?? 0} 响应 / ${metrics.value.resolve_timeout_count ?? 0} 解决`,
    tone: metrics.value.timeout_rate > 15 ? 'danger' : metrics.value.timeout_rate > 5 ? 'warn' : 'ok',
  },
  {
    key: 'kb',
    label: '知识库命中率',
    value: metrics.value.kb_hit_rate ?? 0,
    unit: '%',
    sub: `${metrics.value.kb_linked_count ?? 0} 单已沉淀 · 共 ${metrics.value.kb_articles ?? 0} 条`,
    tone: (metrics.value.kb_hit_rate ?? 0) >= 50 ? 'ok' : 'warn',
  },
])

onMounted(load)
</script>

<template>
  <div class="dash">
    <div class="row-between" style="margin-bottom: 14px">
      <div>
        <h2 style="margin: 0; font-size: 17px; font-weight: 600">服务概览</h2>
        <span class="muted" style="font-size: 12.5px">近 {{ days }} 天</span>
      </div>
      <div class="row" style="gap: 6px">
        <button
          v-for="d in [7, 30, 90]"
          :key="d"
          class="btn btn-sm"
          :class="{ 'btn-primary': days === d }"
          @click="days = d; load()"
        >
          {{ d }} 天
        </button>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div v-if="loading" class="empty">加载中…</div>

    <template v-else-if="data">
      <!-- 指标卡 -->
      <div class="metric-grid">
        <div v-for="c in cards" :key="c.key" class="metric card">
          <div class="metric-label">{{ c.label }}</div>
          <div class="metric-value" :class="`tone-${c.tone}`">
            {{ c.value }}<span class="metric-unit">{{ c.unit }}</span>
          </div>
          <div class="metric-sub muted">{{ c.sub }}</div>
        </div>
      </div>

      <!-- 趋势 -->
      <div class="card" style="margin-top: 14px">
        <div class="card-head">
          <h3>工单趋势</h3>
          <div class="row" style="gap: 12px">
            <span class="legend"><i class="dot dot-created"></i>新建</span>
            <span class="legend"><i class="dot dot-resolved"></i>解决</span>
          </div>
        </div>
        <div class="card-body">
          <div v-if="!chart" class="empty">数据不足</div>
          <svg v-else :viewBox="`0 0 ${chart.W} ${chart.H}`" class="trend-chart">
            <!-- 网格线 -->
            <line
              v-for="i in 4"
              :key="`g${i}`"
              :x1="34"
              :x2="chart.W - 12"
              :y1="12 + (i - 1) * ((chart.H - 36) / 3)"
              :y2="12 + (i - 1) * ((chart.H - 36) / 3)"
              stroke="#232c38"
              stroke-width="1"
            />
            <text
              v-for="i in 4"
              :key="`t${i}`"
              :x="28"
              :y="16 + (i - 1) * ((chart.H - 36) / 3)"
              text-anchor="end"
              fill="#6b7885"
              font-size="10"
            >
              {{ Math.round(chart.maxV * (4 - i) / 3) }}
            </text>
            <!-- 面积 -->
            <path :d="chart.areaPath" fill="rgba(91,124,250,0.09)" />
            <!-- 折线 -->
            <polyline
              :points="chart.createdLine"
              fill="none"
              stroke="#5b7cfa"
              stroke-width="2"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
            <polyline
              :points="chart.resolvedLine"
              fill="none"
              stroke="#3fb950"
              stroke-width="2"
              stroke-linejoin="round"
              stroke-linecap="round"
              stroke-dasharray="4 3"
            />
            <!-- x 轴标签 -->
            <text
              v-for="i in chart.labelIdx"
              :key="`x${i}`"
              :x="chart.xOf(i)"
              :y="chart.H - 7"
              text-anchor="middle"
              fill="#6b7885"
              font-size="10"
            >
              {{ chart.trend[i].date.slice(5) }}
            </text>
          </svg>
        </div>
      </div>

      <!-- 分布 -->
      <div class="dist-grid">
        <div class="card">
          <div class="card-head"><h3>分类分布</h3></div>
          <div class="card-body">
            <div v-if="!catBars.length" class="empty">暂无数据</div>
            <div v-for="r in catBars" :key="r.category" class="bar-row">
              <span class="bar-label truncate">{{ r.category }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: r.pct + '%' }"></div>
              </div>
              <span class="bar-val mono">{{ r.count }}</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>状态分布</h3></div>
          <div class="card-body">
            <div v-if="!statusBars.length" class="empty">暂无数据</div>
            <div v-for="r in statusBars" :key="r.code" class="bar-row">
              <span class="bar-label truncate">{{ r.label }}</span>
              <div class="bar-track">
                <div class="bar-fill alt" :style="{ width: r.pct + '%' }"></div>
              </div>
              <span class="bar-val mono">{{ r.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 待办 + 高频 -->
      <div class="dist-grid">
        <div class="card">
          <div class="card-head"><h3>待处理工单（按优先级）</h3></div>
          <div class="card-body">
            <div v-if="!data.recent?.length" class="empty">没有待处理工单</div>
            <RouterLink
              v-for="t in data.recent"
              :key="t.id"
              :to="`/tickets/${t.id}`"
              class="todo-row"
            >
              <span class="badge" :class="`badge-${t.priority.toLowerCase()}`">{{ t.priority }}</span>
              <span class="grow truncate todo-title">{{ t.title }}</span>
              <span
                class="mono tiny"
                :class="t.sla_response_breached ? 'overdue' : 'muted'"
              >
                {{ fmtRemaining(t.sla_resolve_remaining) }}
              </span>
            </RouterLink>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <h3>高频知识条目</h3>
            <span class="muted tiny">被检索命中次数</span>
          </div>
          <div class="card-body">
            <div v-if="!data.top_kb?.length" class="empty">暂无数据</div>
            <RouterLink
              v-for="a in data.top_kb"
              :key="a.id"
              :to="`/kb?focus=${a.id}`"
              class="todo-row"
            >
              <span class="grow truncate todo-title">{{ a.title }}</span>
              <span class="badge badge-mute">{{ a.hits }} 次</span>
            </RouterLink>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.metric { padding: 14px 16px; }
.metric-label {
  font-size: 11.5px;
  color: var(--text-mute);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.metric-value {
  margin: 7px 0 4px;
  font-size: 27px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.metric-unit {
  margin-left: 3px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-mute);
}
.tone-accent { color: var(--accent); }
.tone-ok { color: var(--ok); }
.tone-warn { color: var(--warn); }
.tone-danger { color: var(--danger); }
.metric-sub { font-size: 11.5px; }

.trend-chart { width: 100%; height: auto; }
.legend {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: var(--text-dim);
}
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-created { background: var(--accent); }
.dot-resolved { background: var(--ok); }

.dist-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 14px;
}
.bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}
.bar-label {
  width: 82px;
  flex-shrink: 0;
  font-size: 12.5px;
  color: var(--text-dim);
}
.bar-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-elev-2);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--accent);
  transition: width 0.4s ease;
}
.bar-fill.alt { background: #8b5cf6; }
.bar-val {
  width: 30px;
  text-align: right;
  font-size: 12px;
  color: var(--text-dim);
}
.todo-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 4px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.todo-row:last-child { border-bottom: none; }
.todo-row:hover { background: var(--bg-elev-2); }
.todo-title { font-size: 12.5px; }
.tiny { font-size: 11.5px; }
.overdue { color: var(--danger); }
.error-box {
  margin-bottom: 12px;
  padding: 8px 11px;
  border-radius: var(--radius-sm);
  background: rgba(242, 85, 90, 0.1);
  border: 1px solid rgba(242, 85, 90, 0.3);
  color: #ff9ea1;
  font-size: 12.5px;
}
@media (max-width: 1080px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 720px) {
  .metric-grid { grid-template-columns: 1fr; }
  .dist-grid { grid-template-columns: 1fr; }
}
</style>
