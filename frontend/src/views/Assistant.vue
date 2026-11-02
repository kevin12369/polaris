<script setup>
import { onMounted, ref } from 'vue'
import { assistantApi } from '../api'
import { fmtRelative } from '../utils'

const engine = ref(null)
const input = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')
const history = ref([])

const SAMPLES = [
  '502 Bad Gateway Error: request to /api/v2/orders timed out after 5000ms',
  '所有用户登录都提示账号或密码错误，服务完全不可用',
  '导出订单报表得到 0 行，但页面明明有 1000 多条记录',
  'docker 容器一直 CrashLoopBackOff，日志报 database connection refused',
]

async function loadStatus() {
  try {
    engine.value = await assistantApi.status()
  } catch (e) {
    engine.value = null
  }
}

async function loadHistory() {
  try {
    history.value = await assistantApi.history()
  } catch (e) {
    history.value = []
  }
}

async function run(text) {
  const q = (text ?? input.value).trim()
  if (!q) return
  input.value = q
  loading.value = true
  error.value = ''
  try {
    result.value = await assistantApi.troubleshoot(q)
    loadHistory()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadHistory()
})
</script>

<template>
  <div class="assistant-page">
    <div class="assistant-grid">
      <!-- 左：输入 -->
      <div class="col">
        <div class="card">
          <div class="card-head">
            <h3>输入报错</h3>
            <span v-if="engine" class="badge" :class="engine.llm_enabled ? 'badge-ok' : 'badge-mute'">
              {{ engine.llm_enabled ? '大模型增强' : '本地规则引擎' }}
            </span>
          </div>
          <div class="card-body">
            <textarea
              v-model="input"
              rows="7"
              placeholder="粘贴客户的报错信息、异常日志或错误描述…&#10;例如：502 Bad Gateway Error: request to /api/v2/orders timed out"
              @keyup.ctrl.enter="run()"
            ></textarea>
            <div class="row-between" style="margin-top: 10px">
              <span class="muted tiny">Ctrl + Enter 快速执行</span>
              <button class="btn btn-primary" :disabled="loading" @click="run()">
                {{ loading ? '分析中…' : '生成排查步骤' }}
              </button>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top: 14px">
          <div class="card-head"><h3>示例报错</h3></div>
          <div class="card-body">
            <button v-for="s in SAMPLES" :key="s" class="sample" @click="run(s)">
              {{ s }}
            </button>
          </div>
        </div>

        <div v-if="history.length" class="card" style="margin-top: 14px">
          <div class="card-head"><h3>最近查询</h3></div>
          <div class="card-body">
            <button
              v-for="h in history.slice(0, 8)"
              :key="h.id"
              class="history-row"
              @click="run(h.query)"
            >
              <span class="truncate grow">{{ h.query }}</span>
              <span class="badge" :class="h.hit ? 'badge-ok' : 'badge-mute'">
                {{ h.hit ? '命中' : '未命中' }}
              </span>
              <span class="muted tiny">{{ fmtRelative(h.created_at) }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 右：输出 -->
      <div class="col">
        <div v-if="error" class="error-box">{{ error }}</div>

        <div v-if="!result" class="card">
          <div class="empty">
            <div class="empty-icon">✦</div>
            输入报错信息后，这里会给出可执行的排查步骤
            <div class="muted" style="margin-top: 10px; font-size: 12px; max-width: 340px; margin-left: auto; margin-right: auto">
              优先检索你的知识库；库里没有匹配时，会按问题分类给出标准排查清单，
              并建议把结论沉淀回知识库。
            </div>
          </div>
        </div>

        <template v-else>
          <div class="card">
            <div class="card-head">
              <h3>诊断结论</h3>
              <div class="row" style="gap: 6px">
                <span class="badge" :class="result.hit ? 'badge-ok' : 'badge-warn'">
                  {{ result.hit ? '知识库命中' : '通用排查清单' }}
                </span>
                <span class="badge badge-mute">置信 {{ Math.round(result.confidence * 100) }}%</span>
                <span class="badge badge-mute">引擎 {{ result.engine }}</span>
              </div>
            </div>
            <div class="card-body">
              <div class="summary">{{ result.summary }}</div>
            </div>
          </div>

          <div class="card" style="margin-top: 14px">
            <div class="card-head"><h3>排查步骤</h3></div>
            <div class="card-body">
              <ol class="steps">
                <li v-for="(s, i) in result.steps" :key="i">
                  <div class="step-title">
                    <span class="step-no">{{ i + 1 }}</span>
                    <strong>{{ s.title }}</strong>
                  </div>
                  <div class="step-detail">{{ s.detail }}</div>
                  <div v-if="s.source" class="step-src">来源：{{ s.source }}</div>
                </li>
              </ol>
            </div>
          </div>

          <div v-if="result.matched_articles?.length" class="card" style="margin-top: 14px">
            <div class="card-head"><h3>引用的知识库条目</h3></div>
            <div class="card-body">
              <div v-for="a in result.matched_articles" :key="a.id" class="matched">
                <div class="grow">
                  <div class="row" style="gap: 7px">
                    <span style="font-size: 13px">{{ a.title }}</span>
                    <span class="badge badge-mute">{{ a.category }}</span>
                  </div>
                  <div v-if="a.summary" class="muted" style="font-size: 12px; margin-top: 3px">
                    {{ a.summary }}
                  </div>
                  <div class="muted tiny" style="margin-top: 3px">
                    相关度 {{ a.score }}
                    <template v-if="a.matched_terms?.length">
                      · 命中词 {{ a.matched_terms.slice(0, 5).join('、') }}
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.assistant-grid {
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}
.sample {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  margin-bottom: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 11.5px;
  line-height: 1.5;
  cursor: pointer;
  transition: border-color 0.14s ease, color 0.14s ease;
}
.sample:hover {
  border-color: var(--accent-border);
  color: var(--text);
}
.history-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 4px;
  border: none;
  background: none;
  color: var(--text-dim);
  font-family: inherit;
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
  border-radius: 4px;
}
.history-row:hover {
  background: var(--bg-elev-2);
  color: var(--text);
}
.summary {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
}
.steps {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: step;
}
.steps li {
  padding: 11px 0;
  border-bottom: 1px solid var(--border);
}
.steps li:last-child { border-bottom: none; }
.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}
.step-no {
  width: 19px;
  height: 19px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--accent-dim);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}
.step-detail {
  margin-top: 5px;
  padding-left: 27px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-dim);
  white-space: pre-wrap;
}
.step-src {
  margin-top: 4px;
  padding-left: 27px;
  font-size: 11.5px;
  color: var(--text-mute);
}
.matched {
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
}
.matched:last-child { border-bottom: none; }
.tiny { font-size: 11.5px; }
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
  .assistant-grid { grid-template-columns: 1fr; }
}
</style>
