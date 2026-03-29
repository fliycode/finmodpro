# FinModPro Demo Data

当前仓库提供一个可重复执行的演示数据命令：

```bash
cd /root/finmodpro/backend
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py seed_rbac
./.venv/bin/python manage.py seed_demo_data
```

## 作用

该命令会重建一套最小可演示数据，覆盖：

- `demo-admin` 用户
- `demo-analyst` 用户
- 2 篇知识库文档元数据与切块
- 1 个成功入库的 ingestion task
- 1 个问答会话与消息
- 1 条 retrieval log
- 2 条风险事件（含 `approved` / `pending`）
- 1 份公司风险报告

## 默认账号

- 用户名：`demo-admin`
- 用户名：`demo-analyst`
- 默认密码：`DemoPass123!`

说明：

- 当前系统没有单独的 `analyst` 角色表，`demo-analyst` 会被放入现有 `member` 组
- 命令可重复执行；会先删除旧的 demo 数据，再重新写入

## 适用演示路径

这套数据主要用于稳定展示：

- 登录
- 知识库文档列表 / 文档详情元数据
- 问答历史
- 风险事件列表 / 审核状态
- 风险报告列表与详情

它不尝试伪造完整的“实时上传 + 异步入库 + 在线模型调用”过程，而是优先保证已有页面/API 可稳定展示。
