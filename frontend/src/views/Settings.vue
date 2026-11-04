<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { session } from '../store'
import { t } from '../i18n'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const isDefault = ref(true)

const form = ref({
  work_days: [0, 1, 2, 3, 4],
  work_start_hour: 9,
  work_end_hour: 18,
  holidays: [],
  extra_workdays: [],
})

// 内置法定节假日（只读，展示给用户看）
const builtinHolidays = ref([])
const builtinExtra = ref([])
// 自定义休假日的新增输入
const newHoliday = ref('')
const newExtra = ref('')

const DAYS = computed(() => [
  { v: 0, label: t('day.mon') },
  { v: 1, label: t('day.tue') },
  { v: 2, label: t('day.wed') },
  { v: 3, label: t('day.thu') },
  { v: 4, label: t('day.fri') },
  { v: 5, label: t('day.sat') },
  { v: 6, label: t('day.sun') },
])

const isAdmin = () => session.user?.role === 'admin'

function toggleDay(v) {
  const idx = form.value.work_days.indexOf(v)
  if (idx >= 0) form.value.work_days.splice(idx, 1)
  else form.value.work_days.push(v)
  form.value.work_days.sort((a, b) => a - b)
}

function addHoliday() {
  const d = newHoliday.value.trim()
  if (!d) return
  if (!form.value.holidays.includes(d)) form.value.holidays.push(d)
  form.value.holidays.sort()
  newHoliday.value = ''
}

function removeHoliday(d) {
  form.value.holidays = form.value.holidays.filter((x) => x !== d)
}

function addExtra() {
  const d = newExtra.value.trim()
  if (!d) return
  if (!form.value.extra_workdays.includes(d)) form.value.extra_workdays.push(d)
  form.value.extra_workdays.sort()
  newExtra.value = ''
}

