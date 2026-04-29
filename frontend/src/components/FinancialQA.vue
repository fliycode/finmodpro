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
import { getWorkspacePageModel } from '../lib/workspace-page-models.js';
import ChatHistory from './ChatHistory.vue';
import ChatMemoryDrawer from './ChatMemoryDrawer.vue';
import AppIcon from './ui/AppIcon.vue';
import AnswerDossier from './workspace/qa/AnswerDossier.vue';
import ConversationCanvas from './workspace/qa/ConversationCanvas.vue';
import EvidenceRail from './workspace/qa/EvidenceRail.vue';

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
const activeChapter = ref('conversation');
const qaChromeState = getQaChromeState();
const qaPageModel = getWorkspacePageModel('qa');

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
const assistantEntries = computed(() =>
  visibleMessages.value.filter((message) => message.role === 'assistant'),
);
const latestAssistantEntry = computed(() => (
  [...assistantEntries.value].reverse().find((message) => !message.isError) ?? null
));
const latestCitations = computed(() => latestAssistantEntry.value?.citations ?? []);
const chapterTabs = computed(() => qaPageModel?.regions ?? []);
const evidenceHistoryItems = computed(() => historyItems.value.slice(0, 5));

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

const setActiveChapter = (chapterId) => {
  activeChapter.value = chapterId;
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
  activeChapter.value = 'conversation';
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
      activeChapter.value = 'dossier';
    } else {
      messages.value = [{
        role: 'system',
        content: `已加载会话：${session.title || '未命名会话'}`,
        tone: 'success',
      }];
      activeChapter.value = 'conversation';
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
  activeChapter.value = 'conversation';
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
    activeChapter.value = 'dossier';
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
  <div class="qa-dossier-shell">
    <nav class="qa-dossier-shell__chapters" aria-label="QA chapters">
      <button
        v-for="region in chapterTabs"
        :key="region.id"
        type="button"
        :class="['qa-dossier-shell__chapter', { 'is-active': activeChapter === region.id }]"
        @click="setActiveChapter(region.id)"
      >
        {{ region.label }}
      </button>
    </nav>

    <div class="qa-dossier-layout">
      <ConversationCanvas
        :active="activeChapter === 'conversation'"
        :message-count="visibleMessages.length"
      >
        <template #toolbar>
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
        </template>

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
              :key="`${msg.role}-${index}`"
              :class="['message', msg.role, msg.tone ? `tone-${msg.tone}` : '']"
            >
              <div :class="getAvatarClass(msg.role)">{{ getAvatarLabel(msg.role) }}</div>
              <div class="message-content">
                <div :class="['bubble', { 'bubble-error': msg.isError }]">
                  <div class="bubble-text">{{ msg.content }}</div>
                  <div v-if="msg.isStreaming" class="typing-bars" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                  <div v-if="msg.duration_ms" class="duration-info">
                    耗时: {{ (msg.duration_ms / 1000).toFixed(2) }}s
                  </div>
                  <div v-if="msg.answer_notice" class="answer-notice">
                    {{ msg.answer_notice }}
                  </div>
                  <button
                    v-if="msg.citations && msg.citations.length > 0"
                    type="button"
                    class="citation-jump"
                    @click="setActiveChapter('evidence')"
                  >
                    {{ getCitationDisclosureLabel(msg.citations) }}
                  </button>
                </div>
              </div>
            </div>

            <div v-if="isAsking && !hasStreamingAssistant" class="message assistant">
              <div :class="getAvatarClass('assistant')">AI</div>
              <div class="message-content">
                <div class="bubble typing-surface">
                  <div class="typing-ledger" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </div>
                  <p>正在整理结论与证据…</p>
                </div>
              </div>
            </div>
          </div>

          <div class="input-area">
            <textarea
              v-model="query"
              rows="1"
              placeholder="输入您的金融分析问题，按 Enter 发送，Shift + Enter 换行"
              @keydown.enter.exact.prevent="handleAsk"
            />
            <button
              :disabled="isAsking || !query.trim()"
              class="send-btn"
              type="button"
              aria-label="发送"
              title="发送"
              @click="handleAsk"
            >
              <AppIcon name="send" />
            </button>
          </div>
        </div>
      </ConversationCanvas>

      <AnswerDossier
        :active="activeChapter === 'dossier'"
        :entry-count="assistantEntries.length"
        :is-empty="showEmptyState"
      >
        <div class="answer-dossier__body">
          <section v-if="showEmptyState" class="qa-empty-dossier">
            <p class="qa-empty-dossier__eyebrow">Awaiting first answer</p>
            <h3>新对话会先在这里形成结论档案。</h3>
            <p>提交问题后，摘要、回答提示和关键依据会先汇总为可阅读的档案，再同步到证据索引。</p>
          </section>

          <div v-else class="qa-dossier-list">
            <article
              v-for="(message, index) in assistantEntries"
              :key="`assistant-${index}`"
              class="qa-dossier-entry"
            >
              <header class="qa-dossier-entry__header">
                <p>结论 {{ index + 1 }}</p>
                <span v-if="message.duration_ms">{{ (message.duration_ms / 1000).toFixed(2) }}s</span>
              </header>
              <div class="qa-dossier-entry__body">{{ message.content }}</div>
              <div v-if="message.answer_notice" class="qa-dossier-entry__note">
                {{ message.answer_notice }}
              </div>
            </article>
          </div>
        </div>
      </AnswerDossier>

      <EvidenceRail
        :active="activeChapter === 'evidence'"
        :citation-count="latestCitations.length"
        :history-count="evidenceHistoryItems.length"
      >
        <div class="evidence-rail__body">
          <div class="evidence-rail__actions">
            <button type="button" class="evidence-action" @click="handleQaAction('history')">
              打开历史会话
            </button>
            <button type="button" class="evidence-action" @click="handleQaAction('memory')">
              打开记忆抽屉
            </button>
          </div>

          <div v-if="sessionLoadFailureNotice" class="qa-inline-notice qa-inline-notice--compact">
            {{ sessionLoadFailureNotice }}
          </div>

          <section class="evidence-block">
            <header class="evidence-block__header">
              <h3>最新依据</h3>
              <span>{{ latestCitations.length ? '来自最近结论' : '等待回答' }}</span>
            </header>
            <div v-if="latestCitations.length" class="evidence-list">
              <article
                v-for="(cite, index) in latestCitations"
                :key="`${cite.document_title}-${index}`"
                class="evidence-card"
              >
                <header class="evidence-card__header">
                  <span class="evidence-card__index">[{{ index + 1 }}]</span>
                  <strong>{{ cite.document_title || '未命名文档' }}</strong>
                </header>
                <p class="evidence-card__meta">
                  {{ cite.doc_type || '文档' }}
                  <span v-if="cite.page_label && cite.page_label !== 'N/A'">· 位置 {{ cite.page_label }}</span>
                  <span v-if="cite.score > 0">· 相关度 {{ (cite.score * 100).toFixed(0) }}%</span>
                </p>
                <p class="evidence-card__snippet">{{ cite.snippet || '暂无摘录。' }}</p>
              </article>
            </div>
            <p v-else class="evidence-empty">发送问题后，引用依据会在这里沉淀为证据索引。</p>
          </section>

          <section class="evidence-block">
            <header class="evidence-block__header">
              <h3>会话线索</h3>
              <span>{{ evidenceHistoryItems.length }} 条记录</span>
            </header>
            <ul class="evidence-history-list">
              <li v-for="item in evidenceHistoryItems" :key="item.id">
                <strong>{{ item.title }}</strong>
                <span>{{ item.timestamp }}</span>
                <p>{{ item.summaryPreview || item.preview }}</p>
              </li>
            </ul>
          </section>
        </div>
      </EvidenceRail>
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
.qa-dossier-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}

