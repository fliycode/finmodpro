# FinModPro Unstructured 知识库解析接入设计

日期：2026-04-15

## 1. 目标

为 FinModPro 的知识库摄取链路补齐文档解析能力，重点解决当前两类真实问题：

- `docx` 已允许上传，但解析尚未实现，导致无法正常入库
- `pdf` 当前只做基础抽文本，缺少更好的页面和结构化元数据

第一阶段目标不是重写整条 ingest / RAG 流程，而是把 `Unstructured` 作为独立解析层接入，提升 `pdf/docx` 的入库质量，同时保持当前 `chunk/embed/index` 主链路不变。

## 2. 当前事实

当前仓库的知识库链路边界已经足够清楚：

- `knowledgebase.services.document_service.parse_document()` 通过 `parse_document_file(document)` 进入解析阶段
- `knowledgebase.services.chunk_service.build_chunks()` 仍然是当前 chunk 主逻辑
- `knowledgebase.models.Document.parsed_text` 承载全文
- `knowledgebase.models.DocumentChunk.metadata` 已承载 `page_label` 等 chunk 级元数据
- `rag.services.vector_store_service` 与 `rag.services.retrieval_service` 已经会把 chunk metadata 带到 citation 结果里

这意味着第一阶段最合理的做法是替换解析层，而不是更换检索框架或重做 chunk 逻辑。

## 3. 范围

### 3.1 In Scope

- 为 `pdf` 和 `docx` 引入 `Unstructured` 解析能力
- 保留 `txt` 的本地解析路径
- 将解析结果收敛为 `parsed_text + 文档级 provenance + chunk 级 metadata`
- 为 `pdf` 提供 `Unstructured -> pypdf` 的回退路径
- 记录 parser、strategy、fallback 等解析来源信息
- 为解析适配层、ingest 流程和 API 兼容性补测试

### 3.2 Out of Scope

- OCR 流程设计
- 表格专用抽取链路
- 将 element 原样持久化到数据库
- 新增 `DocumentElement` 一类的新表
- 按 element 级别重新定义 chunk 算法
- 替换现有 embedding、Milvus、retrieval、citation 主链路
- 引入 `LlamaIndex`

## 4. 设计原则

- 只替换解析层，不推翻 ingest 主链路
- 不把文档解析重依赖塞进 Django / Celery 容器
- 保持现有 API 形状和前端消费方式稳定
- 失败语义必须清晰：哪些类型能回退，哪些类型直接失败
- 先把 `docx 可入库` 和 `pdf 元数据增强` 做对，再考虑更重的版面/元素建模

## 5. 架构设计

### 5.1 组件职责

#### Django / FinModPro

职责：

- 负责上传、摄取编排、切块、向量化和检索
- 维护当前文档、版本和任务状态
- 调用解析适配层并处理结果

不负责：

- 在进程内承担复杂文档解析依赖
- 自己实现 `docx`/高级 `pdf` 结构解析

#### Unstructured 解析服务

职责：

- 接收 `pdf/docx` 文件
- 返回清洗后的文本和基础结构化元数据
- 对不同文档类型应用解析策略

不负责：

- 决定 FinModPro 如何切块和索引
- 管理知识库业务状态

### 5.2 为什么第一版采用独立解析服务

不将 Unstructured 重依赖直接安装进 `backend` / `celery-worker` 容器，原因是：

- 会显著增加主应用镜像体积和运行时复杂度
- 解析依赖与 Django 在线服务职责不同
- 后续若替换解析后端，独立服务更容易回滚
- 当前 `docker-compose.prod.yml` 已是多服务形态，扩展一个内部解析服务符合现状

因此第一阶段应采用：

- `txt`：本地解析
- `pdf/docx`：通过内部 HTTP 调用独立 Unstructured 解析服务

## 6. 运行时数据流

第一阶段目标数据流：

1. 用户上传 `txt/pdf/docx`
2. `document_service.create_document_from_upload()` 创建文档记录
3. `ingest_document()` 进入解析阶段
4. `parse_document(document)` 调用 parser adapter
5. parser adapter：
   - `txt` 走本地读取与清洗
   - `pdf/docx` 走 Unstructured 解析服务
   - `pdf` 在 Unstructured 不可达或解析失败时可退回 `pypdf`
