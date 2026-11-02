"""技术术语中英别名表。

背景：目标用户（深圳的跨境物流、餐饮软件公司）日常接触的**报错日志是英文的，
但知识库条目是中文写的**。客服把 "timeout" 粘进 AI 排障助手，
期望能命中标题为「连接超时」的知识库条目。

不处理这个错配，检索在真实场景下的命中率会显著低于测试数据。
"""
from __future__ import annotations

# 别名 -> 规范词。规范词本身也会被加入查询 token 集合。
TERM_ALIASES: dict[str, str] = {
    # 超时 / 响应
    "timeout": "超时",
    "timed out": "超时",
    "time out": "超时",
    "etimedout": "超时",
    "read timeout": "超时",
    "connection timeout": "超时",
    "latency": "延迟",
    "delay": "延迟",
    "slow": "缓慢",
    # 连接 / 网络
    "connection refused": "连接拒绝",
    "connection reset": "连接重置",
    "econnrefused": "连接拒绝",
    "econnreset": "连接重置",
    "network": "网络",
    "timeout error": "超时",
    "unreachable": "无法连接",
    "dns": "域名解析",
    "gateway": "网关",
    "gateway timeout": "网关超时",
    "proxy": "代理",
    "load balancer": "负载均衡",
    # 服务 / 部署
    "crashloopbackoff": "容器反复重启",
    "crash loop": "容器反复重启",
    "oomkilled": "内存溢出",
    "out of memory": "内存溢出",
    "container": "容器",
    "docker": "容器",
    "kubernetes": "容器",
    "k8s": "容器",
    "deploy": "部署",
    "deployment": "部署",
    "rollback": "回滚",
    "restart": "重启",
    "health check": "健康检查",
    "nginx": "网关",
    "upstream": "上游",
    "downstream": "下游",
    # 数据库
    "deadlock": "死锁",
    "constraint": "约束",
    "duplicate key": "主键冲突",
    "primary key": "主键",
    "foreign key": "外键",
    "index": "索引",
    "slow query": "慢查询",
    "transaction": "事务",
    "rollback": "回滚",
    "null": "为空",
    "nullpointerexception": "空指针",
    "null pointer": "空指针",
    "sql": "数据库",
    # 认证
    "unauthorized": "未认证",
    "forbidden": "无权限",
    "401": "未认证",
    "403": "无权限",
    "token expired": "令牌过期",
    "jwt": "令牌",
    "login": "登录",
    "logout": "退出登录",
    "password": "密码",
    "sso": "单点登录",
    "permission": "权限",
    "auth": "鉴权",
    # 支付
    "payment": "支付",
    "invoice": "发票",
    "refund": "退款",
    "callback": "回调",
    "webhook": "回调",
    "order": "订单",
    "checkout": "下单",
    # 业务通用
    # 注意：纯数字状态码（500/502/404 等）不做别名扩展 ——
    # 它们已由检索层的"精确短语通道"处理，若在这里扩展成"服务端错误"
    # 会引入过泛的词，反而让不相关文档得分更高（如"5000ms"被当成"500"）。
    "export": "导出",
    "import": "导入",
    "report": "报表",
    "upload": "上传",
    "download": "下载",
    "sync": "同步",
    "cron": "定时任务",
    "scheduled": "定时任务",
    "cache": "缓存",
    "redis": "缓存",
    "mysql": "数据库",
    "postgres": "数据库",
    "sqlite": "数据库",
    "cpu": "处理器",
    "memory": "内存",
    "disk": "磁盘",
    "thread": "线程",
    "pool": "连接池",
    "lock": "锁",
    "sla": "服务时限",
}

# 别名扩展的最小长度门槛：过短的别名（如 "api"）容易误命中
_MIN_ALIAS_LEN = 3


def expand_query(text: str) -> list[str]:
    """返回查询文本中命中的别名对应的规范词列表。"""
    low = (text or "").lower()
    found: list[str] = []
    for alias, canonical in TERM_ALIASES.items():
        if len(alias) < _MIN_ALIAS_LEN:
            continue
        if alias in low:
            found.append(canonical)
    # 去重并保持稳定顺序
    seen: set[str] = set()
    out: list[str] = []
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out
