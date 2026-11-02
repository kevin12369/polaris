<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { session } from '../store'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const isDefault = ref(true)

const form = ref({
  work_days: [0, 1, 2, 3, 4],
  work_start_hour: 9,
  work_end_hour: 18,
})

const DAYS = [
  { v: 0, label: '周一' },
  { v: 1, label: '周二' },
  { v: 2, label: '周三' },
  { v: 3, label: '周四' },
  { v: 4, label: '周五' },
  { v: 5, label: '周六' },
  { v: 6, label: '周日' },
]

const isAdmin = () => session.user?.role === 'admin'

function toggleDay(v) {
  const idx = form.value.work_days.indexOf(v)
  if (idx >= 0) form.value.work_days.splice(idx, 1)
  else form.value.work_days.push(v)
  form.value.work_days.sort((a, b) => a - b)
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/settings/work-schedule')
    form.value = {
      work_days: res.work_days,
      work_start_hour: res.work_start_hour,
      work_end_hour: res.work_end_hour,
    }
    isDefault.value = res.is_default
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    const res = await api.put('/settings/work-schedule', {
      work_days: form.value.work_days,
      work_start_hour: Number(form.value.work_start_hour),
      work_end_hour: Number(form.value.work_end_hour),
    })
    isDefault.value = false
    success.value = res.note
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function resetDefault() {
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    await api.put('/settings/work-schedule', {
      work_days: [0, 1, 2, 3, 4],
      work_start_hour: 9,
      work_end_hour: 18,
    })
    await load()
    success.value = '已恢复默认排班（周一至周五 09:00-18:00）。'
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <div class="card" style="max-width: 620px">
      <div class="card-head">
        <h3>工作时间表</h3>
        <span v-if="isDefault" class="badge badge-mute">默认</span>
        <span v-else class="badge badge-info">自定义</span>
      </div>
      <div class="card-body">
        <p class="muted intro">
          SLA 倒计时按工作时间计算。周末和晚上不计入。
          如果你们周末也值班，把对应日期勾上即可 —— SLA 会自动按新排班计算。
        </p>

        <div v-if="error" class="msg error">{{ error }}</div>
        <div v-if="success" class="msg success">{{ success }}</div>

        <div class="field">
          <label>工作日</label>
          <div class="day-row">
            <button
              v-for="d in DAYS"
              :key="d.v"
              class="day-btn"
              :class="{ on: form.work_days.includes(d.v) }"
              :disabled="!isAdmin()"
              @click="toggleDay(d.v)"
            >
              {{ d.label }}
            </button>
          </div>
        </div>

        <div class="two-col">
          <div class="field">
            <label>上班时间</label>
            <select v-model.number="form.work_start_hour" :disabled="!isAdmin()">
              <option v-for="h in 24" :key="h" :value="h - 1">{{ h - 1 }}:00</option>
            </select>
          </div>
          <div class="field">
            <label>下班时间</label>
            <select v-model.number="form.work_end_hour" :disabled="!isAdmin()">
              <option v-for="h in 24" :key="h" :value="h + 1">{{ h }}:00</option>
            </select>
          </div>
        </div>

        <div class="preview muted">
          每天工作时长：
          <strong>{{ form.work_end_hour - form.work_start_hour }} 小时</strong>
          · 每周共
          <strong>{{ (form.work_end_hour - form.work_start_hour) * form.work_days.length }} 小时</strong>
        </div>

        <div v-if="!isAdmin()" class="msg mute">
          仅管理员可修改工作时间表。
        </div>
        <div v-else class="actions">
          <button class="btn" :disabled="saving" @click="resetDefault">恢复默认</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 620px;
}
.intro {
  margin: 0 0 16px;
  font-size: 12.5px;
  line-height: 1.7;
}
.day-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.day-btn {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  color: var(--text-dim);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.14s ease;
}
.day-btn:hover:not(:disabled) {
  border-color: var(--accent-border);
  color: var(--text);
}
.day-btn.on {
  background: var(--accent-dim);
  border-color: var(--accent-border);
  color: var(--accent);
  font-weight: 500;
}
.day-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.preview {
  padding: 10px 12px;
  margin-bottom: 16px;
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  font-size: 12.5px;
}
.preview strong {
  color: var(--text);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.msg {
  padding: 8px 11px;
  margin-bottom: 14px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
}
.msg.error {
  background: rgba(242, 85, 90, 0.1);
  border: 1px solid rgba(242, 85, 90, 0.3);
  color: #ff9ea1;
}
.msg.success {
  background: rgba(63, 185, 80, 0.09);
  border: 1px solid rgba(63, 185, 80, 0.28);
  color: #7ee787;
}
.msg.mute {
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  color: var(--text-mute);
}
@media (max-width: 560px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}
</style>
