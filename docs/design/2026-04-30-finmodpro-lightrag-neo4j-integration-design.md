# FinModPro LightRAG（含 Neo4j 可选增强）接入设计

日期：2026-04-30

## 1. Context

FinModPro 当前已经具备完整的知识库摄取与检索主链路：文档上传后进入 `parse -> chunk -> vectorize -> retrieve` 流程，向量主存储为 Milvus，问答层已有 LangGraph 编排与重排序能力。当前系统并不是“没有 RAG”，而是已经有一条正在运行的 RAG 主路径。

当前评估的 LightRAG 不是替代整个系统，而是评估是否把它作为一个独立的图增强检索子系统接入，优先服务于知识库问答增强、文档图谱探索与管理端试点。用户当前偏好是：**尽量直接用 LightRAG，不深改其项目，只接受轻量的 UI 风格对齐**。

本机实测资源也会影响方案：当前生产机资源较紧，LightRAG 单独试跑可启动，Neo4j + LightRAG 联机也可启动，但两者同时运行后整机余量明显变小。因此设计必须把“边界清晰、可回滚、可渐进”作为第一原则，而不是一次性深度并入主系统。

## 2. 当前事实

### 2.1 FinModPro 当前已有能力

- 文档摄取编排在 `backend/knowledgebase/services/document_service.py`
- 文档解析层已支持 `txt/pdf/docx`，并采用独立解析服务思路
- chunk、section chunk、向量化、Milvus 检索与 RAG API 已成型
- 管理端与工作区已有统一的 Vue shell、RBAC、路由与布局模式
- LLM、embedding、rerank 在当前项目内已有现成 API 与基础设施

### 2.2 LightRAG 当前可提供的能力

- 自带 API Server、WebUI、OpenAPI 文档
- 可接外部 LLM / embedding / rerank
- 支持独立 graph / vector / kv / doc status 存储后端
- 默认可用 file-based / NetworkX / NanoVector 轻量模式
- 可切换到 Milvus、Neo4j 等更正式的后端

### 2.3 当前验证结论

- LightRAG 单独试运行成功
- Neo4j + LightRAG 联机试运行成功
- 当前机器上 **Neo4j + LightRAG 可试跑，但不适合直接长期生产常驻**
- Neo4j 不是首发硬依赖；LightRAG 即使不接 Neo4j 也能工作

## 3. Goals / Non-goals

### 3.1 Goals

- 为 FinModPro 提供一条 **可渐进启用** 的 LightRAG 接入路径
- 第一阶段优先复用现有 LLM / embedding / rerank / Milvus 能力
- 将 LightRAG 保持为 **独立 sidecar 子系统**，避免污染主业务边界
- 允许先复用 LightRAG 自带 WebUI，并只做轻量风格对齐
- 为第二阶段引入 Neo4j 作为图后端预留明确扩展点
- 明确部署、鉴权、路由、数据边界、回滚策略和资源风险

### 3.2 Non-goals

- 第一阶段不重写 FinModPro 现有知识库 ingest 主链路
- 第一阶段不把 LightRAG 深度并入 Django 进程
- 第一阶段不要求把 LightRAG WebUI 深改成 FinModPro 原生页面
- 第一阶段不要求所有问答立即切到 LightRAG
- 第一阶段不要求在当前生产机上同时稳定常驻 Neo4j + LightRAG

## 4. 设计原则

- **Sidecar 优先**：LightRAG 作为独立子系统接入，而不是主业务内嵌模块
- **主链路不翻车**：FinModPro 现有知识库主链路继续保留，LightRAG 先增量接入
- **轻 UI、重边界**：UI 只做换壳和微调，不做深度 fork
- **Neo4j 后置**：图后端增强是第二阶段，不是首发阻塞项
- **生产回滚简单**：LightRAG 故障不能拖垮现有知识库、问答和管理端
- **协议优先于绑定**：优先复用当前已有 API，而不是重复部署 embedding / rerank

## 5. Alternatives Considered

### 方案 A：LightRAG 独立 sidecar，第一阶段不启用 Neo4j（推荐）

做法：

- LightRAG 作为独立服务部署
- 复用当前 LLM / embedding / rerank API
- vector storage 优先接现有 Milvus
- graph storage 第一阶段先使用默认轻量实现，或保留 file-based / NetworkX
- 管理端通过独立入口引入其 WebUI，并只做轻量风格对齐

优点：

- 改动最小，最快可落地
- 不会破坏现有 ingest / rag / chat 主链路
- 与当前资源现实更匹配
- 失败时可直接摘除，不影响主系统

缺点：

- 第一阶段图谱能力不算“满配”
- WebUI 与主站体验仍会有轻微割裂
- 会短期存在两套检索能力并行

