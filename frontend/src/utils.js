/** 通用工具函数。 */

/** 分钟数格式化为「2小时30分」/「45分钟」 */
export function fmtMinutes(mins) {
  if (mins === null || mins === undefined) return '—'
  const m = Math.abs(Math.round(mins))
  if (m < 60) return `${m}分钟`
  const h = Math.floor(m / 60)
  const rest = m % 60
  if (h < 24) return rest ? `${h}小时${rest}分` : `${h}小时`
  const d = Math.floor(h / 24)
  const rh = h % 24
  return rh ? `${d}天${rh}小时` : `${d}天`
}

/** 剩余时间 -> 带符号文案 */
export function fmtRemaining(mins) {
  if (mins === null || mins === undefined) return '—'
  if (mins < 0) return `已超时 ${fmtMinutes(mins)}`
  return `剩 ${fmtMinutes(mins)}`
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
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)}天前`
  return fmtTime(iso)
}

/** SLA 状态判定 */
export function slaState(ticket) {
  const respBreach = ticket.sla_response_breached
  const resolveBreach = ticket.sla_resolve_breached
  const closed = ticket.status === 'closed' || ticket.status === 'resolved'
  if (respBreach || resolveBreach) return { tone: 'danger', label: 'SLA 超时' }
  const remaining = ticket.sla_resolve_remaining
  if (!closed && remaining !== null && remaining < 120) {
    return { tone: 'warn', label: '即将超时' }
  }
  if (closed) return { tone: 'ok', label: 'SLA 达标' }
  return { tone: 'ok', label: 'SLA 正常' }
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
