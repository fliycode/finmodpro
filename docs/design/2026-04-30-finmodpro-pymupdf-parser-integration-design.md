# FinModPro PyMuPDF PDF 解析接入设计

日期：2026-04-30

更新口径：项目文档按“PyMuPDF 已作为 PDF 主解析与 fallback 引擎接入”后的形态描述；`unstructured-api` 仅作为轻量解析服务名称和兼容 elements 输出边界保留，不再代表官方重版 Unstructured PDF 解析能力。

## 1. Context

FinModPro 当前已经有一条稳定的知识库摄取主链路：文档上传后进入 `parse -> chunk -> vectorize -> retrieve`，其中 `pdf` 主解析通过独立的轻量 `unstructured-api` 服务完成。完整接入后，该轻量服务内部的 PDF 引擎和后端 fallback 均统一为 PyMuPDF。

当前瓶颈并不在 ingest 编排、chunk 或 Milvus，而在 **PDF 文本抽取质量**。轻量服务里的 PDF 路径当前基于 `pdfminer.six` 按行拆成 `Paragraph`；后端 fallback 则使用 `pypdf` 纯文本提取。两者都能工作，但都偏“基础抽文本”，对后续页码、块边界、表格与引用质量的提升空间有限。

PyMuPDF 适合作为 **PDF-only 底层解析增强** 引入，而不是作为整个多格式解析系统的替代物。当前设计的目标不是推翻现有轻量服务边界，而是在不破坏 `txt/docx` 支持和不新增常驻重服务的前提下，升级 PDF 解析质量。

## 2. 当前事实

### 2.1 当前 PDF 主路径

- `backend/knowledgebase/services/parser_service.py` 对 `pdf` 先调用 `parse_via_unstructured(...)`
- 该调用最终进入 `deploy/unstructured-light/app.py`
- 轻量服务对 PDF 当前使用 `pdfminer.high_level.extract_text()`
- 结果被按行拆成 `Paragraph` element 列表

### 2.2 当前 PDF fallback

- `ParserService._parse_pdf()` 当前用 `pypdf.PdfReader(...).extract_text()`
- 当轻量服务不可达或解析失败时，会退回该路径

### 2.3 当前轻量服务边界

轻量 `unstructured-light` 服务当前同时承载：

- `pdf`
- `docx`
- `txt`

并对外暴露统一的 `/general/v0/general` element 输出接口。

### 2.4 当前资源事实

- `finmodpro-unstructured-api` 当前镜像约 **183MB**
- 当前容器实测内存约 **32MB**
- Compose 配置对其设置了 `512m` 限额与 `128m` reservation
- 当前机器磁盘与内存都偏紧，不适合再额外新增一个 PDF 专用常驻服务

### 2.5 PyMuPDF 资源事实

本次实测结果：

- PyMuPDF wheel 约 **24MB**
- 临时安装目录约 **62MB**
- 单纯 `import fitz` 的 RSS 约 **47.8MB**

这说明 PyMuPDF 本身是一个**可接受的依赖级增强**，但不值得为它单独新起服务。

## 3. Goals / Non-goals

### 3.1 Goals

- 提升 FinModPro 当前 PDF 解析质量
- 保持现有 `unstructured-light` 服务边界不变
- 保持 `txt/docx` 路径不受影响
- 保持当前后端 `parse -> elements -> result` 契约不变
- 让主路径与 fallback 的 PDF 能力尽量收敛
- 在当前机器资源约束下可落地、可回滚

### 3.2 Non-goals

- 不重写整个知识库 ingest 主链路
- 不删除 `unstructured-light` 服务
- 不把 PyMuPDF 当作 `docx/txt` 解析器
- 不在第一阶段引入 OCR / Tesseract
- 不在第一阶段新增独立 PyMuPDF 微服务
- 不修改现有 Milvus / retrieval / frontend 消费契约

## 4. 设计原则

- **只换 PDF 引擎，不换外部契约**
- **主路径先升级，fallback 再统一**
- **多格式边界保持稳定**
- **轻依赖优先于新服务**
- **元数据先做增量增强，不一次性做复杂版面系统**
- **回滚必须简单**

## 5. Alternatives Considered

### 方案 A：只替换后端 fallback 为 PyMuPDF

