<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { qaApi } from '../api/qa.js';
import {
  getDefaultSessionFilters,
  getCitationDisclosureLabel,
  getSessionLoadFailureNotice,
  getQaChromeState,
  normalizeDatasetId,
  normalizeHistoryItems,
  updateMessageAt,
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
const isLoadingSessions = ref(false);
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

const deleteSession = async (id) => {
  if (!id) {
    return;
  }
  const confirmed = typeof window === 'undefined'
    ? true
    : window.confirm('确定删除这条历史会话吗？删除后不可恢复。');
  if (!confirmed) {
    return;
  }

  try {
    await chatApi.deleteSession(id);
    if (String(currentSessionId.value) === String(id)) {
      currentSessionId.value = null;
      activeSessionLoadFailed.value = false;
      resetConversation();
      await clearSessionRoute();
    }
    await refreshSessionOptions();
  } catch (error) {
    console.error('删除会话失败:', error);
    messages.value.push({
      role: 'system',
      content: '删除会话失败，请稍后重试。',
      tone: 'warning',
    });
  }
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
  await refreshSessionOptions();
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
          title: '',
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

    messages.value.push(createAssistantPlaceholder());
    const assistantMessageIndex = messages.value.length - 1;
    const updateAssistantMessage = (patch) => {
      messages.value = updateMessageAt(messages.value, assistantMessageIndex, patch);
    };
    await scrollToBottom();

    const finalState = await qaApi.streamQuestion(currentQuery, {
      sessionId: currentSessionId.value,
      filters: activeSessionFilters.value,
      onMeta(meta) {
        updateAssistantMessage({
          citations: meta.citations,
          answer_mode: meta.answer_mode,
          answer_notice: meta.answer_notice,
          duration_ms: meta.duration_ms,
        });
      },
      onChunk(content, state) {
        updateAssistantMessage({ content: state.answer || content });
      },
      onDone(doneState) {
        updateAssistantMessage({
          content: doneState.answer || messages.value[assistantMessageIndex]?.content || '未获取到回答，请稍后重试。',
          citations: doneState.citations,
          answer_mode: doneState.answer_mode,
          answer_notice: doneState.answer_notice,
          duration_ms: doneState.duration_ms,
        });
      },
    });

    updateAssistantMessage({
      isStreaming: false,
      content: finalState.answer || messages.value[assistantMessageIndex]?.content || '未获取到回答，请稍后重试。',
    });
    await refreshSessionOptions();
  } catch (error) {
    const lastMessage = messages.value[messages.value.length - 1];
    if (lastMessage?.isStreaming) {
      messages.value = updateMessageAt(messages.value, messages.value.length - 1, {
        isStreaming: false,
        isError: true,
        content: getFriendlyErrorMessage(error),
        citations: [],
        answer_notice: '',
      });
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
    <div class="qa-shell">
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
      </div>

      <div class="chat-window">
        <div v-if="sessionLoadFailureNotice" class="qa-inline-notice" role="status">
          {{ sessionLoadFailureNotice }}
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

              <details v-if="msg.citations && msg.citations.length > 0" class="citations-container">
                <summary class="citations-title">
                  {{ getCitationDisclosureLabel(msg.citations) }}
                  <span class="citations-title__hint">展开查看</span>
                </summary>
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
              </details>
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
        @delete-session="deleteSession"
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
  margin: -18px calc(var(--workspace-content-padding-inline) * -1) -28px;
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
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: var(--surface-2);
}

.qa-shell__toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 12px 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 12px clamp(18px, 2.4vw, 32px);
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.94);
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

.messages {
  flex: 1;
  min-height: 0;
  padding: 24px clamp(22px, 3.2vw, 48px) 14px;
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
  border: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.78);
  border-radius: 14px;
  padding: 0;
}

.citations-title {
  cursor: pointer;
  list-style: none;
  padding: 10px 12px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5a677d;
  user-select: none;
}

.citations-title::-webkit-details-marker {
  display: none;
}

.citations-title::before {
  content: '›';
  display: inline-block;
  margin-right: 8px;
  color: #2457c5;
  font-size: 15px;
  transform: rotate(0deg);
  transition: transform 160ms ease;
}

.citations-container[open] .citations-title::before {
  transform: rotate(90deg);
}

.citations-title__hint {
  margin-left: 8px;
  color: #8a94a6;
  font-size: 11px;
  letter-spacing: 0;
  text-transform: none;
}

.citations-list {
  display: grid;
  gap: 8px;
  padding: 0 10px 10px;
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
  padding: 10px clamp(22px, 3.2vw, 48px) 14px;
  border-top: 1px solid rgba(20, 32, 51, 0.08);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  gap: 10px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(14px);
}

.input-area textarea {
  min-height: 48px;
  max-height: 18svh;
  resize: none;
  border-radius: 14px;
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  padding: 12px 14px;
  font: inherit;
  color: #142033;
  line-height: 1.45;
}

.send-btn {
  align-self: center;
  height: 42px;
  border: none;
  border-radius: 12px;
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
