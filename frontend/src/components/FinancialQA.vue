<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { kbApi } from '../api/knowledgebase.js';
import { qaApi } from '../api/qa.js';
import {
  getActiveSessionLabel,
  getDefaultSessionFilters,
  normalizeDatasetId,
  normalizeHistoryItems,
} from '../lib/workspace-qa.js';
import ChatHistory from './ChatHistory.vue';

const props = defineProps({
  sessionId: {
    type: [String, Number],
    default: null,
  },
});

const DEFAULT_SYSTEM_MESSAGE = '您好，我是您的金融助手。请输入您的金融问题。';

const route = useRoute();
const router = useRouter();
const currentSessionId = ref(props.sessionId);
const query = ref('');
const messages = ref([{ role: 'system', content: DEFAULT_SYSTEM_MESSAGE, tone: 'info' }]);
const isAsking = ref(false);
const messagesContainer = ref(null);
const sessionOptions = ref([]);
const datasets = ref([]);
const isLoadingSessions = ref(false);
const isLoadingDatasets = ref(false);
const isHydratingSession = ref(false);
const historyDrawerOpen = ref(false);
const activeSessionFilters = ref({});

const hasStreamingAssistant = computed(() =>
  messages.value.some((message) => message.isStreaming),
);

const activeSessionLabel = computed(() =>
  getActiveSessionLabel(sessionOptions.value, currentSessionId.value),
);

const historyItems = computed(() => normalizeHistoryItems(sessionOptions.value));
const activeDatasetId = computed(() =>
  activeSessionFilters.value?.dataset_id ?? normalizeDatasetId(route.query.dataset),
);

const selectedDatasetId = computed({
  get() {
    return activeDatasetId.value === null || activeDatasetId.value === undefined
      ? ''
      : String(activeDatasetId.value);
  },
  async set(value) {
    const normalized = normalizeDatasetId(value);
    activeSessionFilters.value = normalized === null ? {} : { dataset_id: normalized };
    const nextQuery = { ...router.currentRoute.value.query };
    if (normalized === null) {
      delete nextQuery.dataset;
    } else {
      nextQuery.dataset = String(normalized);
    }
    await router.replace({ query: nextQuery });
  },
});

const getAvatarLabel = (role) => {
  if (role === 'user') return '我';
  if (role === 'assistant') return 'AI';
  return '系统';
};

const getAvatarClass = (role) => ({
  avatar: true,
  [`avatar-${role}`]: true,
});

const getFriendlyErrorMessage = (error) => {
  const message = String(error?.message || '').trim();
  if (!message) {
    return '请求失败，请稍后重试。';
  }
  if (/当前未配置可用的对话模型|模型|llm|未启用|未配置/i.test(message)) {
    return '当前未配置可用的对话模型，请联系管理员在模型配置中启用聊天模型后再试。';
  }
  return message;
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth',
    });
  }
};

const resetConversation = () => {
  messages.value = [{ role: 'system', content: DEFAULT_SYSTEM_MESSAGE, tone: 'info' }];
};

const refreshDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    const result = await kbApi.listDatasets();
    datasets.value = Array.isArray(result?.datasets) ? result.datasets : [];
  } catch (error) {
    console.error('加载数据集列表失败:', error);
  } finally {
    isLoadingDatasets.value = false;
  }
};

const refreshSessionOptions = async () => {
  isLoadingSessions.value = true;
  try {
    sessionOptions.value = await chatApi.listHistory({
      datasetId: activeDatasetId.value,
    });
  } catch (error) {
    console.error('加载会话列表失败:', error);
  } finally {
    isLoadingSessions.value = false;
  }
};

const syncSessionRoute = async (sessionId) => {
  if (!sessionId || router.currentRoute.value.query.session === String(sessionId)) {
    return;
  }

  await router.replace({
    query: {
      ...router.currentRoute.value.query,
      session: String(sessionId),
    },
  });
};

const clearSessionRoute = async () => {
  const nextQuery = { ...router.currentRoute.value.query };
  delete nextQuery.session;
  await router.replace({ query: nextQuery });
};