做法：

- 保留 `unstructured-light` 内部 `pdfminer`
- 仅把 `ParserService._parse_pdf()` 从 `pypdf` 改为 PyMuPDF

优点：

- 改动最小
- 回滚最简单
- 可低风险验证 PyMuPDF

缺点：

- 主路径仍旧没有升级
- 只有轻量服务失败时才享受收益
- 不是主能力提升

### 方案 B：替换轻量服务里的 PDF 主路径，并同步替换 fallback（推荐）

做法：

- `deploy/unstructured-light/app.py` 的 `_extract_pdf()` 改为 PyMuPDF 实现
- `backend/knowledgebase/services/parser_service.py` 的 `_parse_pdf()` 也改为 PyMuPDF

优点：

- 主路径与 fallback 都升级
- 保持现有 API 形状与服务边界稳定
- 收益最大，改动仍可控

缺点：

- 需要自己定义 PyMuPDF 输出到当前 element schema 的映射
- 相比只改 fallback，多一个服务端实现面

### 方案 C：彻底移除 `unstructured-light`，让 Django / Celery 直接调用 PyMuPDF

做法：

- 移除内部 HTTP 解析服务
- 让 backend / celery 直接安装并调用 PyMuPDF

优点：

- 少一层内部 HTTP
- 运行路径更直接

缺点：

- 打破当前分层边界
- 主容器镜像变重
- `docx/txt/pdf` 多格式解析边界被打散
- 回滚更难

### 推荐结论

**采用方案 B。**  
即：**保留 `unstructured-light` 服务，只把其 PDF 引擎换成 PyMuPDF，并把后端 fallback 也统一升级到 PyMuPDF。**

## 6. Proposed Design

## 6.1 总体结构

替换后的结构不改变大框架：

1. 用户上传文档
2. Django / Celery 进入 `parse_document()`
3. `pdf` 继续优先调用 `unstructured-light`
4. `unstructured-light` 内部对 PDF 改用 PyMuPDF
5. 解析结果仍返回统一 `elements`
6. 后端按现有 `_elements_to_result()` 逻辑收敛为 `parsed_text + metadata`
7. 若轻量服务失败，则 fallback 到后端本地 PyMuPDF 文本抽取
8. 下游 chunk / vectorize / retrieve 逻辑保持不变

## 6.2 模块边界

### Django / Celery

负责：

- 上传、任务编排、切块、向量化、检索主链路
- 轻量服务失败时的 fallback
- 解析结果收敛与 provenance 记录

不负责：

- 在主请求链路里承担复杂 PDF 版面系统
- 替代轻量多格式解析服务

### unstructured-light

负责：

- 继续对外提供统一 `/general/v0/general` 接口
- 继续处理 `pdf/docx/txt`
- 其中 `pdf` 由 PyMuPDF 驱动

不负责：

- 自己决定 chunking、向量化与检索
- 暴露全新、与现有不兼容的返回契约

## 6.3 代码级替换点

### 必改文件

1. `deploy/unstructured-light/app.py`
   - 重写 `_extract_pdf()`
   - 从 `pdfminer.six` 改为 PyMuPDF 逐页/逐块抽取

2. `deploy/unstructured-light/requirements.txt`
   - 新增 `PyMuPDF`
   - 视最终是否保留 `pdfminer.six` 决定是否移除它

3. `backend/knowledgebase/services/parser_service.py`
   - 重写 `_parse_pdf()`
   - 从 `pypdf` 改为 PyMuPDF fallback

### 可选增强文件

4. `backend/knowledgebase/services/chunk_service.py`
   - 如果第一阶段返回更稳定的 `page_number` / `element_types`，可小幅增强 metadata 透传

### 不应大改文件

- `backend/knowledgebase/services/document_service.py`
- `backend/knowledgebase/services/vector_service.py`
- `backend/rag/services/*`
- 前端知识库与问答页面

## 7. 解析结果契约设计

### 7.1 现有契约必须保留

轻量服务当前输出：

```python
[
  {"type": "...", "text": "...", "metadata": {...}}
]
```

第一阶段必须保留这一形状，避免牵连下游。

### 7.2 PyMuPDF 到 element 的映射策略

第一阶段不做复杂语义识别，只做最小可用映射：