### 方案 B：LightRAG sidecar + Neo4j 同步首发

做法：

- 首发时就同时落地 LightRAG、Milvus、Neo4j
- 让 LightRAG 从第一天就跑正式图后端

优点：

- 图能力更完整
- 一开始就按目标架构搭建

缺点：

- 对当前机器资源压力过大
- 部署复杂度、排障复杂度、数据迁移复杂度更高
- 首发风险明显高于收益

### 方案 C：深度整合到 FinModPro 主系统，重做自有前后端

做法：

- 把 LightRAG 的前后端核心能力拆进当前仓库
- FinModPro 自己承载 UI、API、鉴权、状态管理与数据编排

优点：

- 最终用户体验最统一
- 长期产品控制力最强

缺点：

- 工程量最大
- 几乎等于 fork + 平台化重写
- 与用户当前“先直接用、少改”的目标冲突

### 推荐结论

**第一阶段采用方案 A。第二阶段按效果与资源情况决定是否进入方案 B 的 Neo4j 增强。方案 C 仅在 LightRAG 被证明是长期核心能力后再考虑。**

## 6. Proposed Design

### 6.1 总体结构

第一阶段的目标结构：

1. FinModPro 继续承担：
   - 用户、权限、RBAC
   - 文档上传、解析、切块、向量化、现有知识库主链路
   - 管理端统一入口与导航
2. LightRAG 作为独立 sidecar 承担：
   - 图增强检索试点
   - 文档图谱探索
   - 独立 API / WebUI
3. 当前已有基础设施复用：
   - LLM API：复用 FinModPro 已接入模型服务
   - embedding API：复用现有服务
   - rerank API：如协议兼容则直接复用
   - vector storage：优先复用现有 Milvus

### 6.2 模块边界

#### FinModPro

负责：

- 统一认证、鉴权、管理端入口
- 控制“谁可以进入 LightRAG 管理面”
- 保留现有知识库主流程与对外主业务 API
- 视需要提供与 Dataset / Document 相关的桥接信息

不负责：

- 在自身进程内承载 LightRAG 的图谱逻辑
- 直接持有 LightRAG 内部状态存储逻辑

#### LightRAG

负责：

- 自己的检索、图谱、图查询和 WebUI
- 自己的索引状态与图相关数据
- 自己的 API 文档与管理面

不负责：

- 接管 FinModPro 用户体系
- 替代 FinModPro 所有现有知识库功能

#### Neo4j（第二阶段可选）

负责：

- 在确认图谱价值后，承载 LightRAG 的正式图存储

不负责：

- 直接作为 FinModPro 业务数据库
- 取代 MySQL / Milvus 的既有职责

## 7. 第一阶段设计（推荐首发）

### 7.1 部署形态

第一阶段建议：

- LightRAG 作为独立服务
- 不在 Django / Celery 容器内安装 LightRAG 依赖
- 使用反向代理把它挂到 FinModPro 的管理端路径下，例如：
  - `/admin/lightrag`
  - `/admin/lightrag/api/*`

### 7.2 存储与模型配置

第一阶段建议：

- **Vector Storage**：Milvus
- **Graph Storage**：默认轻量图实现（不先启用 Neo4j）
- **KV / Doc Status**：先用 LightRAG 默认持久化
- **LLM**：复用现有模型 API
- **Embedding**：复用现有 embedding API
- **Rerank**：协议兼容则直接复用，不兼容则先关闭

### 7.3 UI 集成方式

第一阶段不把 LightRAG WebUI 深度改写为 FinModPro 原生页面。

建议做法：

- 保留 LightRAG 自带 WebUI
- 在 FinModPro 管理端增加一个统一入口
- 通过反向代理或独立子应用方式承载
- 只做轻量品牌对齐：
  - Logo / 标题
  - 主色与中性色
  - 少量文案与页头
  - 入口导航与跳转行为

不做：

- 深改核心交互流程
- 重写其前端状态管理
- 让其直接嵌入现有 Vue 页面树的核心组件体系

### 7.4 用户路径

管理员第一阶段典型路径：

1. 登录 FinModPro 管理端
2. 进入 `/admin/lightrag`
3. FinModPro 网关或反向代理完成统一入口控制
4. 在 LightRAG WebUI 内进行图谱检索、文档探索、试点问答

### 7.5 为什么第一阶段不启用 Neo4j

原因不是 Neo4j 没价值，而是：

- 当前机器资源余量不足
- 首发目标是验证 LightRAG 在业务上有没有价值
- 先复用 Milvus / 模型 API / 现成 WebUI 能最快完成试点
- 如果第一阶段效果一般，Neo4j 的额外复杂度没有必要承担