.qa-dossier-shell__chapters {
  display: none;
  gap: 8px;
}

.qa-dossier-shell__chapter {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(154, 106, 44, 0.12);
  border-radius: 999px;
  background: rgba(255, 248, 238, 0.9);
  color: #7f6547;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.qa-dossier-shell__chapter.is-active {
  background: #8b5f2d;
  border-color: #8b5f2d;
  color: #fbf6ed;
}

.qa-dossier-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) minmax(280px, 0.82fr);
  gap: 18px;
  min-height: 0;
}

.qa-shell__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ghost-btn {
  min-height: 36px;
  padding: 0 13px;
  border-radius: 8px;
  border: 1px solid rgba(154, 106, 44, 0.12);
  background: rgba(255, 248, 238, 0.9);
  color: #5f482e;
  font-weight: 700;
  cursor: pointer;
}

.ghost-btn--primary {
  background: #8b5f2d;
  border-color: #8b5f2d;
  color: #fbf6ed;
}

.chat-window,
.answer-dossier__body,
.evidence-rail__body {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-window {
  flex: 1;
}

.qa-inline-notice {
  margin: 16px 18px 0;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid rgba(180, 72, 52, 0.16);
  background: rgba(255, 243, 239, 0.96);
  color: #8d3f32;
  font-size: 13px;
  line-height: 1.55;
}

.qa-inline-notice--compact {
  margin: 0 0 16px;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px 18px 14px;
}

.messages--empty {
  padding-top: 10px;
}

.message {
  display: flex;
  gap: 14px;
}

.message.user {
  flex-direction: row-reverse;
}

.message.system {
  align-self: center;
  width: min(100%, 92%);
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.avatar-user {
  background: #7f5b2f;
  color: #fbf6ed;
}

.avatar-assistant {
  background: rgba(154, 106, 44, 0.14);
  color: #6c4f2b;
}

.avatar-system {
  background: rgba(154, 106, 44, 0.08);
  color: #8b7358;
}

.bubble {
  border-radius: 18px;
  padding: 14px 16px;
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
  border: 1px solid rgba(95, 69, 35, 0.1);
  line-height: 1.72;
  white-space: pre-wrap;
}

.message.user .bubble {
  background: #2f2418;
  color: #f7f1e5;
  border-color: transparent;
}

.message.system .bubble {
  background: rgba(255, 248, 238, 0.94);
  color: #6f5a42;
  border-style: dashed;
}

.bubble-error {
  border-color: rgba(180, 72, 52, 0.16);
  background: rgba(255, 243, 239, 0.96);
  color: #8d3f32;
}

.bubble-text {
  min-height: 24px;
}

.typing-bars,
.typing-ledger {
  display: inline-flex;
  gap: 6px;
  margin-top: 10px;
}

.typing-bars span,
.typing-ledger span {
  width: 16px;
  height: 4px;
  border-radius: 999px;
  background: rgba(139, 95, 45, 0.44);
  animation: ledgerPulse 1.1s ease-in-out infinite;
}

.typing-bars span:nth-child(2),
.typing-ledger span:nth-child(2) {
  animation-delay: 0.14s;
}

.typing-bars span:nth-child(3),
.typing-ledger span:nth-child(3) {
  animation-delay: 0.28s;
}

.typing-surface p {
  margin: 10px 0 0;
  font-size: 13px;
  color: #7f6547;
}

.duration-info,
.answer-notice {
  margin-top: 10px;
  font-size: 12px;
}

.duration-info {
  color: #7f6547;
}

.answer-notice {
  color: #8a6030;
}

.citation-jump {
  margin-top: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #8b5f2d;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.citation-jump::after {
  content: '→';
}

.input-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 42px;
  gap: 10px;
  align-items: center;
  margin: 16px 18px 18px;
  padding: 10px 10px 10px 16px;
  border-radius: 18px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  background: rgba(255, 251, 245, 0.98);
}

.input-area textarea {
  height: 24px;
  min-height: 24px;
  max-height: 120px;
  resize: none;
  overflow: auto;
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  color: #2f2418;
  line-height: 24px;
  outline: none;
}

.send-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: #8b5f2d;
  color: #fbf6ed;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.2s ease,
    background-color 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background: #7a5226;
  transform: translateY(-1px);
}