const loadSession = async (id) => {
  if (!id) return;
  isHydratingSession.value = true;
  try {
    const session = await chatApi.getSession(id);
    activeSessionFilters.value = session.contextFilters || {};
    if (Array.isArray(session.messages) && session.messages.length > 0) {
      messages.value = session.messages;
    } else {
      messages.value = [{
        role: 'system',
        content: `已加载会话：${session.title || '未命名会话'}`,
        tone: 'success',
      }];
    }
  } catch (error) {
    console.error('加载会话失败:', error);
    messages.value = [{
      role: 'system',
      content: '加载会话失败，请刷新页面后重试。',
      tone: 'error',
    }];
  } finally {
    isHydratingSession.value = false;
  }
  await refreshSessionOptions();
  await scrollToBottom();
};

const openSession = async (id) => {
  if (!id) {
    return;
  }

  currentSessionId.value = id;
  await syncSessionRoute(id);
  await loadSession(id);
  historyDrawerOpen.value = false;
};

const startNewConversation = async () => {
  currentSessionId.value = null;
  query.value = '';
  activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
  resetConversation();
  historyDrawerOpen.value = false;
  await clearSessionRoute();
  await refreshSessionOptions();
};

watch(() => props.sessionId, async (newId) => {
  currentSessionId.value = newId;
  if (newId && !isHydratingSession.value && !isAsking.value) {
    await loadSession(newId);
    return;
  }
  if (!newId) {
    activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
    resetConversation();
  }
});

watch(
  () => route.query.dataset,
  async () => {
    if (!currentSessionId.value) {
      activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
    }
    await refreshSessionOptions();
  },
);

onMounted(async () => {
  activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
  await Promise.all([refreshSessionOptions(), refreshDatasets()]);
  if (currentSessionId.value) {
    await loadSession(currentSessionId.value);
  }
});

const createAssistantPlaceholder = () => ({
  role: 'assistant',
  content: '',
  citations: [],
  answer_mode: 'cited',
  answer_notice: '',
  duration_ms: 0,
  isStreaming: true,
});

const handleAsk = async () => {
  if (!query.value.trim() || isAsking.value) {
    return;
  }

  const currentQuery = query.value.trim();
  query.value = '';
  messages.value.push({ role: 'user', content: currentQuery });
  isAsking.value = true;
  await scrollToBottom();

  try {
    if (!currentSessionId.value) {
      try {
        const session = await chatApi.createSession({
          title: currentQuery.slice(0, 50),
          contextFilters: activeSessionFilters.value,
        });
        if (session?.id) {
          currentSessionId.value = session.id;
          activeSessionFilters.value = session.contextFilters || activeSessionFilters.value;
          await refreshSessionOptions();
          await syncSessionRoute(session.id);
        }
      } catch (error) {
        console.warn('创建会话失败，继续使用临时会话:', error);
        messages.value.push({
          role: 'system',
          content: '会话创建失败，本次回答不会写入历史记录。',
          tone: 'warning',
        });
      }
    }

    const assistantMessage = createAssistantPlaceholder();
    messages.value.push(assistantMessage);
    await scrollToBottom();

    const finalState = await qaApi.streamQuestion(currentQuery, {
      sessionId: currentSessionId.value,
      filters: activeSessionFilters.value,
      onMeta(meta) {
        assistantMessage.citations = meta.citations;
        assistantMessage.answer_mode = meta.answer_mode;
        assistantMessage.answer_notice = meta.answer_notice;
        assistantMessage.duration_ms = meta.duration_ms;
      },
      onChunk(content, state) {
        assistantMessage.content = state.answer || `${assistantMessage.content}${content}`;
      },
      onDone(doneState) {
        assistantMessage.content = doneState.answer || assistantMessage.content || '未获取到回答，请稍后重试。';
        assistantMessage.citations = doneState.citations;
        assistantMessage.answer_mode = doneState.answer_mode;
        assistantMessage.answer_notice = doneState.answer_notice;
        assistantMessage.duration_ms = doneState.duration_ms;
      },
    });

    assistantMessage.isStreaming = false;
    assistantMessage.content = finalState.answer || assistantMessage.content || '未获取到回答，请稍后重试。';
    await refreshSessionOptions();
  } catch (error) {
    const lastMessage = messages.value[messages.value.length - 1];
    if (lastMessage?.isStreaming) {
      lastMessage.isStreaming = false;
      lastMessage.isError = true;
      lastMessage.content = getFriendlyErrorMessage(error);
      lastMessage.citations = [];
      lastMessage.answer_notice = '';
    } else {
      messages.value.push({
        role: 'assistant',
        content: getFriendlyErrorMessage(error),
        isError: true,
      });
    }
  } finally {
    isAsking.value = false;
    await scrollToBottom();
  }
};
</script>

