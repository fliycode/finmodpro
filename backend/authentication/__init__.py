"""
authentication/ — Django 认证应用

负责用户认证全流程：注册、登录、登出、Token 刷新、密码重置。
使用自定义 JWT 方案（不依赖 Django 内置 Session 认证）。

核心设计:
  - Access Token: 短期（15分钟），存于前端内存中，通过 Authorization: Bearer <token> 传递
  - Refresh Token: 长期（1-7天），存于 HTTP-only Cookie 中，防止 XSS 窃取
  - 密码重置: 生成一次性 Token，通过 SHA256 HMAC 哈希存储

目录结构:
  - models.py          — 数据模型 (UserProfile, PasswordResetToken)
  - urls.py            — URL 路由
  - apps.py            — Django App 配置
  - drf_authentication.py  — DRF 认证后端（从请求头提取 JWT）
  - controllers/auth_controller.py  — 视图层（接收 HTTP 请求、调用 Service）
  - services/auth_service.py     — 用户注册/认证业务逻辑
  - services/jwt_service.py      — JWT 令牌创建/验证
  - services/refresh_session_service.py — Refresh Token 会话管理
  - services/password_reset_service.py  — 密码重置流程

SpringBoot 类比: Spring Security + OAuth2 Resource Server 的认证模块
  - controllers ≈ @RestController
  - services ≈ @Service
  - drf_authentication ≈ OncePerRequestFilter（从 Header 解析 Token）
  - models ≈ @Entity（JPA 实体）
"""
