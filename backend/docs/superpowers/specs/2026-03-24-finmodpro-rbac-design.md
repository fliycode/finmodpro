# FinModPro RBAC 设计文档

日期：2026-03-24

## 1. 背景

FinModPro 当前已经具备第一阶段可联调认证能力：

- 前端：Vue + Vite + JavaScript 登录/注册页
- 后端：Django + JWT 最小闭环
- 已有接口：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `GET /api/health`

下一步需要补齐 RBAC（Role-Based Access Control，基于角色的访问控制），用于支撑毕设演示中的登录后权限控制、菜单可见性控制以及后端接口鉴权。

## 2. 目标

本阶段目标不是构建企业级完整权限平台，而是实现一套**适合毕设演示、可讲清楚、可运行、可扩展**的 RBAC 方案。

本方案要求：

1. 直接复用 Django 内置 `User / Group / Permission`
2. 用户可拥有多个角色（即多个 Group）
3. 接口鉴权按权限码判断，角色作为权限集合
4. 前端菜单、页面、按钮可根据角色/权限控制显示
5. 注册用户默认进入普通用户角色
6. 保持现有 JWT 方案，不将完整权限塞入 token

## 3. 为什么选择 Django Group / Permission

本项目当前定位是**毕设演示**，不是正式商用系统第一版，因此优先考虑：

- 开发和联调速度
- 方案可解释性
- 稳定性
- 与 Django 生态一致
- 尽量减少重复造轮子

相比自建完整 RBAC 域模型，直接复用 Django 内置权限体系的优点是：

- 上手快，工作量更小
- Django 原生支持用户、组、权限关系
- 认证和管理逻辑更容易说明
- 适合答辩时介绍“系统基于 Django 内置权限体系实现 RBAC”

因此本阶段明确采用：

- **角色 = Django Group**
- **权限 = Django Permission**
- **用户角色关系 = User.groups**

## 4. 作用域

本阶段采用：

- **系统级 RBAC**

即：

- 所有角色和权限在系统层面统一定义
- 不引入组织级、团队级、项目级多层权限边界

原因：

- 当前演示范围无需多租户或多组织结构
- 系统级 RBAC 足够支撑用户登录后不同菜单与接口能力差异
- 可显著降低实现复杂度

## 5. 用户与角色关系

本阶段采用：

- **一个用户可拥有多个角色（多个 Group）**

这样可以兼顾：

- 标准 RBAC 设计习惯
- 后续扩展灵活性
- 避免“单角色”过早限制系统能力

## 6. 权限校验粒度

本阶段采用：

- **接口按 Permission 校验**
- **角色（Group）只负责聚合 Permission**

也就是说：

- 用户通过所属 Group 获得 Permission
- 后端接口最终判断用户是否拥有某个 Permission
- 前端则基于角色和权限做展示控制

## 7. 角色设计

本阶段定义三类基础角色：

### 7.1 `super_admin`
系统最高权限角色。

用途：

- 演示系统超级管理员
- 可以拥有全部权限

### 7.2 `admin`
业务管理角色。

用途：

- 具备用户查看、基础管理等能力
- 不一定具备系统最高权限

### 7.3 `member`
普通用户角色。

用途：

- 新注册用户默认角色
- 拥有最基础可见页面权限

## 8. 权限设计

权限命名尽量贴合 Django 默认习惯与毕设演示场景，优先采用：

- `view_xxx`
- `add_xxx`
- `change_xxx`
- `delete_xxx`

在此基础上，按演示需要扩展少量业务权限。

建议首批权限如下：

- `view_dashboard`
- `view_user`
- `add_user`
- `change_user`
- `delete_user`
- `view_role`
- `assign_role`

> 说明：`assign_role` 不属于 Django 默认 CRUD 权限，可作为自定义 Permission 增加。

## 9. 角色与权限映射建议

### 9.1 `super_admin`
- 拥有全部权限

### 9.2 `admin`
- `view_dashboard`
- `view_user`
- `add_user`
- `change_user`
- `view_role`

### 9.3 `member`
- `view_dashboard`

> 说明：此映射用于第一阶段演示，后续可根据页面实际情况继续调整。

## 10. JWT 设计

当前认证仍沿用已有 JWT 最小闭环设计。

本阶段 JWT 保持轻量，仅用于标识身份，不直接承载完整角色/权限信息。

### 10.1 JWT 中保留
- `user_id`
- `sub`
- `iat`
- `exp`