<template>
  <div class="page-stack qa-page">
    <div class="qa-shell ui-card">
      <div class="qa-shell__toolbar">
        <div class="qa-shell__heading">
          <span class="qa-shell__eyebrow">智能问答</span>
          <div class="qa-shell__title-row">
            <h1 class="qa-shell__title">{{ activeSessionLabel }}</h1>
            <span class="qa-shell__session-state">
              {{ currentSessionId ? '延续会话中' : '新对话' }}
            </span>
          </div>
          <div class="qa-shell__filters">
            <label class="qa-shell__dataset-picker">
              <span>数据集范围</span>
              <select v-model="selectedDatasetId" :disabled="isLoadingDatasets">
                <option value="">全部数据集</option>
                <option
                  v-for="dataset in datasets"
                  :key="dataset.id"
                  :value="String(dataset.id)"
                >
                  {{ dataset.name }}
                </option>
              </select>
            </label>
          </div>
        </div>

        <div class="qa-shell__actions">
          <button class="ghost-btn" type="button" @click="historyDrawerOpen = true">
            历史会话
          </button>
          <button class="ghost-btn ghost-btn--primary" type="button" @click="startNewConversation">
            新对话
          </button>
        </div>
      </div>

      <div class="chat-window">
        <div ref="messagesContainer" class="messages">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role, msg.tone ? `tone-${msg.tone}` : '']"
          >
            <div :class="getAvatarClass(msg.role)">{{ getAvatarLabel(msg.role) }}</div>
            <div class="message-content">
              <div :class="['bubble', { 'bubble-error': msg.isError }]">
                <div class="bubble-text">{{ msg.content }}</div>
                <div v-if="msg.isStreaming" class="stream-caret" />
                <div v-if="msg.duration_ms" class="duration-info">
                  耗时: {{ (msg.duration_ms / 1000).toFixed(2) }}s
                </div>
                <div v-if="msg.answer_notice" class="answer-notice">
                  {{ msg.answer_notice }}
                </div>
              </div>

              <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
                <div class="citations-title">引用依据</div>
                <div class="citations-list">
                  <div v-for="(cite, i) in msg.citations" :key="i" class="citation-card">
                    <div class="citation-card__header">
                      <span class="cite-index">[{{ i + 1 }}]</span>
                      <span class="cite-title">{{ cite.document_title }}</span>
                    </div>
                    <div class="cite-meta">
                      <span>{{ cite.doc_type }}</span>
                      <span v-if="cite.page_label && cite.page_label !== 'N/A'">位置 {{ cite.page_label }}</span>
                      <span v-if="cite.score > 0">相关度 {{ (cite.score * 100).toFixed(0) }}%</span>
                    </div>
                    <div class="cite-snippet">{{ cite.snippet }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="isAsking && !hasStreamingAssistant" class="message assistant">
            <div :class="getAvatarClass('assistant')">AI</div>
            <div class="message-content">
              <div class="bubble typing">
                <span class="dot" />
                <span class="dot" />
                <span class="dot" />
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <textarea
            v-model="query"
            placeholder="输入您的金融分析问题，按 Enter 发送，Shift + Enter 换行"
            @keydown.enter.exact.prevent="handleAsk"
          />
          <button :disabled="isAsking || !query.trim()" class="send-btn" @click="handleAsk">发送</button>
        </div>
      </div>
    </div>

    <el-drawer
      v-model="historyDrawerOpen"
      direction="rtl"
      size="360px"
      :with-header="false"
      class="qa-history-drawer"
    >
      <ChatHistory
        :items="historyItems"
        :is-loading="isLoadingSessions"
        :active-session-id="currentSessionId"
        @refresh="refreshSessionOptions"
        @open-session="openSession"
      />
    </el-drawer>
  </div>
</template>

<style scoped>
.qa-page {
  min-height: calc(100vh - 142px);
}

.qa-shell {
  min-height: calc(100vh - 170px);
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.qa-shell__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  padding: 18px 22px 14px;
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
}

.qa-shell__heading {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qa-shell__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.qa-shell__dataset-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.qa-shell__dataset-picker select {
  min-height: 36px;
  min-width: 220px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text-primary);
}

.qa-shell__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.qa-shell__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.qa-shell__title {
  margin: 0;
  font-size: 24px;
  line-height: 1.1;
  color: var(--text-primary);
}

.qa-shell__session-state {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.qa-shell__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ghost-btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text-primary);
  font-weight: 600;
  cursor: pointer;
}

