import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import { session } from './store'
import { t } from './i18n'
import './styles.css'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { titleKey: 'nav.dashboard' } },
  { path: '/tickets', name: 'tickets', component: () => import('./views/Tickets.vue'), meta: { titleKey: 'nav.tickets' } },
  { path: '/tickets/:id', name: 'ticket-detail', component: () => import('./views/TicketDetail.vue'), meta: { titleKey: 'nav.tickets' } },
  { path: '/kb', name: 'kb', component: () => import('./views/Knowledge.vue'), meta: { titleKey: 'nav.kb' } },
  { path: '/assistant', name: 'assistant', component: () => import('./views/Assistant.vue'), meta: { titleKey: 'nav.assistant' } },
  { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue'), meta: { titleKey: 'nav.settings' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = session.token
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'dashboard' }
  }
})

createApp(App).use(router).mount('#app')