.send-btn :deep(.app-icon) {
  width: 17px;
  height: 17px;
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.qa-empty-dossier {
  padding: 24px 22px 26px;
}

.qa-empty-dossier__eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.qa-empty-dossier h3 {
  margin: 0 0 10px;
  font-size: 26px;
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: #2f2418;
}

.qa-empty-dossier p {
  margin: 0;
  color: #6f5a42;
  line-height: 1.75;
}

.qa-dossier-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  overflow-y: auto;
}

.qa-dossier-entry {
  padding: 18px 18px 16px;
  border-radius: 18px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  background: rgba(255, 251, 245, 0.92);
}

.qa-dossier-entry__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.qa-dossier-entry__header p {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #8b7358;
}

.qa-dossier-entry__header span {
  color: #8a6030;
  font-size: 12px;
  font-weight: 700;
}

.qa-dossier-entry__body {
  color: #2f2418;
  line-height: 1.8;
  white-space: pre-wrap;
}

.qa-dossier-entry__note {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(95, 69, 35, 0.1);
  color: #8a6030;
  font-size: 13px;
  line-height: 1.65;
}

.evidence-rail__body {
  padding: 16px;
  overflow-y: auto;
  gap: 18px;
}

.evidence-rail__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-action {
  min-height: 38px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  background: rgba(255, 251, 245, 0.96);
  color: #5f482e;
  font-weight: 700;
  cursor: pointer;
  text-align: left;
}

