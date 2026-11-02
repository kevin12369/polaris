<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { endSession, session } from './store'
import { t, lang, setLang } from './i18n'

const route = useRoute()
const router = useRouter()

const company = computed(() => session.company)
const user = computed(() => session.user)
const navOpen = ref(false)

const isAuthed = computed(() => !!session.token)

const navItems = computed(() => [
  { name: 'dashboard', label: t('nav.dashboard'), icon: '◈', to: '/dashboard' },
  { name: 'tickets', label: t('nav.tickets'), icon: '▤', to: '/tickets' },
  { name: 'kb', label: t('nav.kb'), icon: '◫', to: '/kb' },
  { name: 'assistant', label: t('nav.assistant'), icon: '✦', to: '/assistant' },
  { name: 'settings', label: t('nav.settings'), icon: '⚙', to: '/settings' },
])

function logout() {
  endSession()
  router.push({ name: 'login' })
}

function toggleLang() {
  setLang(lang.value === 'zh' ? 'en' : 'zh')
}
</script>

<template>
  <div v-if="!isAuthed" class="auth-shell">
    <RouterView />
  </div>

  <div v-else class="app-shell">
    <aside class="sidebar" :class="{ open: navOpen }">
      <div class="brand">
        <div class="brand-mark">✦</div>
        <div class="grow">
          <div class="brand-name truncate">{{ t('brand.name') }}</div>
          <div class="brand-sub truncate">{{ company?.name || t('common.unnamed') }}</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="nav-item"
          :class="{ active: route.name === item.name || (item.name === 'tickets' && route.name === 'ticket-detail') }"
          @click="navOpen = false"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <button class="lang-toggle" :title="t('common.langSwitch')" @click="toggleLang">
          {{ lang === 'zh' ? 'EN' : '中文' }}
        </button>
        <div class="user-card">
          <div class="avatar">{{ (user?.name || '?').slice(0, 1) }}</div>
          <div class="grow">
            <div class="user-name truncate">{{ user?.name }}</div>
            <div class="user-role">{{ user?.role === 'admin' ? t('nav.role.admin') : t('nav.role.agent') }}</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm btn-block" @click="logout">{{ t('nav.logout') }}</button>
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <button class="btn btn-ghost btn-sm menu-btn" @click="navOpen = !navOpen">☰</button>
        <div class="topbar-title">{{ route.meta.titleKey ? t(route.meta.titleKey) : t('brand.name') }}</div>
        <div class="grow"></div>
        <span class="plan-pill">{{ company?.plan === 'trial' ? t('nav.plan.trial') : company?.plan || t('nav.plan.trial') }}</span>
      </header>

      <main class="content">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <div v-if="navOpen" class="nav-backdrop" @click="navOpen = false"></div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ---------- 侧边栏 ---------- */
.sidebar {
  width: 216px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px;
  border-bottom: 1px solid var(--border);
}
.brand-mark {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), #8b5cf6);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}
.brand-name {
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.brand-sub {
  font-size: 11.5px;
  color: var(--text-mute);
}

.nav {
  flex: 1;
  padding: 10px 8px;
  overflow-y: auto;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 10px;
  margin-bottom: 2px;
  border-radius: var(--radius-sm);
  color: var(--text-dim);
  font-size: 13.5px;
  font-weight: 500;
  transition: background 0.12s ease, color 0.12s ease;
}
.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
}
.nav-icon {
  width: 16px;
  text-align: center;
  font-size: 13px;
  opacity: 0.9;
}

.sidebar-foot {
  padding: 10px;
  border-top: 1px solid var(--border);
}
.lang-toggle {
  width: 100%;
  height: 26px;
  margin-bottom: 6px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-elev-2);
  color: var(--accent);
  font-family: var(--mono);
  font-size: 11.5px;
  cursor: pointer;
  transition: border-color 0.14s ease, color 0.14s ease;
}
.lang-toggle:hover {
  border-color: var(--accent-border);
  color: var(--accent-hover);
}
.user-card {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 8px;
  margin-bottom: 6px;
  border-radius: var(--radius-sm);
}
.avatar {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--bg-elev-2);
  border: 1px solid var(--border-strong);
  font-size: 12px;
  font-weight: 600;
}
.user-name {
  font-size: 12.5px;
  font-weight: 500;
}
.user-role {
  font-size: 11px;
  color: var(--text-mute);
}

/* ---------- 主区 ---------- */
.main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 50px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.topbar-title {
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.plan-pill {
  padding: 3px 9px;
  border-radius: 20px;
  background: var(--accent-dim);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  font-size: 11.5px;
  font-weight: 500;
}
.menu-btn {
  display: none;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.nav-backdrop {
  display: none;
}

/* ---------- 登录页全屏 ---------- */
.auth-shell {
  height: 100vh;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.16s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 860px) {
  .sidebar {
    position: fixed;
    z-index: 40;
    height: 100vh;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  .sidebar.open {
    transform: none;
  }
  .menu-btn {
    display: inline-flex;
  }
  .nav-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 30;
    background: rgba(0, 0, 0, 0.55);
  }
  .content {
    padding: 14px;
  }
}
</style>
