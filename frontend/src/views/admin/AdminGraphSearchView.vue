<script setup>
import { computed, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
const isSubmitting = ref(false);
const errorMsg = ref('');
const conversation = ref([]);
const inputRef = ref(null);

const params = reactive({
  extraPrompt: '',
  mode: 'global',
  kgTopK: 6,
  chunkTopK: 6,
  entityTokenLimit: 6000,
  relationTokenLimit: 6000,
  totalTokenLimit: 12000,
  enableRerank: true,
  contextOnly: false,
  promptOnly: false,
  streaming: true,
});

const queryForm = reactive({
  query: '',
});

const modeOptions = [
  { value: 'global', label: 'Global' },
  { value: 'local', label: 'Local' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'naive', label: 'Naive' },
];

const handleSubmit = async () => {
  if ((queryForm.query || '').trim().length < 3) {
    flash.warning('查询内容至少需要 3 个字符。');
    return;
  }

  const userQuery = queryForm.query.trim();
  conversation.value.push({ role: 'user', content: userQuery });
  queryForm.query = '';

  isSubmitting.value = true;
  errorMsg.value = '';
  try {
    const result = await lightragApi.query({
      query: userQuery,
      mode: params.mode,
      top_k: params.kgTopK,
      chunk_top_k: params.chunkTopK,
      entity_token_limit: params.entityTokenLimit,
      relation_token_limit: params.relationTokenLimit,
      total_token_limit: params.totalTokenLimit,
      enable_rerank: params.enableRerank,
      context_only: params.contextOnly,
      prompt_only: params.promptOnly,
      response_type: 'Multiple Paragraphs',
      include_references: true,
      include_chunk_content: true,
    });
    conversation.value.push({
      role: 'assistant',
      content: result?.response || '未返回结果。',
      references: result?.references || [],
    });
  } catch (error) {
    errorMsg.value = error.message || '检索失败。';
    conversation.value.push({
      role: 'assistant',
      content: `检索出错：${error.message || '未知错误'}`,
      error: true,
    });
  } finally {
    isSubmitting.value = false;
  }
};

const clearInput = () => {
  queryForm.query = '';
  inputRef.value?.focus();
};

const clearConversation = () => {
  conversation.value = [];
};

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSubmit();
  }
};
</script>

<template>
  <div class="graph-search">
    <div class="graph-search__main">
      <div class="graph-search__messages">
        <div v-if="!conversation.length" class="graph-search__empty">
          <p>输入查询内容，基于知识图谱进行智能检索。</p>
        </div>
        <div v-else class="graph-search__conversation">
          <article
            v-for="(msg, index) in conversation"
            :key="index"
            :class="['graph-search__message', `graph-search__message--${msg.role}`]"
          >
            <div class="graph-search__message-content">
              <p>{{ msg.content }}</p>
              <div v-if="msg.references?.length" class="graph-search__references">
                <span class="graph-search__references-label">引用 ({{ msg.references.length }})</span>
                <div class="graph-search__reference-list">
                  <div
                    v-for="(ref, refIdx) in msg.references"
                    :key="refIdx"
                    class="graph-search__reference"
                  >
                    <strong>{{ ref.title || ref.doc_id || `引用 ${refIdx + 1}` }}</strong>
                    <p>{{ ref.content || ref.chunk_content || '' }}</p>
                  </div>
                </div>
              </div>
            </div>
          </article>
          <div v-if="isSubmitting" class="graph-search__message graph-search__message--assistant">
            <div class="graph-search__message-content">
              <p class="graph-search__typing">检索中...</p>
            </div>
          </div>
        </div>
      </div>

      <div class="graph-search__input-bar">
        <textarea
          ref="inputRef"
          v-model="queryForm.query"
          class="graph-search__input"
          placeholder="输入查询内容"
          rows="1"
          @keydown="handleKeydown"
        />
        <div class="graph-search__input-actions">
          <button
            type="button"
            class="graph-search__btn graph-search__btn--ghost"
            @click="clearInput"
          >
            清空
          </button>
          <button
            type="button"
            class="graph-search__btn graph-search__btn--primary"
            :disabled="isSubmitting || queryForm.query.trim().length < 3"
            @click="handleSubmit"
          >
            发送
          </button>
        </div>
      </div>
    </div>

    <aside class="graph-search__params">
      <div class="graph-search__params-header">
        <strong>参数</strong>
        <button type="button" class="graph-search__btn graph-search__btn--ghost" @click="clearConversation">清空对话</button>
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">附加输出提示词</label>
        <textarea
          v-model="params.extraPrompt"
          class="graph-search__param-textarea"
          placeholder="可选，对输出格式或内容的额外要求"
          rows="3"
        />
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">查询模式</label>
        <div class="graph-search__mode-group">
          <button
            v-for="option in modeOptions"
            :key="option.value"
            type="button"
            :class="['graph-search__mode-chip', { 'graph-search__mode-chip--active': params.mode === option.value }]"
            @click="params.mode = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">KG Top K</label>
        <el-input-number v-model="params.kgTopK" :min="1" :max="50" size="small" />
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">文本块 Top K</label>
        <el-input-number v-model="params.chunkTopK" :min="1" :max="50" size="small" />
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">实体词元数上限</label>
        <el-input-number v-model="params.entityTokenLimit" :min="500" :max="50000" :step="500" size="small" />
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">关系词元数上限</label>
        <el-input-number v-model="params.relationTokenLimit" :min="500" :max="50000" :step="500" size="small" />
      </div>

      <div class="graph-search__param-group">
        <label class="graph-search__param-label">总词元数上限</label>
        <el-input-number v-model="params.totalTokenLimit" :min="1000" :max="100000" :step="1000" size="small" />
      </div>

      <div class="graph-search__param-group graph-search__param-group--row">
        <label class="graph-search__param-label">启用重排</label>
        <el-switch v-model="params.enableRerank" size="small" />
      </div>

      <div class="graph-search__param-group graph-search__param-group--row">
        <label class="graph-search__param-label">仅需上下文</label>
        <el-switch v-model="params.contextOnly" size="small" />
      </div>

      <div class="graph-search__param-group graph-search__param-group--row">
        <label class="graph-search__param-label">仅需提示</label>
        <el-switch v-model="params.promptOnly" size="small" />
      </div>

      <div class="graph-search__param-group graph-search__param-group--row">
        <label class="graph-search__param-label">流式响应</label>
        <el-switch v-model="params.streaming" size="small" />
      </div>
    </aside>
  </div>