.evidence-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-block__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.evidence-block__header h3 {
  margin: 0;
  font-size: 15px;
  color: #2f2418;
}

.evidence-block__header span {
  color: #8b7358;
  font-size: 12px;
}

.evidence-list,
.evidence-history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.evidence-card,
.evidence-history-list li {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  background: rgba(255, 251, 245, 0.94);
}

.evidence-card__header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.evidence-card__index {
  color: #8b5f2d;
  font-weight: 800;
}

.evidence-card__meta,
.evidence-history-list span {
  margin: 0 0 8px;
  color: #8b7358;
  font-size: 12px;
}

.evidence-card__snippet,
.evidence-history-list p {
  margin: 0;
  color: #4d3d2a;
  line-height: 1.65;
}

.evidence-history-list strong {
  display: block;
  margin-bottom: 6px;
  color: #2f2418;
}

.evidence-empty {
  margin: 0;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 251, 245, 0.92);
  color: #6f5a42;
  line-height: 1.65;
}

:deep(.qa-history-drawer .el-drawer__body) {
  padding: 18px;
  background: #f7f1e5;
}

@keyframes ledgerPulse {
  0%,
  100% {
    opacity: 0.45;
    transform: scaleX(0.85);
  }
  50% {
    opacity: 1;
    transform: scaleX(1);
  }
}

@media (max-width: 1280px) {
  .qa-dossier-layout {
    grid-template-columns: minmax(0, 1fr) minmax(0, 0.92fr);
  }

  .evidence-rail {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1024px) {
  .qa-dossier-shell__chapters {
    display: flex;
    flex-wrap: wrap;
  }

  .qa-dossier-layout {
    display: block;
  }
}

@media (max-width: 720px) {
  .input-area {
    grid-template-columns: minmax(0, 1fr) 40px;
    margin-inline: 14px;
  }

  .messages,
  .qa-dossier-list,
  .evidence-rail__body {
    padding-inline: 14px;
  }
}
</style>
