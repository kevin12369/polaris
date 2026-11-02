<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authApi } from '../api'
import { startSession } from '../store'
import { t } from '../i18n'

const router = useRouter()
const route = useRoute()

const mode = ref('login') // login | register
const form = ref({ company_name: '', name: '', email: '', password: '', industry: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    let res
    if (mode.value === 'login') {
      res = await authApi.login(form.value.email.trim(), form.value.password)
    } else {
      res = await authApi.register({
        company_name: form.value.company_name.trim(),
        name: form.value.name.trim(),
        email: form.value.email.trim(),
        password: form.value.password,
        industry: form.value.industry.trim() || null,
      })
    }
    startSession(res)
    router.push(route.query.redirect || '/dashboard')
  } catch (e) {
    error.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}

function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}
</script>

<template>
  <div class="login-page">
    <div class="login-card fade-in">
      <div class="login-head">
        <div class="brand-mark">✦</div>
        <h1>{{ t('login.title') }}</h1>
        <p class="muted">
          {{ mode === 'login' ? t('login.subtitle') : t('login.switchRegister') }}
        </p>
      </div>

      <form @submit.prevent="submit">
        <template v-if="mode === 'register'">
          <div class="field">
            <label>{{ t('login.companyName') }}</label>
            <input v-model="form.company_name" :placeholder="t('login.companyPlaceholder')" required />
          </div>
          <div class="field">
            <label>{{ t('login.yourName') }}</label>
            <input v-model="form.name" :placeholder="t('login.namePlaceholder')" required />
          </div>
          <div class="field">
            <label>{{ t('login.industry') }}</label>
            <input v-model="form.industry" :placeholder="t('login.industryPlaceholder')" />
          </div>
        </template>

        <div class="field">
          <label>{{ t('login.email') }}</label>
          <input v-model="form.email" type="email" placeholder="you@company.com" required />
        </div>
        <div class="field">
          <label>{{ t('login.password') }}</label>
          <input
            v-model="form.password"
            type="password"
            :placeholder="t('login.passwordHint')"
            required
            minlength="6"
          />
        </div>

        <div v-if="error" class="error-box">{{ error }}</div>

        <button class="btn btn-primary btn-block" type="submit" :disabled="loading">
          {{ loading ? t('common.saving') : mode === 'login' ? t('login.submit') : t('login.submitRegister') }}
        </button>
      </form>

      <div class="login-foot">
        <span class="muted">{{ mode === 'login' ? t('login.hasAccount') : t('login.noAccount') }}</span>
        <button class="btn btn-ghost btn-sm" type="button" @click="switchMode">
          {{ mode === 'login' ? t('login.signup') : t('login.toLogin') }}
        </button>
      </div>

      <div v-if="mode === 'login'" class="demo-tip">
        <strong>{{ t('login.demoTitle') }}</strong>
        <span class="mono">demo@acme.com / demo1234</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(900px 500px at 50% -10%, rgba(91, 124, 250, 0.1), transparent 70%),
    var(--bg);
}
.login-card {
  width: 100%;
  max-width: 372px;
  padding: 28px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
}
.login-head {
  text-align: center;
  margin-bottom: 22px;
}
.brand-mark {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), #8b5cf6);
  color: #fff;
  font-weight: 700;
  font-size: 19px;
}
.login-head h1 {
  margin: 0 0 5px;
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.login-head p {
  margin: 0;
  font-size: 13px;
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
.login-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 16px;
  font-size: 12.5px;
}
.demo-tip {
  margin-top: 16px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  border: 1px dashed var(--border-strong);
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
}
.demo-tip strong {
  font-size: 11.5px;
  color: var(--text-dim);
}
</style>
