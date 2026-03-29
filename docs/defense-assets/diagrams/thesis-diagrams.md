# 系统设计与图示 (Thesis Diagrams)

本文档包含了用于毕业论文和答辩演示的系统核心架构图、业务流程图和页面导航图。
所有图表均使用 Mermaid 语法编写，可以直接在支持 Mermaid 的 Markdown 编辑器（如 Typora, VS Code, GitHub）中预览，或通过 [Mermaid Live Editor](https://mermaid.live/) 导出为 PNG/SVG 格式以插入论文。

## 1. 系统架构图 (System Architecture)

该图展示了 FinModPro 平台的前端、后端、数据库、缓存、向量引擎以及大语言模型服务的整体架构和数据流向。

```mermaid
graph TD
    %% 前端层
    subgraph Frontend [前端表示层 (Vue 3 / Vite)]
        UI[Web UI 界面]
        Router[Vue Router]
        Store[状态管理]
        API_Client[Axios 请求客户端]
        UI --> Router
        UI --> Store
        UI --> API_Client
    end

    %% API 交互
    API_Client -- HTTP/REST API --> Gateway[Nginx / API 网关]
    
    %% 后端服务层
    subgraph Backend [后端服务层 (Django / DRF)]
        Gateway --> Auth[Authentication 认证鉴权]
        Gateway --> CoreAPI[业务 API (知识库, 问答, 风险)]
        
        Auth --> CoreAPI
        
        CoreAPI --> Tasks[异步任务触发]
    end

    %% 异步任务层
    subgraph AsyncTasks [异步任务处理 (Celery)]
        Tasks -- 发布任务 --> RedisBroker[(Redis Broker)]
        RedisBroker -- 消费任务 --> Worker[Celery Worker (文档解析/向量化)]
    end

    %% 数据持久层
    subgraph DataStorage [数据与存储层]
        CoreAPI -- 读写业务数据 --> MySQL[(MySQL 关系型数据库)]
        Worker -- 读写文档元数据 --> MySQL
        Worker -- 保存/读取文件 --> MediaStorage[本地文件系统 / Media 目录]
        CoreAPI -- 读写/下载文件 --> MediaStorage
        Worker -- 写入向量数据 --> Milvus[(Milvus 向量数据库)]
        CoreAPI -- 向量检索 --> Milvus
    end

    %% AI 模型层
    subgraph AI_Layer [AI 模型服务层 (Ollama)]
        Worker -- 调用 Embedding 模型 --> EmbedModel[Embedding 服务]
        CoreAPI -- 调用 Chat 模型 --> ChatModel[LLM 对话服务]
    end
```

## 2. 核心业务流程图 (Core Business Flow)

该图展示了从文档上传入库，到智能问答与风险抽取的完整业务生命周期。

```mermaid
sequenceDiagram
    participant User as 用户 (Analyst/Admin)
    participant UI as 前端页面
    participant API as 后端 API
    participant Celery as Celery Worker
    participant DB as MySQL/Milvus
    participant LLM as Ollama (LLM/Embed)

    %% 登录与上传阶段
    User->>UI: 登录系统
    UI->>API: 提交鉴权请求
    API-->>UI: 返回 JWT Token
    User->>UI: 上传金融报告 (PDF)
    UI->>API: 提交文档信息与文件
    API->>DB: 保存文件至磁盘并记录文档元数据 (Status: Pending)
    API->>Celery: 触发文档入库异步任务
    API-->>UI: 返回上传成功及任务 ID
    
    %% 异步解析阶段
    Celery->>DB: 更新状态为 Parsing
    Celery->>Celery: 读取 PDF 并解析文本
    Celery->>Celery: 文本清洗与滑动窗口切块 (Chunking)
    Celery->>LLM: 请求 Embedding (向量化)
    LLM-->>Celery: 返回向量特征
    Celery->>DB: 将 Chunk 写入 MySQL，向量写入 Milvus
    Celery->>DB: 更新状态为 Parsed
    
    %% 问答与抽取阶段
    User->>UI: 发起风险问题询问
    UI->>API: 提交 Query
    API->>LLM: 预处理 Query 并请求 Embedding
    LLM-->>API: 返回 Query 向量
    API->>DB: 在 Milvus 中进行相似度检索 (Top-K)
    DB-->>API: 返回命中片段及文档引用
    API->>LLM: 组装 Prompt (包含命中上下文) 并请求大模型
    LLM-->>API: 返回生成的回答及引用证据
    API->>DB: 保存问答日志
    API-->>UI: 展示答案与参考卡片
    
    %% 审核阶段
    API->>Celery: (后台) 触发结构化风险抽取任务
    Celery->>LLM: 基于文档块进行信息抽取
    LLM-->>Celery: 返回结构化风险事件 (公司, 类型, 摘要)
    Celery->>DB: 保存风险事件 (待审核)
    User->>UI: 进入风险审核页面
    UI->>API: 获取待审核风险列表
    API-->>UI: 返回数据
    User->>UI: 人工确认通过或驳回
    UI->>API: 更新审核状态
    API->>DB: 持久化审核结果并可生成风险报告
```

## 3. 页面结构与导航图 (Page Navigation / Structure)

该图展示了前端应用的主要页面层级关系与导航路径。

```mermaid
mindmap
  root((FinModPro<br/>金融风控平台))
    登录注册
      (登录页 Login)
    系统主框架
      工作台 / 仪表盘 (Dashboard)
        ::icon(fa fa-bar-chart)
        (全局统计指标)
        (快捷入口)
      知识库管理 (Knowledge Base)
        ::icon(fa fa-book)
        (知识库列表页)
        (知识库详情页)
          (文档列表)
          (上传文档弹窗)
          (解析状态监控)
      智能问答 (RAG Chat)
        ::icon(fa fa-comments)
        (新建会话)
        (历史会话列表)
        (问答交互区)
        (证据来源参考卡片)
      风险审核与报告 (Risk Management)
        ::icon(fa fa-shield)
        (风险事件列表页)
          (按公司/类型筛选)
        (人工审核操作区)
        (风险报告生成与展示页)
      系统与模型设置 (Settings)
        ::icon(fa fa-cog)
        (模型配置页 Model Config)
          (启用/切换 LLM 模型)
          (查看 Prompt 配置)
        (基础评测结果页 Eval Results)
          (正确率与耗时统计)
```

## 导出说明

由于大部分学术论文需要图片格式（如 `.png`, `.jpg` 或 `.eps`, `.svg`），您可以通过以下方式将这些图转换为所需的格式：

1. **推荐：** 复制各个代码块（```mermaid ... ``` 中的内容），粘贴至 [Mermaid Live Editor](https://mermaid.live/)，在界面右上角点击 "Actions" -> "Download PNG" 或 "Download SVG"。
2. **VS Code：** 安装 `Markdown Preview Mermaid Support` 插件，在预览视图中右键保存为图片。
3. **Typora：** Typora 原生支持 Mermaid，可以在预览状态下右键图片选择保存或导出。

然后将导出的图片放入 `docs/defense-assets/screenshots/` 或其他存放答辩素材的目录中即可在论文中引用。