6. 解析层返回：
   - `parsed_text`
   - `document_metadata`
   - `chunk_metadata_defaults`
7. Django 将 `parsed_text` 写入 `Document.parsed_text`
8. Django 将 parser 来源信息写入当前版本的 provenance 字段
9. `chunk_document()` 继续执行现有切块，但把增强后的 metadata 带入 `DocumentChunk.metadata`
10. 向量化、检索、citation 继续沿用现有主链路

## 7. 解析结果数据契约

### 7.1 第一版返回形状

第一版建议让 parser adapter 返回一个结构化结果，而不是只返回纯字符串：

```python
{
    "parsed_text": "...",
    "document_metadata": {
        "source_parser": "txt" | "unstructured" | "pypdf",
        "source_strategy": "auto" | "hi_res" | "fast" | "local",
        "fallback_used": False,
        "element_count": 0,
    },
    "chunk_metadata_defaults": {
        "page_number": None,
        "section_title": "",
        "element_types": [],
        "source_parser": "unstructured",
        "source_strategy": "auto",
    },
}
```

第一阶段不要求完整 element 列表下沉到数据库，只要求文档级与 chunk 级能拿到可消费的摘要元数据。

### 7.2 数据库存储策略

第一阶段不新增表，不改主模型结构。

沿用现有承载面：

- `Document.parsed_text`
  - 保存最终全文文本
- `DocumentVersion.source_metadata`
  - 保存 `source_parser`、`source_strategy`、`fallback_used`、`element_count`
- `DocumentVersion.processing_notes`
  - 保存必要的人类可读说明，例如 “pdf parse fallback to pypdf”
- `DocumentChunk.metadata`
  - 保存增强后的 chunk 元数据

### 7.3 Chunk 级 metadata 策略

当前 `_build_chunk_metadata()` 已生成：

- `document_id`
- `document_title`
- `doc_type`
- `source_date`
- `dataset_id`
- `dataset_name`
- `root_document_id`
- `version_number`
- `chunk_index`
- `page_label`

第一阶段在此基础上补充可选字段：

- `page_number`
- `section_title`
- `element_types`
- `source_parser`
- `source_strategy`

如果第一版无法稳定为每个 chunk 精确映射 element 边界，则允许：

- `page_number` 为空
- `section_title` 为空
- `element_types` 为空数组

但 `source_parser` 与 `source_strategy` 必须写入，保证后续排障和评估可观测。

## 8. 回退与错误处理

### 8.1 文档类型策略

- `txt`
  - 永远走本地解析
  - 不依赖 Unstructured
- `docx`
  - 默认走 Unstructured
  - 第一阶段无本地 fallback，Unstructured 失败则直接报解析失败
- `pdf`
  - 默认走 Unstructured
  - 若 Unstructured 不可达、超时或解析失败，可退回现有 `pypdf` 文本抽取

### 8.2 为什么 docx 不做本地 fallback

当前仓库并不存在可用的本地 `docx` 解析实现。

如果为了第一阶段临时再引一套本地 `docx` 库，会同时带来：

- 额外依赖
- 双实现维护成本
- 与“独立解析服务”边界冲突

因此 `docx` 的第一阶段语义应保持简单：依赖 Unstructured，失败即失败。

### 8.3 失败语义

- Unstructured 服务不可达、超时、5xx：
  - `pdf` 允许 fallback
  - `docx` 直接失败
- Unstructured 返回空文本：
  - 视为解析失败
- `pypdf` fallback 也失败：
  - 文档摄取失败
- 失败时继续沿用现有 `Document.STATUS_FAILED`、`IngestionTask.STATUS_FAILED` 语义

### 8.4 Provenance 要求

只要出现以下任一情况，必须写入 provenance：

- 使用 `unstructured`
- 使用 `pypdf` fallback
- 解析策略不是默认值
- 出现部分降级

