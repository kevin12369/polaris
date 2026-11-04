/**
 * 轻量国际化。
 *
 * 不引入 vue-i18n —— 那会让打包体积翻倍，而这个项目只需要中英双语。
 * 字典值统一用「中文|English」格式，由 L() 按当前语言取半边。
 *
 * 用法：
 *   import { t, L, setLang, lang } from '../i18n'
 *   t('nav.dashboard')            // 取字典
 *   L('分类 | Category')           // 直接解析双语串
 */
import { reactive } from 'vue'

/** 中文 | English —— 注意竖线前后不要有多余空格 */
export function L(s) {
  if (s == null) return ''
  const i = s.indexOf('|')
  if (i < 0) return s
  return lang.value === 'zh' ? s.slice(0, i) : s.slice(i + 1)
}

const STORAGE_KEY = 'polaris_lang'

function detectLang() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'zh' || saved === 'en') return saved
  // 跟随浏览器语言
  const nav = (navigator.language || 'zh-CN').toLowerCase()
  return nav.startsWith('zh') ? 'zh' : 'en'
}

export const lang = reactive({ value: detectLang() })

export function setLang(code) {
  lang.value = code === 'en' ? 'en' : 'zh'
  localStorage.setItem(STORAGE_KEY, lang.value)
  document.documentElement.setAttribute('lang', lang.value === 'zh' ? 'zh-CN' : 'en')
}

/**
 * 读取字典并按当前语言解析。
 * vars 用于插值：t('tickets.count', { n: 12 }) -> "共 12 条"
 */
export function t(key, vars) {
  const raw = DICT[key]
  if (raw === undefined) return key // 未定义时回退到 key，便于发现遗漏
  let out = L(raw)
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.split('{' + k + '}').join(String(v))
    }
  }
  return out
}

