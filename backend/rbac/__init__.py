"""
rbac/ — 角色权限控制 (RBAC) 应用

此应用负责用户权限管理和用户资料管理。没有独立的 models.py，
而是直接使用 Django 内置的 User / Group / Permission 模型。

核心概念:
  - Role (角色) = Django Group → 一组 Permission 的集合
  - Permission = "app_label.codename" 格式的权限标识 (如 "auth.view_dashboard")
  - 三个系统角色: super_admin / admin / member
  - 支持自定义角色（custom role）

目录结构:
  - controllers/admin_controller.py    — 管理员接口: 用户管理、角色 CRUD
  - controllers/profile_controller.py  — 个人资料: 查看/编辑/改密码/换头像
  - services/rbac_service.py           — RBAC 核心: 角色 & 用户管理
  - services/authz_service.py          — 认证与鉴权装饰器
  - services/profile_stats_service.py  — 用户统计（提问数/文档数等）
  - management/commands/seed_rbac.py   — 初始化系统角色权限

SpringBoot 类比:
  - Group ≈ @ManyToMany 角色实体
  - Permission ≈ GrantedAuthority / 权限字符串
  - @permission_required ≈ @PreAuthorize("hasAuthority('...')")
"""