这样后续在文档详情、检索结果和问题排查时，能明确知道当前文本来自哪条解析路径。

## 9. 配置与部署设计

### 9.1 新增配置

第一阶段建议新增以下配置：

- `UNSTRUCTURED_API_URL`
- `UNSTRUCTURED_API_KEY`
- `UNSTRUCTURED_TIMEOUT_SECONDS`
- `UNSTRUCTURED_PDF_STRATEGY`
- `UNSTRUCTURED_DOCX_STRATEGY`
- `UNSTRUCTURED_PDF_FALLBACK_ENABLED`

### 9.2 docker-compose 扩展

在现有 `docker-compose.prod.yml` 上新增独立解析服务，例如：

- `unstructured-api`

FinModPro backend 与 celery worker 通过内部服务地址访问，不暴露新的公共业务接口。

### 9.3 第一阶段策略选择

第一阶段建议：

- `pdf` 使用自动或通用策略，不引入 OCR 复杂度
- `docx` 先保证成功率和文本质量，不追求完整版面还原
- 不在本阶段启用复杂表格/图像提取配置

## 10. 代码改动边界

第一阶段预计改动集中在以下区域：

- `backend/knowledgebase/services/parser_service.py`
  - 改为 parser adapter
- `backend/knowledgebase/services/document_service.py`
  - `parse_document()` 从纯文本返回切换为结构化解析结果
  - 将 provenance 写入当前版本记录
  - 将 parser metadata 合并到 chunk metadata
- `backend/knowledgebase/tests.py`
  - 增加 parser、ingest、fallback 回归测试
- `backend/.env.example`
  - 增加 Unstructured 配置示例
- `docker-compose.prod.yml`
  - 新增解析服务
- 可选新增：
  - `backend/knowledgebase/services/unstructured_client.py`

第一阶段不应修改：

- `rag/services/retrieval_service.py`
- `rag/services/vector_store_service.py`
- `knowledgebase/services/chunk_service.py` 的基础算法

## 11. 测试与验证方案

### 11.1 Parser 单测

需要覆盖：

- `txt` 仍沿用本地清洗
- `docx` 成功路径
- `pdf` 成功路径
- `pdf` 的 Unstructured 失败后 fallback 到 `pypdf`
- Unstructured 返回空文本
- Unstructured timeout / 5xx

### 11.2 Ingest 集成测试

需要覆盖：

- `parse_document()` 能写入 `parsed_text`
- parser 来源信息被写入版本 provenance
- `chunk_document()` 生成增强后的 chunk metadata
- `docx` 失败时文档和 ingestion task 状态正确

### 11.3 API 兼容性回归

需要确认：

- 上传接口形状不变
- 文档详情仍返回 `parsed_text`
- 文档 chunk 列表仍兼容现有前端消费
- 检索 citation 结构不变，只是 metadata 更丰富

### 11.4 部署级冒烟

至少验证：

- `docker compose -f docker-compose.prod.yml config`
- `txt` 上传并入库
- `docx` 上传并入库
- `pdf` 上传并入库
- 人为断开 Unstructured 后：
  - `pdf` 能按设计 fallback 或失败
  - `docx` 直接 fail-fast

## 12. 风险与后续阶段

### 12.1 当前阶段风险

- Unstructured 返回的结构化粒度与期望可能不完全一致
- 第一阶段仍采用字符切块，无法完整保留 element 边界
- `pdf` fallback 后的 citation 质量仍会弱于结构化解析成功路径

### 12.2 后续阶段再考虑的事项

- OCR
- 表格专用解析
- element 级持久化
- 基于 section / page 的 chunking
- 解析质量评测面板

## 13. 最终建议

第一阶段应按以下方式推进：

- `txt` 保持本地解析
- `pdf/docx` 接入独立 Unstructured 解析服务
- `pdf` 保留 `pypdf` fallback
- 不改数据库主结构
- 不动现有 chunk / embedding / retrieval 主链路

这样可以用最小范围补齐 `docx` 入库能力，并显著改善 `pdf` 的解析质量和 citation 元数据基础，同时保持系统可回退、可验证、可分阶段演进。