function removeExtra(d) {
  form.value.extra_workdays = form.value.extra_workdays.filter((x) => x !== d)
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/settings/work-schedule')
    form.value = {
      work_days: res.work_days,
      work_start_hour: res.work_start_hour,
      work_end_hour: res.work_end_hour,
      holidays: res.custom_holidays || [],
      extra_workdays: res.custom_extra_workdays || [],
    }
    builtinHolidays.value = res.builtin_holidays || []
    builtinExtra.value = res.builtin_extra_workdays || []
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
      holidays: form.value.holidays,
      extra_workdays: form.value.extra_workdays,
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
    success.value = t('s.restored')
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
        <h3>{{ t('s.schedule') }}</h3>
        <span v-if="isDefault" class="badge badge-mute">{{ t('s.scheduleDefault') }}</span>
        <span v-else class="badge badge-info">{{ t('s.scheduleCustom') }}</span>
      </div>
      <div class="card-body">
        <p class="muted intro">{{ t('s.scheduleIntro') }}</p>

        <div v-if="error" class="msg error">{{ error }}</div>
        <div v-if="success" class="msg success">{{ success }}</div>

        <div class="field">
          <label>{{ t('s.workdays') }}</label>
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
            <label>{{ t('s.start') }}</label>
            <select v-model.number="form.work_start_hour" :disabled="!isAdmin()">
              <option v-for="h in 24" :key="h" :value="h - 1">{{ h - 1 }}:00</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('s.end') }}</label>
            <select v-model.number="form.work_end_hour" :disabled="!isAdmin()">
              <option v-for="h in 24" :key="h" :value="h + 1">{{ h }}:00</option>
            </select>
          </div>
        </div>

        <div class="preview muted">
          {{ t('s.preview') }}
          <strong>{{ form.work_end_hour - form.work_start_hour }} {{ t('s.hoursUnit') }}</strong>
          {{ t('s.weekly') }}
          <strong>{{ (form.work_end_hour - form.work_start_hour) * form.work_days.length }} {{ t('s.hoursUnit') }}</strong>
        </div>

        <!-- 节假日 -->
        <div class="section">
          <div class="section-head">
            <h4>{{ t('s.holidays') }}</h4>
            <span class="muted tiny">{{ t('s.holidaysHint') }}</span>
          </div>

          <div class="builtin-note muted">
            {{ t('s.builtinHolidays') }}
            <span class="date-chips">
              <span v-for="d in builtinHolidays" :key="d" class="chip chip-static">{{ d.slice(5) }}</span>
            </span>
          </div>
          <div v-if="builtinExtra.length" class="builtin-note muted">
            {{ t('s.builtinExtra') }}
            <span class="date-chips">
              <span v-for="d in builtinExtra" :key="d" class="chip chip-work">{{ d.slice(5) }}</span>
            </span>
          </div>

          <div class="field">
            <label>{{ t('s.customHolidays') }}</label>
            <div class="add-row">
              <input
                v-model="newHoliday"
                type="date"
                class="input"
                :disabled="!isAdmin()"
                @keyup.enter="addHoliday"
              />
              <button class="btn btn-sm" :disabled="!isAdmin() || !newHoliday" @click="addHoliday">
                {{ t('common.add') }}
              </button>
            </div>
            <div v-if="form.holidays.length" class="date-chips custom">
              <span v-for="d in form.holidays" :key="d" class="chip chip-custom">
                {{ d }}
                <button
                  v-if="isAdmin()"
                  class="chip-x"
                  :title="t('common.remove')"
                  @click="removeHoliday(d)"
                >×</button>
              </span>
            </div>
            <p v-else class="muted tiny">{{ t('s.noCustomHolidays') }}</p>
          </div>

          <div class="field">
            <label>{{ t('s.customExtra') }}</label>
            <div class="add-row">
              <input
                v-model="newExtra"
                type="date"
                class="input"
                :disabled="!isAdmin()"
                @keyup.enter="addExtra"
              />
              <button class="btn btn-sm" :disabled="!isAdmin() || !newExtra" @click="addExtra">
                {{ t('common.add') }}
              </button>
            </div>
            <div v-if="form.extra_workdays.length" class="date-chips custom">
              <span v-for="d in form.extra_workdays" :key="d" class="chip chip-work-custom">
                {{ d }}
                <button
                  v-if="isAdmin()"
                  class="chip-x"
                  :title="t('common.remove')"
                  @click="removeExtra(d)"
                >×</button>
              </span>
            </div>
            <p v-else class="muted tiny">{{ t('s.noCustomExtra') }}</p>
          </div>
        </div>

        <div v-if="!isAdmin()" class="msg mute">
          {{ t('s.adminOnly') }}
        </div>
        <div v-else class="actions">
          <button class="btn" :disabled="saving" @click="resetDefault">{{ t('s.restoreDefault') }}</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">
            {{ saving ? t('common.saving') : t('common.save') }}
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

/* ---------- 节假日区块 ---------- */
.section {
  margin: 18px 0 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.section-head h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.builtin-note {
  margin-bottom: 8px;
  font-size: 11.5px;
  line-height: 1.8;
}
.date-chips {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-left: 4px;
}
.date-chips.custom {
  display: flex;
  margin: 8px 0 0;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.6;
}
.chip-static {
  background: rgba(242, 85, 90, 0.12);
  border: 1px solid rgba(242, 85, 90, 0.3);
  color: #ff9ea1;
}
.chip-work {
  background: rgba(63, 185, 80, 0.1);
  border: 1px solid rgba(63, 185, 80, 0.28);
  color: #7ee787;
}
.chip-custom {
  background: var(--bg-elev-2);
  border: 1px solid var(--border-strong);
  color: var(--text-dim);
}
.chip-work-custom {
  background: var(--bg-elev-2);
  border: 1px solid var(--border-strong);
  color: #7ee787;
}
.chip-x {
  padding: 0 2px;
  border: none;
  background: none;
  color: var(--text-mute);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.chip-x:hover {
  color: var(--danger);
}
.add-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.add-row .input {
  flex: 1;
  min-width: 0;
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
