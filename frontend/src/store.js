/**
 * 响应式会话状态。
 *
 * 背景：直接用 computed(() => !!localStorage.getItem('sw_token')) 会有坑 ——
 * localStorage 不是响应式源，computed 首次求值后会被缓存，登录成功后侧边栏
 * 永远不会重新渲染。这里用 reactive 持有会话状态，所有写入口统一走本模块。
 */
import { reactive } from 'vue'
import { setToken, clearSession } from './api'

function readUser() {
  try {
    return JSON.parse(localStorage.getItem('sw_user') || 'null')
  } catch {
    return null
  }
}

function readCompany() {
  try {
    return JSON.parse(localStorage.getItem('sw_company') || 'null')
  } catch {
    return null
  }
}

export const session = reactive({
  token: localStorage.getItem('sw_token') || '',
  user: readUser(),
  company: readCompany(),
})

export function isAuthed() {
  return !!session.token
}

/** 登录成功 / 注册成功后调用，同步写入内存与 localStorage。 */
export function startSession({ access_token, user, company }) {
  setToken(access_token)
  session.token = access_token
  session.user = user
  session.company = company
  localStorage.setItem('sw_user', JSON.stringify(user))
  localStorage.setItem('sw_company', JSON.stringify(company))
}

/** 登出。 */
export function endSession() {
  clearSession()
  session.token = ''
  session.user = null
  session.company = null
}