</template>

<style scoped>
.graph-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 18px;
  height: calc(100vh - 200px);
  min-height: 500px;
}

.graph-search__main {
  display: grid;
  grid-template-rows: 1fr auto;
  gap: 0;
  min-width: 0;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  overflow: hidden;
  background: var(--surface-2);
}

.graph-search__messages {
  overflow-y: auto;
  padding: 24px;
}

.graph-search__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.graph-search__empty p {
  margin: 0;
  color: var(--text-muted);
}

.graph-search__conversation {
  display: grid;
  gap: 18px;
}

.graph-search__message {
  display: grid;
  gap: 8px;
}

.graph-search__message--user {
  justify-items: end;
}

.graph-search__message--assistant {
  justify-items: start;
}

.graph-search__message-content {
  max-width: 85%;
  padding: 14px 18px;
  border-radius: 18px;
  line-height: 1.7;
}

.graph-search__message--user .graph-search__message-content {
  background: var(--brand);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.graph-search__message--assistant .graph-search__message-content {
  background: var(--surface-3);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.graph-search__message--assistant .graph-search__message-content .graph-search__references {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

.graph-search__references-label {
  display: block;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.graph-search__reference-list {
  display: grid;
  gap: 8px;
}

.graph-search__reference {
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: var(--surface-2);
}

.graph-search__reference strong {
  display: block;
  color: var(--text-primary);
  font-size: 0.8125rem;
  margin-bottom: 4px;
}

.graph-search__reference p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  line-height: 1.55;
}

.graph-search__message-content p {
  margin: 0;
  white-space: pre-wrap;
}

.graph-search__typing {
  color: var(--text-muted);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.graph-search__input-bar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: end;
  padding: 14px 18px;
  border-top: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.graph-search__input {
  resize: none;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  padding: 10px 14px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 0.875rem;
  line-height: 1.5;
  min-height: 40px;
  max-height: 120px;
}

.graph-search__input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(36, 87, 197, 0.15);
}

.graph-search__input::placeholder {
  color: var(--text-muted);
}

.graph-search__input-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.graph-search__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 10px;
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, opacity 0.18s ease;
}

.graph-search__btn--primary {
  background: var(--brand);
  color: #fff;
}

.graph-search__btn--primary:hover {
  background: #1d48a8;
}

.graph-search__btn--primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.graph-search__btn--ghost {
  background: transparent;
  color: var(--text-secondary);
}

.graph-search__btn--ghost:hover {
  background: var(--surface-3);
}

.graph-search__params {
  display: grid;
  gap: 14px;
  align-content: start;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
  overflow-y: auto;
  height: calc(100vh - 200px);
  min-height: 500px;
}

.graph-search__params-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.graph-search__params-header strong {
  color: var(--text-primary);
  font-size: 0.875rem;
}

.graph-search__param-group {
  display: grid;
  gap: 6px;
}

.graph-search__param-group--row {
  grid-template-columns: 1fr auto;
  align-items: center;
}

.graph-search__param-label {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.graph-search__param-textarea {
  resize: vertical;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 8px 12px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 0.8125rem;
  line-height: 1.5;
  min-height: 60px;
}

.graph-search__param-textarea:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(36, 87, 197, 0.15);
}

.graph-search__param-textarea::placeholder {
  color: var(--text-muted);
}

.graph-search__mode-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.graph-search__mode-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-1);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.graph-search__mode-chip:hover,
.graph-search__mode-chip--active {
  border-color: rgba(36, 87, 197, 0.24);
  background: var(--brand-soft);
  color: var(--brand);
}

@media (max-width: 960px) {
  .graph-search {
    grid-template-columns: 1fr;
    height: auto;
  }

  .graph-search__params {
    height: auto;
    min-height: 0;
  }
}
</style>