.ghost-btn--primary {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}

.chat-window {
  flex: 1;
  min-height: calc(100vh - 260px);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(243, 245, 247, 0.95) 100%);
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  padding: 24px 26px 18px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.message {
  display: flex;
  gap: 14px;
  max-width: min(96%, 1120px);
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.system {
  align-self: center;
  max-width: min(100%, 860px);
}

.message.system .message-content {
  align-items: center;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.avatar-user {
  background: #10233d;
  color: #fff;
}

.avatar-assistant {
  background: #dbe6f7;
  color: #10233d;
}

.avatar-system {
  background: #eef2f7;
  color: #5a677d;
}

.bubble {
  position: relative;
  border-radius: 18px;
  padding: 15px 17px;
  background: #fff;
  color: #142033;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
  border: 1px solid rgba(20, 32, 51, 0.08);
  line-height: 1.72;
  white-space: pre-wrap;
}

.message.user .bubble {
  background: #10233d;
  color: #f8fafc;
}

.message.system .bubble {
  background: #fff;
  color: #5a677d;
  border-style: dashed;
}

.bubble-error {
  border-color: rgba(185, 28, 28, 0.16);
  background: #fff5f5;
  color: #991b1b;
}

.bubble-text {
  min-height: 24px;
}

.stream-caret {
  display: inline-block;
  width: 9px;
  height: 18px;
  margin-left: 4px;
  background: #2457c5;
  border-radius: 999px;
  animation: blink 1s steps(1) infinite;
}

.duration-info,
.answer-notice {
  margin-top: 10px;
  font-size: 12px;
}

.duration-info {
  color: #5a677d;
}

.answer-notice {
  color: #8a5a00;
}

.citations-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.citations-title {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5a677d;
}

.citations-list {
  display: grid;
  gap: 10px;
}

.citation-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 12px 14px;
}

.citation-card__header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}

.cite-index {
  color: #2457c5;
  font-weight: 700;
}

.cite-title {
  color: #142033;
  font-weight: 600;
}

.cite-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
  color: #5a677d;
  font-size: 12px;
}

.cite-snippet {
  color: #334155;
  font-size: 13px;
  line-height: 1.6;
}

.input-area {
  padding: 16px 22px 22px;
  border-top: 1px solid rgba(20, 32, 51, 0.08);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 92px;
  gap: 12px;
  background: rgba(255, 255, 255, 0.92);
}

.input-area textarea {
  min-height: 108px;
  resize: vertical;
  border-radius: 18px;
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  padding: 16px 18px;
  font: inherit;
  color: #142033;
}

.send-btn {
  align-self: end;
  height: 46px;
  border: none;
  border-radius: 14px;
  background: #2457c5;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.typing {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #7c8aa5;
  animation: bounce 1.1s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.16s;
}

.dot:nth-child(3) {
  animation-delay: 0.32s;
}

:deep(.qa-history-drawer .el-drawer__body) {
  padding: 18px;
  background: #f7f9fb;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  50.01%, 100% {
    opacity: 0;
  }
}

@media (max-width: 900px) {
  .qa-shell__toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .message {
    max-width: 100%;
  }

  .input-area {
    grid-template-columns: 1fr;
  }

  .send-btn {
    width: 100%;
  }
}
</style>