### 10.2 JWT 中不放
- 完整 Group 列表
- 完整 Permission 列表
- 菜单树或页面权限

### 10.3 原因
- 权限变更后无需等待旧 token 过期才能生效
- token 更短、更稳定
- 权限逻辑集中在服务端，更易维护

## 11. 后端接口设计

### 11.1 保留现有接口
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/health`

### 11.2 新增核心接口：`GET /api/auth/me`

用于前端登录后获取当前用户身份、角色与权限摘要。

#### 示例响应
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "groups": ["member"],
  "permissions": ["view_dashboard"]
}
```

### 11.3 第二阶段可补接口
如演示需要角色分配功能，可补：

- `GET /api/rbac/groups`
- `GET /api/rbac/permissions`
- `GET /api/rbac/users/{id}/groups`
- `PUT /api/rbac/users/{id}/groups`

本阶段不强制要求全部完成，但应在设计上预留。

## 12. 注册默认行为

用户注册成功后：

1. 创建 Django `User`
2. 自动加入 `member` 组
3. 返回现有 JWT 登录态能力
4. 前端后续通过 `/api/auth/me` 可拿到 `member` 角色和对应权限

## 13. 后端实现方式

虽然底层复用 Django 内置模型，但工程结构仍保持 MVC 思路，避免把权限逻辑散落在各处。

建议新增独立 RBAC 相关模块（命名可为 `rbac` 或 `authorization`）。

### 建议职责划分
- `controllers/`
  - 处理接口请求与响应
- `services/`
  - 封装 Group / Permission 查询、分配、聚合逻辑
- `urls.py`
  - 暴露 RBAC 相关接口

同时补充通用鉴权工具，例如：

- `require_permissions(...)`
- `require_groups(...)`

用于后端接口保护。

## 14. 前端设计

前端权限控制的职责是：

- 提升体验
- 根据当前用户角色/权限控制可见性

不是安全边界本身。

### 前端第一阶段动作
1. 登录成功后保存 JWT
2. 调用 `GET /api/auth/me`
3. 保存当前用户的：
   - 用户信息
   - groups
   - permissions
4. 按 groups / permissions 控制：
   - 页面可见性
   - 菜单可见性
   - 按钮可见性

### 原则
- 前端只做展示控制
- 真正鉴权始终以后端为准

## 15. Redis 设计

虽然项目目标栈包含 Redis，但本阶段 RBAC **不强制把 Redis 作为首要实现项**。

### 当前建议
- 先完成数据库与服务端权限聚合逻辑
- Redis 作为后续优化项预留

### 后续可做方向
- 缓存用户权限聚合结果
- 用户角色变更后清缓存
- 减少高频权限查询开销

由于项目当前以毕设演示为主，此项应排在 RBAC 主功能之后。

## 16. 分阶段实施建议

### Phase 1：RBAC 最小闭环
- 初始化基础 Group 与 Permission
- 注册默认加入 `member`
- 实现 `GET /api/auth/me`
- 后端基础权限校验能力可用
- 前端能根据 `groups / permissions` 控制界面显示

### Phase 2：角色分配与演示完善
- 提供 Group / Permission 查询接口
- 提供用户角色分配接口
- 前端补角色管理相关展示能力（如果需要）

### Phase 3：可选优化
- Redis 缓存权限结果
- 更细化的演示能力
- 更丰富的权限管理页面

## 17. 本阶段明确不做

为保证方案聚焦，本阶段不做以下内容：

- 多租户 / 多组织 / 多项目级权限边界
- 数据范围权限（例如“只能看自己部门数据”）
- refresh token 与复杂登录态治理
- 审计日志系统
- 完整菜单配置平台
- 权限树编辑器
- 复杂审批流

## 18. 验收标准

本阶段完成后，应满足：

1. 系统内存在基础 Group 与 Permission 初始化方案
2. 新注册用户默认属于 `member`
3. 登录后前端可通过 `/api/auth/me` 获取用户角色与权限
4. 后端接口可基于 Permission 做访问控制
5. 前端可根据角色/权限控制页面、菜单、按钮显示
6. 整体方案足够支撑毕设演示中的 RBAC 展示与说明

## 19. 结论

FinModPro 的 RBAC 第一版正式基线确定为：

- **复用 Django 内置 `Group / Permission / User`**
- **系统级 RBAC**
- **多角色用户**
- **接口按 Permission 校验**
- **前端纳入角色/权限可见性控制**

这套方案在当前“毕设演示”目标下，是实现成本、可解释性和展示效果之间最合适的平衡点。
