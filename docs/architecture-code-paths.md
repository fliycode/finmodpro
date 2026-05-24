# FinModPro 系统代码链路文档

> 所有代码路径均基于 `backend/` 下真实源码追踪，更新时间: 2026-05-24

---

## 目录

1. [认证链路 (Authentication)](#1-认证链路)
2. [智能问答链路 (Chat/Q&A)](#2-智能问答链路)
3. [知识库文档摄取链路 (Knowledge Base Ingest)](#3-知识库文档摄取链路)
4. [RAG 检索链路 (Retrieval)](#4-rag-检索链路)
5. [风险抽取链路 (Risk Extraction)](#5-风险抽取链路)
6. [LLM 运维链路 (Model Config / Gateway / Fine-Tune)](#6-llm-运维链路)
7. [系统监控与告警链路 (Monitoring & Alerts)](#7-系统监控与告警链路)
8. [RBAC 用户与权限管理链路](#8-rbac-用户与权限管理链路)
9. [Dashboard 与审计日志链路](#9-dashboard-与审计日志链路)

---

## 1. 认证链路

### 1.1 登录 (Login)

```mermaid
sequenceDiagram
    participant Browser
    participant Nginx
    participant AuthController as auth_controller.py
    participant AuthService as auth_service.py
    participant JwtService as jwt_service.py
    participant RefreshSession as refresh_session_service.py
    participant RBAC as rbac_service.py
    participant DB as MySQL

    Browser->>Nginx: POST /api/auth/login {username, password, remember_me}
    Nginx->>AuthController: login_view(request)
    AuthController->>AuthController: _parse_json_body(request)
    AuthController->>AuthService: authenticate_user(username, password)
    AuthService->>DB: User.objects.filter(username=username)
    AuthService->>DB: authenticate(username, password)  # Django built-in
    alt 认证失败
        AuthService-->>AuthController: None
        AuthController-->>Browser: 401 用户名或密码错误
    else 认证成功
        AuthService->>RBAC: ensure_user_role_bindings(user)
        AuthService-->>AuthController: user
        AuthController->>RefreshSession: create_refresh_session(user_id, remember_me)
        RefreshSession->>DB: INSERT refresh_session
        RefreshSession-->>AuthController: (cookie_value, session)
        AuthController->>JwtService: generate_access_token(user)
        JwtService->>JwtService: HMAC-SHA256 sign {sub, user_id, iat, exp}
        JwtService-->>AuthController: access_token (JWT)
        AuthController->>AuthController: _set_refresh_cookie(response, ...)
        AuthController-->>Browser: 200 {access_token, user, profile}
    end
```

**代码路径:**
- `authentication/controllers/auth_controller.py:145` → `login_view`
- `authentication/services/auth_service.py:45` → `authenticate_user`
- `authentication/services/auth_service.py:22` → `build_user_auth_profile` → `rbac/services/rbac_service.py`
- `authentication/services/jwt_service.py:27` → `generate_access_token` (HMAC-SHA256 自签名 JWT)
- `authentication/services/refresh_session_service.py` → `create_refresh_session`

### 1.2 Token 刷新 (Refresh)

```mermaid
sequenceDiagram
    participant Browser
    participant AuthController as auth_controller.py
    participant RefreshSession as refresh_session_service.py
    participant JwtService as jwt_service.py
    participant AuthService as auth_service.py
    participant DB as MySQL

    Browser->>AuthController: POST /api/auth/refresh (Cookie: refresh_token)
    AuthController->>AuthController: 读取 request.COOKIES[AUTH_REFRESH_COOKIE_NAME]
    alt Cookie 不存在
        AuthController-->>Browser: 401 + clear cookie
    else Cookie 存在
        AuthController->>RefreshSession: rotate_refresh_session(cookie_value)
        RefreshSession->>DB: 查找 + 验证 refresh_session
        RefreshSession->>DB: 更新 session (rotation)
        RefreshSession-->>AuthController: (new_cookie_value, session)
        AuthController->>AuthService: get_user_by_id(session.user_id)
        AuthService->>DB: User.objects.get(id=user_id)
        AuthService-->>AuthController: user
        AuthController->>JwtService: generate_access_token(user)
        JwtService-->>AuthController: new_access_token
        AuthController->>AuthController: _set_refresh_cookie(response, new_cookie)
        AuthController-->>Browser: 200 {access_token, user, profile}
    end
```

### 1.3 DRF 请求认证中间件

```mermaid
sequenceDiagram
    participant Browser
    participant Nginx
    participant JWTAuth as drf_authentication.py
    participant JwtService as jwt_service.py
    participant DB as MySQL

    Browser->>Nginx: GET /api/xxx (Header: Authorization: Bearer <token>)
    Nginx->>JWTAuth: JWTAuthentication.authenticate(request)
    JWTAuth->>JWTAuth: 解析 Authorization header
    JWTAuth->>JwtService: decode_access_token(token)
    JwtService->>JwtService: 验证 HMAC 签名
    JwtService->>JwtService: 检查 exp (过期时间)
    JwtService-->>JWTAuth: {sub, user_id, iat, exp}
    JWTAuth->>DB: User.objects.get(id=user_id)
    JWTAuth-->>Nginx: (user, token) → request.user 已设置
```

**代码路径:**
- `authentication/drf_authentication.py:8` → `JWTAuthentication`
- `authentication/services/jwt_service.py:56` → `decode_access_token`

---

## 2. 智能问答链路

### 2.1 非流式问答 (POST /api/chat/ask)

```mermaid
sequenceDiagram
    participant Browser
    participant AskCtrl as ask_controller.py
    participant AskSvc as ask_service.py
    participant RAGGraph as rag_graph_service.py
    participant Runtime as runtime_service.py
    participant LangGraph as LangGraph StateGraph
    participant LLMProvider as Provider (DeepSeek)
    participant RAGBackend as retrieval_backend_service.py
    participant LlamaIndex as llamaindex_store_service.py
    participant Milvus as Milvus
    participant DB as MySQL

    Browser->>AskCtrl: POST /api/chat/ask {question, filters, top_k, session_id}
    AskCtrl->>AskCtrl: _parse_request_payload(request)  # 校验参数
    AskCtrl->>AskCtrl: @permission_required("auth.ask_financial_qa")
    alt session_id 存在
        AskCtrl->>DB: get_chat_session_for_user(user, session_id)
    end
    AskCtrl->>AskSvc: ask_question(question, filters, top_k, session)
    AskSvc->>Runtime: get_chat_provider()
    Runtime->>DB: get_active_model_config(CAPABILITY_CHAT)
    Runtime->>Runtime: _build_provider(model_config) → DeepSeekProvider()
    Runtime-->>AskSvc: provider
    AskSvc->>RAGGraph: prepare_chat_payload(question, filters, top_k, session, provider)

    Note over RAGGraph: === LangGraph RAG 管道开始 ===
    RAGGraph->>LangGraph: _RAG_GRAPH.invoke(state)

    LangGraph->>LangGraph: Node: route → _route_by_rules()
    Note over LangGraph: 规则匹配: direct_assistant / document_lookup / constrained / context_filters / default

    alt route == "direct"
        LangGraph->>LangGraph: Node: direct_answer_context → _direct_answer_context()
        LangGraph->>LangGraph: build_chat_messages(question, citations=[], filters)
    else route == "retrieve"
        LangGraph->>LangGraph: Node: rewrite_query → _rewrite_query()
        LangGraph->>LLMProvider: provider.chat("改写查询为检索式")
        LLMProvider-->>LangGraph: {rewritten_query, query_variants}

        LangGraph->>LangGraph: Node: retrieve_and_merge → _retrieve_and_merge()
        LangGraph->>RAGBackend: retrieve_chat_context(query, filters, top_k, variants)
        RAGBackend->>LlamaIndex: query_llamaindex_store(query, filters, ...)
        LlamaIndex->>LlamaIndex: 遍历 queries: [vector_search, BM25, MySQL_fulltext, fallback_keyword]
        LlamaIndex->>Milvus: search() / hybrid_search()
        Milvus-->>LlamaIndex: top-k chunks + scores
        LlamaIndex->>LlamaIndex: _merge_ranked_results (RRF fusion)
        LlamaIndex-->>RAGBackend: merged results
        RAGBackend-->>LangGraph: raw_results

        LangGraph->>LangGraph: rerank_with_variants(raw_results, query_variants)
        LangGraph->>LangGraph: _select_relevant_results (score ≥ threshold)

        LangGraph->>LangGraph: Node: score_filter → _score_filter()
        Note over LangGraph: 再次应用分数阈值 (RAG_SCORE_FILTER_THRESHOLD)

        alt 有结果
            LangGraph->>LangGraph: Node: build_retrieval_context → build_retrieval_response()
            LangGraph->>LangGraph: build_chat_messages(session, question, citations, filters)
        else 无结果
            LangGraph->>LangGraph: Node: empty_retrieval_context (fallback)
        end
    end

    LangGraph-->>RAGGraph: {messages, citations, answer_mode, route, ...}
    RAGGraph-->>AskSvc: payload

    AskSvc->>DB: start_session_turn(session, question)  # 记录用户消息
    AskSvc->>LLMProvider: provider.chat(messages=payload.messages)
    LLMProvider-->>AskSvc: answer
    AskSvc->>AskSvc: _filter_citations_used_by_answer(citations, answer)
    AskSvc->>DB: finalize_session_message(content, citations, metadata)
    AskSvc->>DB: create_retrieval_log(payload)  # 记录检索日志
    AskSvc-->>AskCtrl: {question, answer, citations, answer_mode, duration_ms}
    AskCtrl-->>Browser: 200 JSON
```

### 2.2 流式问答 (POST /api/chat/ask/stream)

```mermaid
sequenceDiagram
    participant Browser
    participant AskCtrl as ask_controller.py
    participant AskSvc as ask_service.py
    participant RAGGraph as rag_graph_service.py
    participant LangGraph as LangGraph (stream mode)
    participant LLMProvider as Provider

    Browser->>AskCtrl: POST /api/chat/ask/stream {question, ...}
    AskCtrl->>AskSvc: stream_question(question, filters, top_k, session)
    AskSvc->>RAGGraph: prepare_chat_payload_streaming(question, ...)

    RAGGraph->>LangGraph: _RAG_GRAPH.stream(input_state, stream_mode=["updates", "custom"])

    loop LangGraph 节点执行
        LangGraph-->>RAGGraph: ("custom", {step: "route", route: "retrieve"})
        RAGGraph-->>AskSvc: ("step", data)
        AskSvc-->>Browser: SSE: event:step → {"step":"route", ...}

        LangGraph-->>RAGGraph: ("custom", {step: "rewrite_query", ...})
        RAGGraph-->>AskSvc: ("step", data)
        AskSvc-->>Browser: SSE: event:step → {"step":"rewrite_query", ...}

        LangGraph-->>RAGGraph: ("custom", {step: "retrieve", ...})
        RAGGraph-->>AskSvc: ("step", data)
        AskSvc-->>Browser: SSE: event:step → {"step":"retrieve", ...}

        LangGraph-->>RAGGraph: ("custom", {step: "score_filter", ...})
        RAGGraph-->>AskSvc: ("step", data)
        AskSvc-->>Browser: SSE: event:step → {"step":"score_filter", ...}

        LangGraph-->>RAGGraph: ("custom", {step: "build_context", ...})
        RAGGraph-->>AskSvc: ("step", data)
        AskSvc-->>Browser: SSE: event:step → {"step":"build_context", ...}
    end

    RAGGraph-->>AskSvc: ("payload", {messages, citations, answer_mode, ...})

    AskSvc-->>Browser: SSE: event:meta → {question, citations, answer_mode, ...}
    AskSvc->>LLMProvider: provider.stream(messages)
    loop 流式生成
        LLMProvider-->>AskSvc: chunk
        AskSvc-->>Browser: SSE: event:chunk → {content: "..."}
    end
    AskSvc-->>Browser: SSE: event:done → {answer, citations, ...}
```

**代码路径:**
- `chat/controllers/ask_controller.py:191` → `chat_ask_view`
- `chat/controllers/ask_controller.py:225` → `chat_ask_stream_view`
- `chat/services/ask_service.py:71` → `ask_question`
- `chat/services/ask_service.py:131` → `stream_question`
- `chat/services/rag_graph_service.py:557` → `prepare_chat_payload`
- `chat/services/rag_graph_service.py:599` → `prepare_chat_payload_streaming`
- `chat/services/rag_graph_service.py:520` → `_build_rag_graph` (LangGraph StateGraph 定义)
- `chat/services/context_service.py` → `build_chat_messages`
- `chat/services/session_service.py` → `start_session_turn`, `finalize_session_message`
- `rag/services/retrieval_backend_service.py:14` → `retrieve_chat_context`

**LangGraph 节点顺序:**
```
START → route → (direct → direct_answer_context → END)
              → (retrieve → rewrite_query → retrieve_and_merge → score_filter
                   → build_retrieval_context → END
                   → empty_retrieval_context → END)
```

---

## 3. 知识库文档摄取链路

### 3.1 文档上传 + 摄取 (Upload → Ingest Pipeline)

```mermaid
sequenceDiagram
    participant Browser
    participant DocCtrl as document_controller.py
    participant IngestCtrl as ingest_controller.py
    participant DocSvc as document_service.py
    participant ParserSvc as parser_service.py
    participant CleanEngine as cleaning_engine_service.py
    participant ChunkSvc as chunk_service.py
    participant VectorSvc as vector_service.py
    participant LlamaIndex as llamaindex_store_service.py
    participant Celery as Celery Worker
    participant Milvus
    participant DB as MySQL

    Note over Browser,DB: === 第 1 步: 文件上传 ===
    Browser->>DocCtrl: POST /api/knowledgebase/documents (multipart/form-data: file)
    DocCtrl->>DocCtrl: @permission_required("auth.view_document" / "auth.upload_document")
    DocCtrl->>DocCtrl: 校验: file 必填, 大小 ≤ 50MB
    DocCtrl->>DocSvc: create_document_from_upload(uploaded_file, title, ...)
    DocSvc->>DocSvc: _detect_doc_type(filename)  # txt/pdf/docx
    DocSvc->>DocSvc: _compute_file_hash(uploaded_file)  # SHA-256
    DocSvc->>DB: 检查重复 (file_hash + file_size)
    alt 重复
        DocSvc-->>DocCtrl: DuplicateDocumentError → 409
    end
    DocSvc->>DB: Document.objects.create(title, file, file_hash, ...)
    DocSvc->>DB: DocumentVersion.objects.create(version_number=1, is_current=True)
    DocSvc-->>DocCtrl: document
    DocCtrl->>DB: record_audit_event("knowledgebase.document.upload", succeeded)
    DocCtrl-->>Browser: 201 {document}

    Note over Browser,DB: === 第 2 步: 触发摄取 ===
    Browser->>IngestCtrl: POST /api/knowledgebase/documents/{id}/ingest
    IngestCtrl->>DocSvc: enqueue_document_ingestion(document)
    DocSvc->>DB: SELECT FOR UPDATE document (防并发)
    DocSvc->>DB: 检查是否有进行中的 IngestionTask
    alt 已有进行中任务
        DocSvc-->>IngestCtrl: (existing_task, created=False) → 200 "已有进行中的摄取任务。"
    end
    DocSvc->>DB: IngestionTask.objects.create(status=QUEUED, step=QUEUED)
    DocSvc->>Celery: ingest_document_task.delay(document_id, task_id)
    DocSvc-->>IngestCtrl: (task, created=True)

    Note over Celery,DB: === 第 3 步: Celery 异步执行摄取管道 ===
    Celery->>DocSvc: ingest_document(document, ingestion_task)
    DocSvc->>DocSvc: _mark_ingestion_task_running(STEP_PARSING)

    DocSvc->>ParserSvc: parse_document_file(document)  # Unstructured API
    ParserSvc-->>DocSvc: {parsed_text, elements, document_metadata, chunk_metadata_defaults}
    DocSvc->>DB: document.parsed_text = result; status = PARSED

    DocSvc->>DocSvc: status → CLEANING (清洗阶段)
    DocSvc->>CleanEngine: clean_document(document=document)
    CleanEngine->>CleanEngine: 应用清洗规则 (去噪/格式化/去重)
    CleanEngine-->>DocSvc: CleaningResult(cleaned_text, quality_score)
    DocSvc->>CleanEngine: evaluate_quality_gate(quality_score)
    alt 质量不达标
        DocSvc-->>Celery: DocumentQualityGateError → document.status=FAILED
    end

    DocSvc->>DocSvc: chunk_document(document, parser_result)
    DocSvc->>DocSvc: choose_chunking_strategy() → flat/hierarchical
    alt hierarchical strategy
        DocSvc->>ChunkSvc: build_hierarchical_document_chunks(text, elements)
        DocSvc->>DB: bulk_create DocumentSectionChunk + DocumentChunk (父子结构)
    else flat strategy
        DocSvc->>ChunkSvc: build_document_chunks / build_document_chunks_from_elements
        DocSvc->>DB: bulk_create DocumentChunk (+ search_text)
    end

    DocSvc->>VectorSvc: vectorize_document(document)
    VectorSvc->>VectorSvc: index_document_chunks(document)
    VectorSvc->>VectorSvc: 遍历所有 chunk, 调用 embedding_provider
    VectorSvc->>Milvus: insert(vectors + metadata)  # batch insert
    VectorSvc->>LlamaIndex: sync_document(document)
    LlamaIndex->>LlamaIndex: invalidate_bm25_cache()

    DocSvc->>DB: document.status = INDEXED; task.status = SUCCEEDED
    DocSvc-->>Celery: document
```

**摄取管道阶段顺序:**
```
UPLOADED → QUEUED → PARSING → CLEANING → CHUNKING → INDEXING → GRAPH_SYNC → COMPLETED (INDEXED)
```

**代码路径:**
- `knowledgebase/controllers/document_controller.py:38` → `document_list_create_view`
- `knowledgebase/controllers/ingest_controller.py:37` → `document_ingest_view`
- `knowledgebase/services/document_service.py:493` → `create_document_from_upload`
- `knowledgebase/services/document_service.py:977` → `enqueue_document_ingestion`
- `knowledgebase/services/document_service.py:826` → `ingest_document` (核心管道)
- `knowledgebase/services/document_service.py:667` → `parse_document`
- `knowledgebase/services/document_service.py:677` → `chunk_document`
- `knowledgebase/services/document_service.py:782` → `vectorize_document`
- `knowledgebase/tasks.py:7` → `ingest_document_task` (Celery 入口)

### 3.2 文档删除链路

```mermaid
sequenceDiagram
    participant Browser
    participant DocCtrl as document_controller.py
    participant DocSvc as document_service.py
    participant VectorSvc as vector_service.py
    participant LlamaIndex as llamaindex_store_service.py
    participant DB as MySQL

    Browser->>DocCtrl: DELETE /api/knowledgebase/documents/{id}
    DocCtrl->>DocSvc: get_document_for_user(user, document_id)  # 权限检查
    DocCtrl->>DocSvc: delete_document_with_vectors(document)
    DocSvc->>DB: 收集 chunk_ids
    DocSvc->>DB: document.delete() (CASCADE: chunks, versions, tasks)
    DocSvc->>DocSvc: transaction.on_commit → _cleanup_deleted_document_artifacts()
    Note over DocSvc: 异步清理 (on_commit)
    DocSvc->>VectorSvc: delete_document(document_id)  # Milvus 向量删除
    DocSvc->>LlamaIndex: delete_document(document_id, chunk_ids)  # LlamaIndex 节点删除
    DocSvc->>DB: storage.delete(file_name)  # 文件存储删除
    DocCtrl-->>Browser: 200 {message: "文档已删除。"}
```

---

## 4. RAG 检索链路

### 4.1 多策略并行检索

```mermaid
sequenceDiagram
    participant Caller as rag_graph_service / retrieval_service
    participant RAGBackend as retrieval_backend_service.py
    participant LlamaIndex as llamaindex_store_service.py
    participant EmbedAdapter as llamaindex_embedding_adapter.py
    participant Milvus as Milvus
    participant DB as MySQL
    participant RerankSvc as rerank_service.py
    participant DashScope as DashScope API

    Caller->>RAGBackend: retrieve_chat_context(query, filters, top_k, query_variants)
    RAGBackend->>LlamaIndex: query_llamaindex_store(query, filters, top_k, variants)

    alt RAG_HYBRID_SEARCH_ENABLED
        LlamaIndex->>LlamaIndex: _hybrid_query()
        loop 每个 query_variant
            LlamaIndex->>LlamaIndex: _hybrid_search()
            LlamaIndex->>EmbedAdapter: _get_query_embedding(query)
            EmbedAdapter->>DashScope: text-embedding API
            DashScope-->>EmbedAdapter: embedding_vector
            LlamaIndex->>Milvus: hybrid_search(dense=AnnSearchRequest(COSINE), sparse=AnnSearchRequest(BM25))
            Milvus-->>LlamaIndex: [hybrid results with RRF ranking]
        end
        LlamaIndex->>LlamaIndex: 多 query 结果融合 (取 max score)
    else 传统模式 (多策略并行)
        LlamaIndex->>LlamaIndex: _normalize_queries(query, variants)
        loop 每个 query
            par 向量检索
                LlamaIndex->>Milvus: search() via LlamaIndex VectorStoreIndex
                Milvus-->>LlamaIndex: vector_results
            and BM25 检索
                LlamaIndex->>LlamaIndex: _bm25_search() via LlamaIndex BM25Retriever
                Note over LlamaIndex: BM25 retriever 带 TTL 缓存
                LlamaIndex-->>LlamaIndex: bm25_results
            and MySQL 全文检索
                LlamaIndex->>DB: MATCH(search_text) AGAINST(query IN NATURAL LANGUAGE MODE)
                DB-->>LlamaIndex: mysql_fulltext_results
            and 关键词回退 (无其他结果时)
                LlamaIndex->>DB: 遍历 chunks iterator(chunk_size=500)
                LlamaIndex->>LlamaIndex: _keyword_match_score (token overlap + phrase match)
                LlamaIndex-->>LlamaIndex: fallback_keyword_results
            end
        end
        LlamaIndex->>LlamaIndex: _merge_ranked_results (RRF k=60 fusion)
    end

    LlamaIndex-->>RAGBackend: merged_results (top-k)
    RAGBackend-->>Caller: results

    Note over Caller,RerankSvc: === 重排序 ===
    Caller->>RerankSvc: rerank_with_variants(results, query_variants, fallback_query)
    RerankSvc->>DashScope: rerank API (gte-rerank)
    DashScope-->>RerankSvc: reranked_scores
    RerankSvc-->>Caller: reranked_results
```

**代码路径:**
- `rag/services/retrieval_service.py:44` → `retrieve` (独立 RAG API 入口)
- `rag/services/retrieval_backend_service.py:4` → `retrieve_rag_context`
- `rag/services/retrieval_backend_service.py:14` → `retrieve_chat_context`
- `rag/services/llamaindex_store_service.py:793` → `query_llamaindex_store` (主检索入口)
- `rag/services/llamaindex_store_service.py:435` → `search` (LlamaIndex 向量检索)
- `rag/services/llamaindex_store_service.py:310` → `_bm25_search` (BM25 检索)
- `rag/services/llamaindex_store_service.py:546` → `_mysql_full_text_search` (MySQL 全文检索)
- `rag/services/llamaindex_store_service.py:674` → `_fallback_keyword_search` (关键词回退)
- `rag/services/llamaindex_store_service.py:349` → `_hybrid_search` (Milvus 原生混合检索)
- `rag/services/llamaindex_store_service.py:508` → `_merge_ranked_results` (RRF 融合)
- `rag/services/rerank_service.py` → `rerank_with_variants`, `rerank_results`

---

## 5. 风险抽取链路

### 5.1 文档风险事件抽取

```mermaid
sequenceDiagram
    participant Browser
    participant ExtractCtrl as extract_controller.py
    participant TaskSvc as task_service.py
    participant ExtractSvc as extraction_service.py
    participant ChunkFilter as chunk_filter_service.py
    participant VerifySvc as verification_service.py
    participant Adjudication as adjudication_service.py
    participant Celery
    participant LLM as LLM Provider
    participant DB as MySQL

    Note over Browser,DB: === 提交抽取任务 ===
    Browser->>ExtractCtrl: POST /api/risk/documents/{id}/extract
    ExtractCtrl->>ExtractCtrl: @permission_required("auth.trigger_ingest")
    ExtractCtrl->>TaskSvc: submit_risk_extraction(document)
    TaskSvc->>DB: 检查是否有进行中的 RISK_EXTRACTION 任务
    alt 有进行中
        TaskSvc-->>ExtractCtrl: RiskExtractionBusyError → 429
    end
    TaskSvc->>DB: RiskExtractionTask.objects.create(status=PENDING)
    TaskSvc->>Celery: risk_extraction_task.delay(document.id, task.id)
    TaskSvc-->>ExtractCtrl: (task, created=True)
    ExtractCtrl-->>Browser: 202 {task_id, status: "PENDING"}

    Note over Celery,DB: === Celery 异步执行抽取 ===
    Celery->>ExtractSvc: extract_risk_events_for_document(document)

    ExtractSvc->>DB: list_document_chunks(document)

    ExtractSvc->>ChunkFilter: select_risk_relevant_chunks(document, chunks)
    ChunkFilter->>ChunkFilter: 关键词匹配过滤 (RISK_SIGNAL_KEYWORDS)
    ChunkFilter-->>ExtractSvc: filtered_chunks

    ExtractSvc->>ExtractSvc: limit_extraction_chunks() (max_chunks=8, max_chars=6000)

    ExtractSvc->>VerifySvc: run_extraction_with_verification(document, chunks)
    Note over VerifySvc: 多轮抽取 + 验证管道
    VerifySvc->>LLM: prompt("risk/extract.txt") → 抽取风险事件
    LLM-->>VerifySvc: [RiskEvent {company_name, risk_type, risk_level, summary, evidence, confidence}]
    VerifySvc->>LLM: prompt("risk/verify.txt") → 验证抽取结果
    LLM-->>VerifySvc: verified_events + verification_report
    VerifySvc-->>ExtractSvc: (events, pipeline_meta)
    Note over pipeline_meta: {rounds_completed, verification_passed, total_llm_calls, human_review_count}

    ExtractSvc->>ExtractSvc: _filter_against_existing(document, events)  # 基于 text similarity 去重

    ExtractSvc->>Adjudication: build_event_enrichment(event_data, chunk)
    Adjudication-->>ExtractSvc: enrichment_metadata

    ExtractSvc->>DB: transaction.atomic() → bulk_create RiskEvent[]

    ExtractSvc-->>Celery: created_events
```

### 5.2 风险抽取轮询

```mermaid
sequenceDiagram
    participant Browser
    participant RiskAPI as risk.js (前端)
    participant ExtractCtrl as extract_controller.py
    participant TaskSvc as task_service.py
    participant Celery
    participant DB as MySQL

    Browser->>RiskAPI: extractDocumentWithPolling(documentId)
    RiskAPI->>ExtractCtrl: POST /api/risk/documents/{id}/extract
    ExtractCtrl-->>RiskAPI: 202 {task_id, status: "PENDING"}

    loop 每 3 秒轮询 (最长 5 分钟)
        RiskAPI->>ExtractCtrl: GET /api/risk/documents/extract/status/{task_id}
        ExtractCtrl->>DB: RiskExtractionTask.objects.filter(id=task_id)
        alt 任务完成
            DB-->>ExtractCtrl: status=SUCCEEDED, result_payload={risk_events[]}
            ExtractCtrl-->>RiskAPI: 200 {status: "SUCCESS", result: {...}}
            RiskAPI-->>Browser: result
        else 任务失败
            DB-->>ExtractCtrl: status=FAILED
            ExtractCtrl-->>RiskAPI: 4xx/5xx {message, error_code}
            RiskAPI-->>Browser: error
        else 仍在运行
            ExtractCtrl-->>RiskAPI: 200 {status: "RUNNING", progress: 62}
        end
    end
```

**代码路径:**
- `risk/controllers/extract_controller.py:21` → `RiskDocumentExtractView`
- `risk/controllers/extract_controller.py:185` → `RiskExtractStatusView`
- `risk/services/extraction_service.py:153` → `extract_risk_events_for_document`
- `risk/services/extraction_service.py:89` → `list_document_chunks`
- `risk/services/extraction_service.py:141` → `detect_risk_signals`
- `risk/services/chunk_filter_service.py` → `select_risk_relevant_chunks`
- `risk/services/extraction_service.py:109` → `limit_extraction_chunks`
- `risk/services/verification_service.py` → `run_extraction_with_verification`
- `risk/services/adjudication_service.py` → `build_event_enrichment`
- `risk/services/extraction_service.py:33` → `_filter_against_existing`
- `risk/services/task_service.py` → `submit_risk_extraction`, `serialize_risk_extraction_task`
- `frontend/src/api/risk.js:94` → `extractDocumentWithPolling`

---

## 6. LLM 运维链路

### 6.1 模型配置管理 + Provider 解析

```mermaid
sequenceDiagram
    participant Browser
    participant ModelCtrl as model_config_controller.py
    participant QuerySvc as model_config_query_service.py
    participant CommandSvc as model_config_command_service.py
    participant Runtime as runtime_service.py
    participant ProviderReg as providers/registry.py
    participant Provider as DeepSeekProvider
    participant DB as MySQL
    participant LLM as LLM API

    Note over Browser,LLM: === 列出模型配置 ===
    Browser->>ModelCtrl: GET /api/ops/model-configs
    ModelCtrl->>QuerySvc: list_model_configs() + get_model_config_overview()
    QuerySvc->>DB: ModelConfig.objects.exclude(provider=LITELLM)
    QuerySvc-->>ModelCtrl: [model_configs, overview]
    ModelCtrl-->>Browser: 200 {total, overview, model_configs[]}

    Note over Browser,LLM: === 激活模型 ===
    Browser->>ModelCtrl: PATCH /api/ops/model-configs/{id}/activation {is_active: true}
    ModelCtrl->>CommandSvc: set_model_config_active_state(id, is_active)
    CommandSvc->>DB: UPDATE is_active (同一 capability 只允许一个激活)
    CommandSvc-->>ModelCtrl: model_config

    Note over Browser,LLM: === 测试连接 ===
    Browser->>ModelCtrl: POST /api/ops/model-configs/test-connection {provider, model_name, endpoint, api_key, ...}
    ModelCtrl->>CommandSvc: test_model_config_connection(payload)
    CommandSvc->>ProviderReg: get_provider_class(provider, capability)
    ProviderReg-->>CommandSvc: DeepSeekProvider class
    CommandSvc->>Provider: DeepSeekProvider(endpoint, model_name, options)
    Provider->>LLM: chat([{role:"user", content:"ping"}], max_tokens=1)
    LLM-->>Provider: response
    Provider-->>CommandSvc: result
    CommandSvc-->>ModelCtrl: {connected: true, model: "...", latency_ms: ...}

    Note over Browser,LLM: === Runtime: 业务调用时解析激活模型 ===
    Note over Runtime: 任何需要 LLM 的业务代码调用:
    Runtime->>DB: get_active_model_config(CAPABILITY_CHAT)
    DB-->>Runtime: active ModelConfig
    Runtime->>ProviderReg: get_provider_class(config.provider, config.capability)
    ProviderReg-->>Runtime: Provider class
    Runtime->>Runtime: provider_class(endpoint, model_name, options) → provider instance
    Runtime-->>Caller: provider (可调用 .chat() / .stream() / .embed() / .rerank())
```

**代码路径:**
- `llm/controllers/model_config_controller.py:62` → `ModelConfigListView`
- `llm/controllers/model_config_controller.py:100` → `ModelConfigDetailView`
- `llm/controllers/model_config_controller.py:175` → `ModelConfigActivationView`
- `llm/controllers/model_config_controller.py:216` → `ModelConfigConnectionTestView`
- `llm/services/model_config_service.py:5` → `get_manageable_model_configs`
- `llm/services/model_config_service.py:9` → `get_active_model_config`
- `llm/services/model_config_command_service.py` → `create_model_config`, `update_model_config`, `test_model_config_connection`
- `llm/services/model_config_query_service.py` → `list_model_configs`, `get_model_config_overview`
- `llm/services/runtime_service.py:35` → `get_chat_provider`
- `llm/services/runtime_service.py:46` → `get_embedding_provider`
- `llm/services/runtime_service.py:51` → `get_rerank_provider`
- `llm/services/providers/registry.py` → `get_provider_class`
- `llm/services/providers/deepseek_provider.py` → `DeepSeekProvider`
- `llm/services/providers/dashscope_provider.py` → `DashScopeProvider`

### 6.2 LLM Gateway 分析

```mermaid
sequenceDiagram
    participant Browser
    participant GatewayCtrl as gateway_controller.py
    participant UsageSvc as model_usage_query_service.py
    participant LogSvc as model_invocation_log_service.py
    participant DB as MySQL
    participant Langfuse as Langfuse

    Browser->>GatewayCtrl: GET /api/ops/llm/gateway/summary
    GatewayCtrl->>UsageSvc: 查询使用统计
    UsageSvc->>DB: 聚合查询 model_invocation_log
    UsageSvc-->>GatewayCtrl: {total_calls, total_tokens, total_cost, ...}

    Browser->>GatewayCtrl: GET /api/ops/llm/gateway/logs?page=1&page_size=20
    GatewayCtrl->>LogSvc: 查询调用日志
    LogSvc->>DB: ModelInvocationLog.objects.order_by("-created_at")
    LogSvc-->>GatewayCtrl: [logs with trace_id]

    Browser->>GatewayCtrl: GET /api/ops/llm/gateway/traces/{trace_id}
    GatewayCtrl->>Langfuse: fetch trace detail
    Langfuse-->>GatewayCtrl: trace spans + observations

    Browser->>GatewayCtrl: GET /api/ops/llm/gateway/costs/timeseries?days=30
    GatewayCtrl->>DB: 按日期聚合成本
    GatewayCtrl-->>Browser: [{date, cost, tokens}, ...]
```

**代码路径:**
- `llm/controllers/gateway_controller.py` → `GatewaySummaryView`, `GatewayLogsView`, `GatewayTraceView`
- `llm/services/model_usage_query_service.py` → 使用统计查询
- `llm/services/model_invocation_log_service.py` → 调用日志记录

---

## 7. 系统监控与告警链路

### 7.1 指标采集 + 告警评估

```mermaid
sequenceDiagram
    participant CeleryBeat as Celery Beat
    participant MetricsTask as ops/tasks.py
    participant MetricsCollector as metrics_collector_service.py
    participant AlertEngine as alert_engine_service.py
    participant Milvus
    participant DB as MySQL
    participant Celery

    Note over CeleryBeat,DB: === 定时指标采集 (Celery Beat periodic task) ===
    CeleryBeat->>MetricsTask: collect_system_metrics()
    MetricsTask->>MetricsCollector: collect_all_metrics()
    MetricsCollector->>DB: 查询 document/chunk/vector 数量
    MetricsCollector->>Milvus: 查询 collection 统计
    MetricsCollector->>DB: 查询 Celery 任务统计
    MetricsCollector->>DB: SystemMetric.objects.create(metric_name, value) for each
    MetricsCollector-->>MetricsTask: metrics[]

    Note over CeleryBeat,DB: === 告警规则评估 ===
    CeleryBeat->>AlertEngine: evaluate_alert_rules()
    AlertEngine->>DB: AlertRule.objects.filter(enabled=True)
    AlertEngine->>DB: 获取每个 rule.metric_name 最新的 SystemMetric
    loop 每个 rule
        AlertEngine->>AlertEngine: _compare_value(value, condition, threshold)
        alt 触发告警 (violated)
            AlertEngine->>DB: 检查是否有已存在的 active alert event
            alt 无活跃告警
                AlertEngine->>DB: AlertEvent.objects.create(status=FIRING)
            else 已有活跃告警
                AlertEngine->>DB: 更新 triggered_value
            end
        else 恢复正常
            AlertEngine->>DB: 批量更新 ActiveEvent → status=RESOLVED
        end
    end
    AlertEngine-->>CeleryBeat: {evaluated, triggered, resolved}
```

### 7.2 前端监控查询

```mermaid
sequenceDiagram
    participant Browser
    participant MetricsCtrl as metrics_controller.py
    participant MonitoringSvc as monitoring_query_service.py
    participant DB as MySQL

    Browser->>MetricsCtrl: GET /api/monitoring/monitoring/status
    MetricsCtrl->>MetricsCtrl: @permission_required("auth.view_monitoring")
    MetricsCtrl->>MonitoringSvc: get_current_system_status()
    MonitoringSvc->>DB: 查询各项服务的最新指标
    MonitoringSvc-->>MetricsCtrl: {services: [{name, status, metrics}]}
    MetricsCtrl-->>Browser: 200

    Browser->>MetricsCtrl: GET /api/monitoring/monitoring/metrics?metric_name=cpu&hours=24
    MetricsCtrl->>MetricsCtrl: get_metric_time_series(metric_name, hours)
    MetricsCtrl->>DB: SystemMetric.objects.filter(metric_name, collected_at >= cutoff)
    MetricsCtrl-->>Browser: [{collected_at, value}, ...]
```

**代码路径:**
- `ops/controllers/metrics_controller.py:17` → `SystemStatusView`
- `ops/controllers/metrics_controller.py:29` → `MetricTimeSeriesView`
- `ops/controllers/alert_rule_controller.py` → `AlertRuleListView`, `AlertRuleDetailView`
- `ops/controllers/alert_event_controller.py` → `AlertEventListView`, `AlertEventAcknowledgeView`
- `ops/services/metrics_collector_service.py` → `collect_all_metrics`
- `ops/services/monitoring_query_service.py` → `get_current_system_status`, `get_metric_time_series`
- `ops/services/alert_engine_service.py:13` → `evaluate_alert_rules`
- `ops/tasks.py` → Celery 定时任务

---

## 8. RBAC 用户与权限管理链路

### 8.1 用户管理

```mermaid
sequenceDiagram
    participant Browser
    participant RBACCtrl as rbac/controllers/
    participant RBACSvc as rbac/services/
    participant DB as MySQL

    Browser->>RBACCtrl: GET /api/admin/users
    RBACCtrl->>RBACSvc: admin_user_collection_view → list users
    RBACSvc->>DB: User.objects.all() + annotate groups, permissions
    RBACSvc-->>RBACCtrl: [user profiles]
    RBACCtrl-->>Browser: 200 {users: [...]}

    Browser->>RBACCtrl: PUT /api/admin/users/{id}/groups {group_ids: [...]}
    RBACCtrl->>DB: User.groups.set(group_ids)
    RBACCtrl-->>Browser: 200 {user profile}

    Browser->>RBACCtrl: POST /api/admin/roles/create {name, permissions: [...]}
    RBACCtrl->>DB: Group.objects.create(name) + Permission.objects.filter(codename__in=...)
    RBACCtrl->>DB: 设置 group_permissions
    RBACCtrl-->>Browser: 201 {role}
```

### 8.2 权限检查链路

```mermaid
sequenceDiagram
    participant Request as HTTP Request
    participant AuthzSvc as rbac/services/authz_service.py
    participant JWTAuth as drf_authentication.py
    participant View as View Function
    participant DB as MySQL

    Request->>JWTAuth: authenticate(request)
    JWTAuth->>JWTAuth: decode_access_token → user_id
    JWTAuth->>DB: User.objects.get(id=user_id)
    JWTAuth-->>Request: request.user = user

    Request->>View: @permission_required("auth.ask_financial_qa")
    View->>AuthzSvc: permission_required decorator
    AuthzSvc->>AuthzSvc: user_has_permission(user, "auth.ask_financial_qa")
    alt 无权限
        AuthzSvc-->>View: False
        View-->>Request: 403 Forbidden
    else 有权限
        AuthzSvc-->>View: True
        View->>View: 执行业务逻辑
    end
```

**代码路径:**
- `rbac/controllers/` → user/group/role CRUD 控制器
- `rbac/services/rbac_service.py` → `assign_default_member_group`, `collect_user_groups`, `collect_user_permission_names`
- `rbac/services/authz_service.py` → `permission_required`, `user_has_permission`
- `rbac/management/commands/seed_rbac.py` → 初始化 RBAC 角色 (super_admin, admin, member)

---

## 9. Dashboard 与审计日志链路

### 9.1 Dashboard 总览

```mermaid
sequenceDiagram
    participant Browser
    participant DashboardCtrl as dashboard_controller.py
    participant DashboardSvc as dashboard_service.py
    participant DB as MySQL
    participant Milvus
    participant Redis

    Browser->>DashboardCtrl: GET /api/dashboard/stats
    DashboardCtrl->>DashboardSvc: get_dashboard_stats()
    DashboardSvc->>DB: Document.objects.count() (by status)
    DashboardSvc->>DB: DocumentChunk.objects.exclude(vector_id="").count()
    DashboardSvc->>DB: RiskEvent.objects.count()
    DashboardSvc->>DB: ChatSession.objects.count()
    DashboardSvc->>DB: User.objects.count()
    DashboardSvc->>Milvus: collection stats
    DashboardSvc->>Redis: Celery queue stats
    DashboardSvc-->>DashboardCtrl: {total_documents, indexed_rate, ...}
    DashboardCtrl-->>Browser: 200
```

### 9.2 审计日志

```mermaid
sequenceDiagram
    participant Browser
    participant AuditCtrl as audit_controller.py
    participant AuditSvc as audit_service.py
    participant DB as MySQL

    Browser->>AuditCtrl: GET /api/audits?page=1&page_size=20
    AuditCtrl->>AuditSvc: list_audit_logs(filters)
    AuditSvc->>DB: AuditRecord.objects.filter(...).order_by("-created_at")
    AuditSvc-->>AuditCtrl: {records, total, page, total_pages}
    AuditCtrl-->>Browser: 200

    Note over DB: 审计事件由各业务模块写入:<br/>- 文档上传/删除 (knowledgebase)<br/>- 模型配置变更 (llm)<br/>- 风险抽取 (risk)<br/>- 用户变更 (rbac)
```

**代码路径:**
- `systemcheck/controllers/dashboard_controller.py` → `DashboardStatsView`
- `systemcheck/services/dashboard_service.py` → dashboard 数据聚合
- `systemcheck/controllers/audit_controller.py` → `AuditLogListView`
- `systemcheck/services/audit_service.py` → `record_audit_event`
- `systemcheck/controllers/health_controller.py` → `HealthView`

---

## 前端 API 层总览

所有前端 API 调用通过 `frontend/src/api/config.js` 的 `createApiConfig()` 统一管理:

```mermaid
sequenceDiagram
    participant Component as Vue Component
    participant ApiModule as api/{module}.js
    participant Config as api/config.js
    participant AuthStorage as lib/auth-storage.js
    participant Backend as Django Backend

    Component->>ApiModule: qaApi.askQuestion("问题", filters, 5)
    ApiModule->>Config: apiConfig.fetchJson("/api/chat/ask", {method:"POST", auth:true, body})
    Config->>AuthStorage: authStorage.getToken()
    AuthStorage-->>Config: access_token
    Config->>Config: getAuthHeaders() → {Authorization: "Bearer <token>"}
    Config->>Backend: fetch(url, {headers, body})

    alt 401 + auth refresh
        Backend-->>Config: 401
        Config->>Config: authRefreshHandler() → POST /api/auth/refresh
        alt refresh 成功
            Config->>Backend: 重试原始请求
        else refresh 失败
            Config->>Config: handleUnauthorized() → 清除 token → 跳转 /login
        end
    end

    Backend-->>Config: response
    Config->>Config: parseJson → 检查 response.ok
    Config-->>ApiModule: data
    ApiModule->>ApiModule: normalize 数据
    ApiModule-->>Component: 标准化结果
```

**前端 API 模块文件:**
| 文件 | 用途 |
|------|------|
| `api/config.js` | 核心 HTTP 客户端 (fetch 封装, Auth header, CSRF, 401 拦截/刷新) |
| `api/auth.js` | 登录/注册/登出/密码重置 |
| `api/qa.js` | 智能问答 (非流式 + SSE 流式) |
| `api/knowledgebase.js` | 知识库 (文档 CRUD, 上传, 摄取, 版本管理) |
| `api/chat.js` | 会话管理 (sessions, messages, memories) |
| `api/risk.js` | 风险分析 (抽取 + 轮询, 报表, 事件, 导出) |
| `api/llm.js` | 模型配置管理 |
| `api/llm-gateway.js` | LLM 网关分析 (摘要, 日志, Trace, 成本) |
| `api/llm-console.js` | LLM 控制台总览 |
| `api/admin.js` | 用户/角色/权限管理 |
| `api/dashboard.js` | Dashboard 统计 |
| `api/monitoring.js` | 系统监控 (状态, 指标, 告警) |
| `api/cleaning.js` | 文档清洗规则管理 |
| `api/ops.js` | 运维信息 (存根) |

---

## 附录: 技术栈速览

| 层 | 技术 |
|---|------|
| **前端框架** | Vue 3 + Vite + Vue Router |
| **后端框架** | Django 5 + Django REST Framework |
| **异步任务** | Celery + Redis |
| **数据库** | MySQL 8.4 |
| **向量存储** | Milvus standalone |
| **RAG 框架** | LlamaIndex (LangGraph for chat RAG pipeline) |
| **LLM 网关** | LiteLLM (port 4000) |
| **观测性** | Langfuse |
| **嵌入/重排** | DashScope (阿里云) |
| **LLM 模型** | DeepSeek (via LiteLLM) |
| **部署** | Docker Compose (10 服务) + Nginx 反向代理 |
