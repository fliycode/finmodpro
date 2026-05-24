"""
系统巡检应用 (systemcheck app)

类比 SpringBoot: 相当于一个独立的后台管理模块 (Actuator + Admin)，
负责系统健康检查、审计日志记录和管理仪表盘功能。

核心能力:
- 健康检查: 数据库/Redis 连通性探测 (类似 Spring Actuator /health)
- 审计日志: 操作审计事件记录和查询 (类似 Spring Data Audit)
- 管理仪表盘: 系统概览统计 (文档数、风险数、模型调用量等)
- 演示数据: 开发环境演示数据播种
"""