- 一页可拆成 1-N 个 element
- 默认 `type = "Paragraph"`
- `text` 为抽取文本
- `metadata` 至少带：
  - `page_number`

如果后续识别出标题块、表格块，再渐进补充：

- `Title`
- `Table`

但首版不要求强识别。

### 7.3 为什么首版不强做复杂语义映射

因为首版目标是：

- 用最小风险替换 PDF 引擎
- 不因为 element 分类规则不成熟，反而把行为做坏

因此第一阶段以：

- 提升文本质量
- 稳定返回页码

为主。

## 8. 失败与回退设计

### 8.1 主路径失败

如果 `unstructured-light` 内部的 PyMuPDF PDF 路径失败：

- 轻量服务仍按现有语义返回错误
- 后端 `ParserService.parse()` 进入 fallback

### 8.2 fallback 失败

如果后端本地 PyMuPDF fallback 也失败：

- 维持当前 `Document.STATUS_FAILED`
- 维持当前 `IngestionTask.STATUS_FAILED`

### 8.3 为什么主路径和 fallback 都改成 PyMuPDF

如果只改主路径不改 fallback，会出现：

- 主路径与 fallback 行为差异大
- 调试困难
- 相同 PDF 在不同错误路径下结果不一致

因此推荐把两者统一到同一套 PDF 引擎上。

## 9. 资源与部署设计

### 9.1 为什么不新增服务

当前机器资源紧张，不适合再起新服务。  
PyMuPDF 本身的体积与导入内存实测都可接受，因此更合理的方式是：

- **把它接到现有 `unstructured-light` 服务里**

而不是：

- 再起一个 `pymupdf-api`

### 9.2 镜像变化预期

预期变化：

- 当前 `unstructured-light` 镜像会变大一些
- 但仍应保持在“轻量解析服务”区间
- 不会接近官方重版 `unstructured` 的量级

### 9.3 当前机器适配判断

结合已知事实：

- 当前轻量服务常驻内存很低
- PyMuPDF 本身不重
- 因此作为依赖接入可接受
- 但不适合同时再新增一套专用解析服务

## 10. Risks & Mitigations

| 风险 | 说明 | 缓解 |
|---|---|---|
| element 映射不稳 | PyMuPDF 原生结果和当前 element schema 不同 | 第一阶段只做最小映射，保持统一契约 |
| 主路径 / fallback 行为不一致 | 两条路径用不同 PDF 引擎会让结果发散 | 主路径与 fallback 都统一到 PyMuPDF |
| 镜像变大 | 当前机器磁盘偏紧 | 不新增服务；保留轻量镜像目标；完成后再测镜像体积 |
| 误把 PyMuPDF 当成通用文档解析器 | 它只适合 PDF 增强 | 明确只替换 PDF，不动 `docx/txt` |
| OCR 需求被提前拉进来 | OCR 会引入 Tesseract 与复杂依赖 | 第一阶段明确不做 OCR |

## 11. Success Criteria

- PDF 主路径已由 PyMuPDF 驱动
- PDF fallback 已由 PyMuPDF 驱动
- `docx/txt` 路径行为不变
- 轻量服务对外 API 形状不变
- 知识库主链路无需大规模改动即可继续工作
- 镜像和常驻内存仍维持在可接受范围
- 解析失败与回滚路径语义保持清晰

## 12. 推荐实施顺序

1. 在 `unstructured-light` 中接入 PyMuPDF 并实现 `_extract_pdf()`
2. 保留现有 element 契约，只做最小 PDF element 映射
3. 将 backend fallback 从 `pypdf` 改为 PyMuPDF
4. 重新测：
   - 镜像大小
   - 空载内存
   - PDF 解析效果
5. 通过后再决定是否补更丰富的 `page_number` / block metadata

## 13. 最终结论

FinModPro 接入 PyMuPDF 的正确方式不是：

- 删除 `unstructured-light`
- 再起一个新的 PyMuPDF 服务
- 或把 PyMuPDF 整个源码 vendoring 到仓库

而是：

> **保留当前轻量多格式解析服务边界，只把其中的 PDF 引擎与后端 PDF fallback 统一升级到 PyMuPDF。**

这是对现有架构侵入最小、收益最稳定、最符合当前机器条件的接入方式。
