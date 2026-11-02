import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import { session } from './store'
import './styles.css'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '仪表盘' } },
  { path: '/tickets', name: 'tickets', component: () => import('./views/Tickets.vue'), meta: { title: '工单' } },
  { path: '/tickets/:id', name: 'ticket-detail', component: () => import('./views/TicketDetail.vue'), meta: { title: '工单详情' } },
  { path: '/kb', name: 'kb', component: () => import('./views/Knowledge.vue'), meta: { title: '知识库' } },
  { path: '/assistant', name: 'assistant', component: () => import('./views/Assistant.vue'), meta: { title: 'AI 排障助手' } },
  { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue'), meta: { title: '设置' } },
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
