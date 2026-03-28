# FinModPro Backend Stage 1 Design

## Goal

在现有 Django 最小骨架上，完成适合前后端联调的第一阶段后端版本：保留健康检查，提供基于真实 access token 的注册/登录闭环，并把配置与代码结构整理到可持续演进的形态。

## Scope

- 保留 `GET /api/health`
- 实现 `POST /api/auth/register`
- 实现 `POST /api/auth/login`
- JWT 仅保留 access token
- 配置切换到面向 MySQL / Redis 的环境变量结构
- 按 MVC 思路拆出 route / controller / service / model 责任

## Architecture

- `config` 负责环境变量与 Django 项目级配置
- `authentication` 负责认证域
- `systemcheck` 负责健康检查域
- 控制层只做请求解析与响应
- 服务层负责认证与 JWT 逻辑
- 模型层当前复用 Django 内置 `User`

## Key Decisions

1. 默认本地仍使用 SQLite，保证无需 MySQL / Redis 也能启动与测试
2. JWT 采用 access token 最小闭环，不引入 refresh token
3. 不新增复杂用户模型，当前阶段直接复用 Django `User`
4. 不依赖外部 JWT 库，使用标准库生成 HS256 token，降低环境阻塞

## Risks

- 切到真实 MySQL 时仍需补充对应驱动与数据库联通验证
- 打开 Redis 配置后仍需确保运行环境存在 Redis 客户端依赖与实例
- 当前没有鉴权中间件或受保护业务接口，JWT 闭环只覆盖签发与校验