## 8. 第二阶段设计（Neo4j 增强）

### 8.1 进入条件

满足以下条件后再进入第二阶段：

- 第一阶段试点证明图增强检索确有业务收益
- LightRAG 被确认不是短期实验，而是中期能力模块
- 资源条件允许：优先独立主机或新增资源，不建议继续硬塞当前生产机

### 8.2 第二阶段变化

第二阶段引入 Neo4j 后：

- LightRAG graph storage 切换为 Neo4j
- 图谱查询与图探索正式走 Neo4j
- 可评估是否同步增强 graph-related 管理能力

### 8.3 第二阶段仍然不做的事

- 不把 Neo4j 直接变成 FinModPro 主业务数据库
- 不把 FinModPro 的所有查询都改写为图查询
- 不要求一次性替换当前主知识库检索链路

## 9. 数据流设计

### 9.1 第一阶段数据流

1. FinModPro 继续完成自身文档 ingest 主链路
2. LightRAG 根据接入策略消费文档与索引输入
3. LightRAG 生成自己的 text chunks / entity / relation / graph state
4. 管理员通过其 WebUI 或 API 访问图增强能力

第一阶段允许与现有知识库链路并行，而不是强制收敛为唯一检索路径。

### 9.2 后续收敛方向

如果第一阶段成功，后续可评估：

- 由 FinModPro 的特定问答场景切到 LightRAG 查询
- 将 LightRAG 作为“增强检索器”而不是替代主检索器
- 在 `chat` 或 `rag` 层增加可配置路由，而非硬切

## 10. 鉴权与安全边界

第一阶段建议：

- LightRAG 不自行成为主认证系统
- FinModPro 负责入口级权限控制
- 外网不直接裸露 LightRAG 原始管理面
- 通过反向代理统一暴露路径、TLS 和访问控制

如果必须先裸露：

- 仅限管理网或白名单范围
- 仅限管理员角色访问

## 11. 部署与资源要求

### 11.1 当前机器约束

基于当前实测：

- LightRAG 单独可试跑
- Neo4j + LightRAG 联机也可试跑
- 但当前生产机资源非常紧张，不适合两者长期稳定常驻

### 11.2 部署建议

第一阶段：

- 可先在当前环境做试点验证
- 但正式常驻部署应先清理磁盘，并保留足够内存余量

第二阶段（Neo4j）：

- 建议单独资源池或新主机
- 不推荐继续与当前主业务服务强行共宿主

## 12. Risks & Mitigations

| 风险 | 说明 | 缓解 |
|---|---|---|
| 资源不足 | 当前机器磁盘和内存余量都偏紧 | 第一阶段先不启用 Neo4j；必要时迁移到独立主机 |
| UI 轻改变深改 | 微调逐渐演变成前端 fork | 明确只允许品牌与入口层改动 |
| 双系统并行带来认知负担 | 用户不知道该用哪个入口 | 第一阶段只开放给管理员试点，限定用途 |
| 模型 API 协议不兼容 | embedding / rerank 不能直接复用 | 增加适配层，先关掉非阻塞组件 |
| 运行边界不清 | 主系统与 LightRAG 职责混淆 | 保持 sidecar 架构，不把逻辑塞回 Django |
| Neo4j 过早接入 | 首发复杂度过高 | 作为第二阶段 gated enhancement |

## 13. Success Criteria

第一阶段成功标准：

- LightRAG 能以独立服务方式接入 FinModPro
- 能复用当前已有 LLM / embedding / Milvus 能力
- 管理端能通过统一入口访问其 WebUI
- WebUI 完成轻量品牌对齐，不深改业务逻辑
- LightRAG 故障不会影响现有知识库主链路

第二阶段成功标准：

- Neo4j 作为 graph backend 成功接入
- 图谱增强能力在实际使用中证明有价值
- 不破坏现有主业务部署稳定性

## 14. 推荐推进顺序

1. 先完成第一阶段 sidecar 接入设计验证
2. 确认模型 API、embedding API、Milvus 配置可直接复用
3. 为管理端增加统一入口与反向代理路径
4. 对 LightRAG WebUI 只做轻量主题与文案微调
5. 小范围管理员试点
6. 评估收益与资源压力后，再决定是否引入 Neo4j

## 15. 最终结论

FinModPro 接入 LightRAG 的最佳路径不是“深度改造并入主系统”，而是：

- **第一阶段：独立 sidecar + 复用现有模型/向量基础设施 + 轻量 UI 对齐**
- **第二阶段：在收益明确后，再引入 Neo4j 作为图后端增强**

这条路径与当前用户偏好、当前资源状态和当前仓库边界最一致，也最容易回滚。
