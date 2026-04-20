<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { kbApi } from '../api/knowledgebase.js';
import { qaApi } from '../api/qa.js';
import {
  getDefaultSessionFilters,
  getSessionLoadFailureNotice,
  getQaChromeState,
  normalizeDatasetId,
  normalizeHistoryItems,
  shouldShowFinancialQaEmptyState,
} from '../lib/workspace-qa.js';
import ChatHistory from './ChatHistory.vue';
import ChatMemoryDrawer from './ChatMemoryDrawer.vue';

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
const activeSessionLoadFailed = ref(false);
const historyDrawerOpen = ref(false);
const memoryDrawerOpen = ref(false);
const activeSessionFilters = ref({});
const qaChromeState = getQaChromeState();

const hasStreamingAssistant = computed(() =>
  messages.value.some((message) => message.isStreaming),
);
const historyItems = computed(() => normalizeHistoryItems(sessionOptions.value));
const activeDatasetId = computed(() =>
  activeSessionFilters.value?.dataset_id ?? normalizeDatasetId(route.query.dataset),
);
const showEmptyState = computed(() => shouldShowFinancialQaEmptyState({
  currentSessionId: currentSessionId.value,
  messages: messages.value,
}));
const sessionLoadFailureNotice = computed(() =>
  getSessionLoadFailureNotice(activeSessionLoadFailed.value),
);
const visibleMessages = computed(() =>
  messages.value.filter((message, index) => !(
    showEmptyState.value
    && index === 0
    && message?.role === 'system'
    && message?.content === DEFAULT_SYSTEM_MESSAGE
  )),
);

const qaActionLabels = {
  history: '历史会话',
  memory: '记忆',
  new: '新对话',
};

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
  activeSessionLoadFailed.value = false;
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
    activeSessionLoadFailed.value = true;
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
  activeSessionLoadFailed.value = false;
  query.value = '';
  activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
  resetConversation();
  historyDrawerOpen.value = false;
  await clearSessionRoute();
  await refreshSessionOptions();
};

const handleQaAction = async (action) => {
  if (action === 'history') {
    historyDrawerOpen.value = true;
    return;
  }

  if (action === 'memory') {
    memoryDrawerOpen.value = true;
    return;
  }

  if (action === 'new') {
    await startNewConversation();
    return;
  }
};

watch(() => props.sessionId, async (newId) => {
  currentSessionId.value = newId;
  if (newId && !isHydratingSession.value && !isAsking.value) {
    await loadSession(newId);
    return;
  }
  if (!newId) {
    activeSessionLoadFailed.value = false;
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
          activeSessionLoadFailed.value = false;
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
  <div class="qa-page">
    <div class="qa-shell ui-card">
      <div class="qa-shell__toolbar">
        <div class="qa-shell__actions">
          <button
            v-for="action in qaChromeState.actions"
            :key="action"
            :class="['ghost-btn', { 'ghost-btn--primary': action === 'new' }]"
            type="button"
            @click="handleQaAction(action)"
          >
            {{ qaActionLabels[action] ?? action }}
          </button>
        </div>

        <label class="qa-shell__dataset-picker qa-shell__dataset-picker--subtle">
          <span>数据集</span>
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

      <div class="chat-window">
        <div v-if="sessionLoadFailureNotice" class="qa-inline-notice" role="status">
          {{ sessionLoadFailureNotice }}
        </div>
        <div v-if="showEmptyState" class="qa-empty-state">
          <h2>开始新一轮分析</h2>
          <p>从历史会话继续、查看记忆，或直接输入新的金融问题。</p>
        </div>

        <div
          ref="messagesContainer"
          class="messages"
          :class="{ 'messages--empty': showEmptyState }"
        >
          <div
            v-for="(msg, index) in visibleMessages"
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
        :show-session-metadata="true"
        @refresh="refreshSessionOptions"
        @open-session="openSession"
      />
    </el-drawer>

    <ChatMemoryDrawer
      v-model:open="memoryDrawerOpen"
      :dataset-id="activeDatasetId"
    />
  </div>
</template>

<style scoped>
.qa-page {
  display: flex;
  flex: 1;
  min-height: 0;
}

.qa-page,
.qa-shell {
  min-height: 0;
}

.chat-window,
.messages {
  min-height: 0;
}

.qa-shell {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.qa-shell__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px 16px;
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.94);
}

.qa-shell__dataset-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.qa-shell__dataset-picker--subtle {
  gap: 5px;
  margin-left: auto;
}

.qa-shell__dataset-picker--subtle span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.qa-shell__dataset-picker select {
  min-height: 32px;
  min-width: 196px;
  padding: 0 11px;
  border-radius: 10px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text-primary);
}

.qa-shell__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ghost-btn {
  min-height: 36px;
  padding: 0 13px;
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
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(243, 245, 247, 0.95) 100%);
  display: flex;
  flex-direction: column;
}

.qa-inline-notice {
  margin: 16px 20px 0;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(185, 28, 28, 0.12);
  background: rgba(255, 245, 245, 0.92);
  color: #991b1b;
  font-size: 13px;
  line-height: 1.5;
}

.qa-empty-state {
  margin: 20px 20px 0;
  padding: 18px 20px;
  border: 1px dashed var(--line-strong);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}

.qa-empty-state h2 {
  margin: 0;
  font-size: 20px;
  color: var(--text-primary);
}

.qa-empty-state p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.messages {
  flex: 1;
  padding: 20px clamp(18px, 2.4vw, 32px) 14px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.messages--empty {
  padding-top: 12px;
}

.message {
  display: flex;
  gap: 14px;
  width: min(100%, 1320px);
  max-width: 100%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.system {
  align-self: center;
  width: min(100%, 920px);
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
  padding: 14px 16px;
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
  gap: 8px;
}

.citations-title {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5a677d;
}

.citations-list {
  display: grid;
  gap: 8px;
}

.citation-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 11px 13px;
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
  flex-shrink: 0;
  padding: 14px clamp(18px, 2.2vw, 24px) 18px;
  border-top: 1px solid rgba(20, 32, 51, 0.08);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 88px;
  gap: 12px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(14px);
}

.input-area textarea {
  min-height: 116px;
  max-height: 30svh;
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
    padding-inline: 16px;
  }

  .qa-shell__dataset-picker--subtle {
    margin-left: 0;
  }

  .qa-shell__dataset-picker select {
    min-width: min(100%, 280px);
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