/** 字典：中文|English */
export const DICT = {
  // ---------- 通用 ----------
  'common.cancel': '取消|Cancel',
  'common.confirm': '确定|Confirm',
  'common.save': '保存|Save',
  'common.saving': '保存中…|Saving…',
  'common.reset': '重置|Reset',
  'common.close': '关闭|Close',
  'common.delete': '删除|Delete',
  'common.edit': '编辑|Edit',
  'common.create': '新建|Create',
  'common.search': '搜索|Search',
  'common.loading': '加载中…|Loading…',
  'common.empty': '暂无数据|No data',
  'common.minutes': '分钟|minutes',
  'common.hours': '小时|hours',
  'common.days': '天|days',
  'common.remaining': '剩 |in ',
  'common.overdue': '已超时 |Overdue ',
  'common.completed': '已完成|Completed',
  'common.all': '全部|All',
  'common.add': '添加|Add',
  'common.remove': '移除|Remove',
  'common.unnamed': '未命名企业|Unnamed workspace',
  'common.langSwitch': '切换语言|Switch language',

  // ---------- 侧边栏与导航 ----------
  'brand.name': '北极星 Polaris|Polaris',
  'brand.sub': '客服工单管理平台|Ticket Management Platform',
  'nav.dashboard': '仪表盘|Dashboard',
  'nav.tickets': '工单|Tickets',
  'nav.kb': '知识库|Knowledge Base',
  'nav.assistant': 'AI 排障|AI Assistant',
  'nav.settings': '设置|Settings',
  'nav.logout': '退出登录|Log out',
  'nav.role.admin': '管理员|Admin',
  'nav.role.agent': '坐席|Agent',
  'nav.plan.trial': '试用版|Trial',
  'nav.menu': '菜单|Menu',

  // ---------- 登录页 ----------
  'login.title': '北极星 Polaris|Polaris',
  'login.subtitle': '客服工单管理平台|Ticket Management Platform',
  'login.email': '邮箱|Email',
  'login.password': '密码|Password',
  'login.passwordHint': '至少 6 位|At least 6 characters',
  'login.submit': '登录|Log in',
  'login.hasAccount': '还没有空间？|Need an account?',
  'login.noAccount': '已有账号？|Already registered?',
  'login.signup': '免费开通|Create free workspace',
  'login.toLogin': '去登录|Log in',
  'login.demoTitle': '演示账号|Demo account',
  'login.switchRegister': '30 秒开通一个独立空间|Create your workspace in 30 seconds',
  'login.switchLogin': '登录你的企业空间|Log in to your workspace',
  'login.companyName': '公司 / 团队名称|Company / team name',
  'login.yourName': '你的姓名|Your name',
  'login.industry': '行业（选填）|Industry (optional)',
  'login.companyPlaceholder': '例如：Acme 科技|e.g. Acme Inc.',
  'login.namePlaceholder': '例如：张三|e.g. Alex Chen',
  'login.industryPlaceholder': '例如：企业软件|e.g. Enterprise software',
  'login.emailPlaceholder': 'you@company.com|you@company.com',
  'login.submitRegister': '开通空间并进入|Create workspace & enter',

  // ---------- 工单列表 ----------
  'tickets.title': '工单|Tickets',
  'tickets.searchPlaceholder': '搜索标题 / 描述 / 工单号…|Search title, description or ID…',
  'tickets.allStatus': '全部状态|All statuses',
  'tickets.allPriority': '全部优先级|All priorities',
  'tickets.allCategory': '全部分类|All categories',
  'tickets.count': '共 {n} 条|{n} tickets',
  'tickets.new': '＋ 新建工单|New ticket',
  'tickets.empty': '还没有工单，点击「新建工单」开始|No tickets yet — create your first one',
  'tickets.col.code': '编号|ID',
  'tickets.col.title': '标题|Title',
  'tickets.col.priority': '优先级|Priority',
  'tickets.col.category': '分类|Category',
  'tickets.col.status': '状态|Status',
  'tickets.col.sla': '解决倒计时|Resolution SLA',
  'tickets.col.created': '创建|Created',
  'tickets.responseTime': '响应 {t}|Response {t}',
  'tickets.kbBadge': '已关联知识库|Linked to knowledge base',
  'tickets.createdSuccess': '工单已创建|Ticket created',
  'tickets.aiJudged': 'AI 判定为「{cat}」/ {pri}，置信度 {conf}%|AI classified as "{cat}" / {pri} ({conf}% confidence)',
  'tickets.suggestedKb': '自动匹配知识库：|Matched from your knowledge base:',
  'tickets.view': '查看|Open',
  'tickets.form.title': '新建工单|New ticket',
  'tickets.form.titleLabel': '标题 *|Title *',
  'tickets.form.titlePlaceholder': '一句话描述问题，例如：导出报表得到 0 行|One line describing the issue',
  'tickets.form.hint': '留空分类与优先级，将由 AI 自动判定|Category and priority are inferred automatically',
  'tickets.form.detail': '详细描述|Details',
  'tickets.form.detailPlaceholder': '现象、报错信息、复现步骤、影响范围|Symptoms, error output, repro steps, impact',
  'tickets.form.requester': '报障人|Reporter',
  'tickets.form.requesterEmail': '报障人邮箱|Reporter email',
  'tickets.form.optional': '选填|optional',
  'tickets.form.submit': '提交并自动分类|Submit & classify',

  // ---------- 工单详情 ----------
  'td.sla': 'SLA 倒计时|SLA countdown',
  'td.sla.response': '首次响应|First response',
  'td.sla.resolve': '解决时限|Resolution',
  'td.sla.target': '目标 {t}|Target {t}',
  'td.sla.due': '截止 {t}|Due {t}',
  'td.sla.answered': '已响应|Responded',
  'td.sla.breached': '响应超时|Response breached',
  'td.sla.overdue': '解决超时|Resolution breached',
  'td.sla.soon': '即将超时|Due soon',
  'td.sla.ok': 'SLA 正常|On track',
  'td.sla.met': 'SLA 达标|On track',
  'td.sla.elapsed': '已响应耗时|Time to first response',
  'td.sla.resolved': '解决耗时|Time to resolve',
  'td.flow': '状态流转|Move ticket',
  'td.note': '备注（将记入处理记录）|Note (added to the timeline)',
  'td.commentOnly': '仅添加备注|Add note only',
  'td.suggest': '知识库建议|Suggested articles',
  'td.suggestEmpty': '没有匹配到相关条目。可在下方「AI 排障」中生成排查步骤。|No match — generate troubleshooting steps below.',
  'td.timeline': '处理记录|Timeline',
  'td.timelineEmpty': '暂无记录|No activity yet',
  'td.resolution': '处理记录|Resolution',
  'td.kbPromote': '知识沉淀|Knowledge capture',
  'td.kbPromoteDesc': '关单时把这次的处理过程存成知识库条目，下次同样的问题 AI 可直接给出答案。|Store the resolution so the assistant can reuse it next time.',
  'td.kbPromoteBtn': '◫ 沉淀为知识库|Promote to knowledge base',
  'td.kbLinked': '已关联条目|Linked articles',
  'td.aiAssist': 'AI 排障|AI assistant',
  'td.aiPlaceholder': '粘贴报错信息或日志片段|Paste the error message or log excerpt',
  'td.aiRun': '生成排查步骤|Generate steps',
  'td.aiAnalyzing': '分析中…|Analysing…',
  'td.createdVia': '创建于|Created',
  'td.source': '来源|Source',
  'td.aiJudgedBadge': 'AI 判定 {c}%|AI {c}%',

  // ---------- 知识库 ----------
  'kb.title': '知识库|Knowledge Base',
  'kb.searchPlaceholder': '搜索知识库…（支持 BM25 全文检索）|Search the knowledge base…',
  'kb.count': '{n} 条|{n} articles',
  'kb.new': '＋ 新建条目|New article',
  'kb.empty': '知识库还是空的|The knowledge base is empty',
  'kb.noMatch': '没有匹配的条目|No matching articles',
  'kb.selectHint': '从左侧选择一个条目查看详情|Select an article to read it',
  'kb.helpful': '👍 有用 {n}|👍 Helpful {n}',
  'kb.steps': '排查步骤|Troubleshooting steps',
  'kb.updated': '更新于 {t}|Updated {t}',
  'kb.hits': '命中 {a} 次 · 浏览 {b} 次|{a} hits · {b} views',
  'kb.fromTicket': '工单沉淀|Promoted from ticket',
  'kb.form.title': '新建知识库条目|New article',
  'kb.form.titleLabel': '标题 *|Title *',
  'kb.form.titlePlaceholder': '例如：502 网关错误的排查路径|e.g. Diagnosing 502 gateway errors',
  'kb.form.category': '分类|Category',
  'kb.form.summary': '摘要|Summary',
  'kb.form.summaryHint': '留空则自动生成|Leave blank to auto-generate',
  'kb.form.tags': '标签|Tags',
  'kb.form.tagsHint': '逗号分隔，如：登录, 高频|Comma separated, e.g. login, frequent',
  'kb.form.content': '内容|Content',
  'kb.form.contentPlaceholder': '根因、现象、处理方法|Root cause, symptoms, resolution',
  'kb.deleteConfirm': '确认删除知识库条目「{t}」？|Delete the article "{t}"?',

  // ---------- AI 排障助手 ----------
  'ai.title': 'AI 排障助手|AI Troubleshooting Assistant',
  'ai.subtitle': '输入报错 → 检索知识库 → 输出排查步骤|Enter an error → search the knowledge base → get steps',
  'ai.placeholder': "粘贴客户的报错信息、异常日志或错误描述…\n例如：502 Bad Gateway Error: request to /api/v2/orders timed out|Paste the customer's error message or log excerpt…",
  'ai.ctrlEnter': 'Ctrl + Enter 快速执行|Ctrl + Enter to run',
  'ai.run': '生成排查步骤|Generate steps',
  'ai.analyzing': '分析中…|Analysing…',
  'ai.samples': '示例报错|Sample errors',
  'ai.history': '最近查询|Recent queries',
  'ai.emptyTitle': '输入报错信息后，这里会给出可执行的排查步骤|Enter an error to get actionable steps',
  'ai.emptyDesc': '优先检索你的知识库；库里没有匹配时，会按问题分类给出标准排查清单，并建议把结论沉淀回知识库。|Your knowledge base is searched first. On a miss you get a standard checklist for the issue category, plus a prompt to capture the outcome.',
  'ai.diagnosis': '诊断结论|Diagnosis',
  'ai.steps': '排查步骤|Troubleshooting steps',
  'ai.matched': '引用的知识库条目|Articles referenced',
  'ai.badge.hit': '知识库命中|KB hit',
  'ai.badge.miss': '通用排查清单|Generic checklist',
  'ai.badge.conf': '置信|Confidence',
  'ai.badge.engine': '引擎|Engine',
  'ai.src': '来源|Source',
  'ai.relevance': '相关度|Relevance',
  'ai.terms': '命中词|Matched terms',
  'ai.historyHit': '命中|Hit',
  'ai.historyMiss': '未命中|Miss',

  // ---------- 仪表盘 ----------
  'd.title': '服务概览|Service overview',
  'd.last': '近 {n} 天|Last {n} days',
  'd.days': '{n} 天|{n}d',
  'd.m.tickets': '工单量|Tickets',
  'd.m.ticketsSub': '待处理 {a} · 已解决 {b}|{a} open · {b} resolved',
  'd.m.response': '平均响应时长|Avg first response',
  'd.m.responseSub': '响应超时率 {a}%|{a}% response breaches',
  'd.m.timeout': '超时率|SLA breach rate',
  'd.m.timeoutSub': '超时 {a} 单（响应 {b} · 解决 {c}）|{a} breached ({b} response · {c} resolution)',
  'd.m.kb': '知识库命中率|KB hit rate',
  'd.m.kbSub': '{a} 单已沉淀 · 共 {b} 条|{a} captured · {b} articles',
  'd.trend': '工单趋势|Ticket volume',
  'd.trend.created': '新建|Created',
  'd.trend.resolved': '解决|Resolved',
  'd.byCategory': '分类分布|By category',
  'd.byStatus': '状态分布|By status',
  'd.todo': '待处理工单（按优先级）|Open tickets by priority',
  'd.todoEmpty': '没有待处理工单|No open tickets',
  'd.topKb': '高频知识条目|Most used articles',
  'd.topKbSub': '被检索命中次数|Times matched by search',
  'd.noData': '暂无数据|No data',
  'd.insufficient': '数据不足|Not enough data',

  // ---------- 设置 ----------
  's.title': '设置|Settings',
  's.schedule': '工作时间表|Working hours',
  's.scheduleDefault': '默认|Default',
  's.scheduleCustom': '自定义|Custom',
  's.scheduleIntro':
    'SLA 倒计时按工作时间计算。周末和晚上不计入。如果你们周末也值班，把对应日期勾上即可 —— SLA 会自动按新排班计算。|SLA countdowns run on working hours only — nights and weekends do not count. Tick the days you staff, and countdowns follow your rota.',
  's.workdays': '工作日|Working days',
  's.start': '上班时间|Start',
  's.end': '下班时间|End',
  's.preview': '每天工作时长：|Daily hours: ',
  's.weekly': '· 每周共 |· per week: ',
  's.hoursUnit': ' 小时| hours',
  's.hourUnit': ' 小时| h',
  's.adminOnly': '仅管理员可修改工作时间表。|Only administrators can change the working hours.',
  's.restoreDefault': '恢复默认|Restore defaults',
  's.saved': '已保存|Saved',
  's.holidays': '节假日|Holidays',
  's.holidaysHint':
    '法定节假日不计入 SLA 倒计时，调休上班日照常计时。|Statutory holidays do not count towards SLA countdowns; make-up working days do.',
  's.builtinHolidays': '内置法定假日（不可修改）：|Built-in statutory holidays (read-only):',
  's.builtinExtra': '内置调休上班日：|Built-in make-up working days:',
  's.customHolidays': '额外休假日（如年会、春节封盘）|Extra days off (e.g. company shutdown)',
  's.customExtra': '额外上班日（如值班）|Extra working days (e.g. on-call)',
  's.noCustomHolidays': '暂无额外休假日|No extra days off',
  's.noCustomExtra': '暂无额外上班日|No extra working days',
  'day.mon': '周一|Mon',
  'day.tue': '周二|Tue',
  'day.wed': '周三|Wed',
  'day.thu': '周四|Thu',
  'day.fri': '周五|Fri',
  'day.sat': '周六|Sat',
  'day.sun': '周日|Sun',
  's.restored': '已恢复默认排班（周一至周五 09:00-18:00）。|Restored the default schedule (Mon-Fri, 09:00-18:00).',
  's.note': '新设置仅对之后创建的工单生效；已有工单的 SLA 截止时间保持不变。|New tickets use this schedule. Existing SLA deadlines are unchanged.',


  // ---------- 补充 ----------
  'tickets.allCategory': '全部分类|All categories',
  'tickets.reset': '重置|Reset',
  'tickets.viewBtn': '查看|Open',
  'kb.allSource': '全部来源|All sources',
  'kb.source.manual': '手写|Hand-written',
  'kb.source.ticket': '工单沉淀|Promoted from ticket',
  'td.back': '← 返回|← Back',
  'td.notFound': '工单不存在|Ticket not found',
  's.restoreDefault2': '恢复默认|Restore defaults',

  // ---------- 优先级标签（后端返回中文）----------
  'pri.P1': '致命中断|Critical outage',
  'pri.P2': '严重|Severe',
  'pri.P3': '一般|Normal',
  'pri.P4': '低|Low',

  // ---------- 分类与状态（后端返回的枚举值） ----------
  'cat.账号登录': '账号登录|Account & login',
  'cat.支付账单': '支付账单|Billing & payments',
  'cat.接口API': '接口 API|API & integration',
  'cat.数据问题': '数据问题|Data issues',
  'cat.性能卡顿': '性能卡顿|Performance',
  'cat.部署运维': '部署运维|Deployment & ops',
  'cat.功能缺陷': '功能缺陷|Product defect',
  'cat.咨询其他': '咨询其他|General enquiry',

  'st.new': '待受理|New',
  'st.triaged': '已分类|Triaged',
  'st.in_progress': '处理中|In progress',
  'st.pending': '待客户|Waiting on customer',
  'st.resolved': '已解决|Resolved',
  'st.closed': '已关闭|Closed',
}

/**
 * 后端返回的枚举值 → 本地化文案。
 * 后端返回中文（如 category="账号登录"、status_label="待受理"），
 * 英文界面下需要映射，故按中文 key 反查字典。
 */
export function catLabel(cat) {
  if (!cat) return ''
  const key = 'cat.' + cat
  return DICT[key] !== undefined ? t(key) : cat
}

export function statusLabel(code, label) {
  if (!code) return label || ''
  const key = 'st.' + code
  return DICT[key] !== undefined ? t(key) : label || code
}

/** 优先级标签 → 本地化文案（后端返回中文） */
export function priLabel(priority, fallback) {
  if (!priority) return fallback || ''
  const key = 'pri.' + priority
  return DICT[key] !== undefined ? t(key) : fallback || priority
}
