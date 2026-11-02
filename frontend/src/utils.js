/** 通用工具函数。 */

import { L, lang } from './i18n'

/**
 * 分钟数格式化为「2小时30分」/「45分钟」
 * 语言相关文案通过 i18n 的 L() 解析，随界面语言切换。
 */
export function fmtMinutes(mins) {
  if (mins === null || mins === undefined) return '—'
  const m = Math.abs(Math.round(mins))
  const unitMin = L('分钟|minutes')
  const unitHour = L('小时|hours')
  const unitDay = L('天|days')
  if (m < 60) return `${m}${unitMin}`
  const h = Math.floor(m / 60)
  const rest = m % 60
  if (h < 24) return rest ? `${h}${unitHour}${rest}${unitMin}` : `${h}${unitHour}`
  const d = Math.floor(h / 24)
  const rh = h % 24
  return rh ? `${d}${unitDay}${rh}${unitHour}` : `${d}${unitDay}`
}

/** 剩余时间 -> 带符号文案 */
export function fmtRemaining(mins) {
  if (mins === null || mins === undefined) return '—'
  if (mins < 0) return `${L('已超时 |Overdue ')}${fmtMinutes(mins)}`
  return `${L('剩 |in ')}${fmtMinutes(mins)}`
}

/** ISO 时间 -> MM-DD HH:mm */
export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (Number.isNaN(d.getTime())) return '—'
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 相对时间 */
export function fmtRelative(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const diff = (Date.now() - d.getTime()) / 1000
  if (Number.isNaN(diff)) return '—'
  const justNow = L('刚刚|just now')
  const minAgo = L('分钟前|min ago')
  const hourAgo = L('小时前|hr ago')
  const dayAgo = L('天前|days ago')
  if (diff < 60) return justNow
  if (diff < 3600) return `${Math.floor(diff / 60)} ${minAgo}`
  if (diff < 86400) return `${Math.floor(diff / 3600)} ${hourAgo}`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} ${dayAgo}`
  return fmtTime(iso)
}

/** SLA 状态判定 */
export function slaState(ticket) {
  const respBreach = ticket.sla_response_breached
  const resolveBreach = ticket.sla_resolve_breached
  const closed = ticket.status === 'closed' || ticket.status === 'resolved'
  if (respBreach || resolveBreach) return { tone: 'danger', label: L('SLA 超时|SLA breached') }
  const remaining = ticket.sla_resolve_remaining
  if (!closed && remaining !== null && remaining < 120) {
    return { tone: 'warn', label: L('即将超时|Due soon') }
  }
  if (closed) return { tone: 'ok', label: L('SLA 达标|On track') }
  return { tone: 'ok', label: L('SLA 正常|On track') }
}

/** 分类 -> 徽章色 */
export const PRIORITY_TONE = { P1: 'p1', P2: 'p2', P3: 'p3', P4: 'p4' }

export const STATUS_TONE = {
  new: 'info',
  triaged: 'info',
  in_progress: 'warn',
  pending: 'mute',
  resolved: 'ok',
  closed: 'mute',
}

/** 数值转百分比字符串 */
export function pct(v, digits = 1) {
  if (v === null || v === undefined) return '—'
  return `${Number(v).toFixed(digits)}%`
}
