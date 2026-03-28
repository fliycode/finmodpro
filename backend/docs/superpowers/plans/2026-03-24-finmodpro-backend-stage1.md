# FinModPro Backend Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 FinModPro 后端第一阶段可联调版本，包含 MySQL / Redis 环境变量结构、真实 JWT access token 注册登录闭环、健康检查保留、MVC 分层整理与 README 补全。

**Architecture:** 保留 Django 现有项目骨架，在认证域内拆出 controller/service/model 职责，并新增独立健康检查 app。数据库与缓存配置通过环境变量切换，默认本地回落到 SQLite 与本地缓存，保证可启动与可测试。

**Tech Stack:** Django 5, SQLite (default local), optional MySQL/Redis config, custom HS256 JWT

---

### Task 1: Write failing API tests

**Files:**
- Modify: `authentication/tests.py`
- Create: `systemcheck/tests.py`

- [x] Step 1: 先把注册/登录测试改成真实 JWT 响应结构
- [x] Step 2: 运行测试并确认因 JWT service 缺失而失败
- [x] Step 3: 补健康检查独立测试
- [x] Step 4: 重新确认目标测试覆盖最小联调闭环

### Task 2: Implement authentication MVC layers

**Files:**
- Create: `authentication/models.py`
- Create: `authentication/services/auth_service.py`
- Create: `authentication/services/jwt_service.py`
- Create: `authentication/controllers/auth_controller.py`
- Modify: `authentication/urls.py`

- [x] Step 1: 拆出用户摘要、注册与登录 service
- [x] Step 2: 实现 access token 生成与校验
- [x] Step 3: 控制层只保留参数解析与响应组装
- [x] Step 4: 路由改接入 controller

### Task 3: Implement config and health organization

**Files:**
- Create: `config/env.py`
- Modify: `config/settings.py`
- Modify: `config/urls.py`
- Create: `systemcheck/apps.py`
- Create: `systemcheck/controllers/health_controller.py`
- Create: `systemcheck/urls.py`

- [x] Step 1: 抽出环境变量读取函数
- [x] Step 2: 增加 MySQL / Redis / JWT 配置项
- [x] Step 3: 独立健康检查 app 与路由
- [x] Step 4: 保证默认本地配置可运行

### Task 4: Document and verify

**Files:**
- Create: `.env.example`
- Modify: `README.md`

- [x] Step 1: 补示例环境变量
- [x] Step 2: 补充运行方式、测试方式、完成边界与 MVC 说明
- [x] Step 3: 运行 `python manage.py test authentication systemcheck`
- [x] Step 4: 运行 `python manage.py check`
- [x] Step 5: 运行 `python manage.py migrate`
