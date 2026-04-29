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
const knowledgeGraphNodes = computed(() => {
  const labels = [...new Set(
    latestCitations.value
      .map((item) => item?.document_title || item?.doc_type || '')
      .map((value) => String(value).trim())
      .filter(Boolean),
  )].slice(0, 4);

  return labels.map((label, index) => ({
    id: `${label}-${index}`,
    label,
    tone: index === 0 ? 'primary' : 'secondary',
  }));
});
const recommendedQuestions = computed(() => {
  if (latestCitations.value.length > 0) {
    const firstTitle = latestCitations.value[0]?.document_title || '当前依据';
    return [
      `基于《${firstTitle}》提炼三条最关键的风险信号`,
      '把当前回答整理成适合汇报的风险摘要',
      '列出还需要补充验证的证据与下一步问题',
    ];
  }

  if (activeDatasetId.value) {
    return [
      '围绕当前知识库先给我一个整体判断框架',
      '先列出值得重点追问的三类风险主题',
      '给我一个适合继续深挖的分析提纲',
    ];
  }

  return [
    '先给我一个适合当前问题的分析框架',
    '把这个问题拆成结论、证据、待验证三部分',
    '给我三个更专业的追问方向',
  ];
});

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

const applySuggestedQuestion = (value) => {
  query.value = value;
  activeChapter.value = 'conversation';
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
              <button
                v-for="(cite, index) in latestCitations"
                :key="`${cite.document_title}-${index}`"
                type="button"
                class="evidence-card evidence-card--interactive"
                :title="`基于 ${cite.document_title || '该文档'} 继续追问`"
                @click="applySuggestedQuestion(`基于《${cite.document_title || '当前文档'}》继续补充关键风险与证据。`)"
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
              </button>
            </div>
            <p v-else class="evidence-empty">发送问题后，引用依据会在这里沉淀为证据索引。</p>
          </section>

          <section class="evidence-block">
            <header class="evidence-block__header">
              <h3>知识关系</h3>
              <span>{{ knowledgeGraphNodes.length ? '基于最新引用' : '等待来源' }}</span>
            </header>
            <div class="knowledge-graph">
              <div class="knowledge-graph__hub">AI</div>
              <div class="knowledge-graph__nodes">
                <button
                  v-for="node in knowledgeGraphNodes"
                  :key="node.id"
                  type="button"
                  class="knowledge-graph__node"
                  :class="`knowledge-graph__node--${node.tone}`"
                  @click="applySuggestedQuestion(`围绕《${node.label}》继续展开交叉验证。`)"
                >
                  {{ node.label }}
                </button>
                <p v-if="knowledgeGraphNodes.length === 0" class="knowledge-graph__empty">
                  回答生成后，这里会把来源文档组织成可继续追问的线索节点。
                </p>
              </div>
            </div>
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

          <section class="evidence-block">
            <header class="evidence-block__header">
              <h3>推荐追问</h3>
              <span>一键带入输入框</span>
            </header>
            <div class="recommendation-list">
              <button
                v-for="question in recommendedQuestions"
                :key="question"
                type="button"
                class="recommendation-item"
                @click="applySuggestedQuestion(question)"
              >
                {{ question }}
              </button>
            </div>
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
  gap: 20px;
  min-height: 0;
}

.qa-dossier-shell__chapters {
  display: none;
  gap: 8px;
}

.qa-dossier-shell__chapter {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(92, 124, 255, 0.16);
  border-radius: 999px;
  background: rgba(14, 24, 42, 0.82);
  color: #90a5cd;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.24s ease,
    background-color 0.24s ease,
    color 0.24s ease,
    transform 0.24s ease;
}

.qa-dossier-shell__chapter.is-active {
  background: linear-gradient(135deg, rgba(58, 99, 255, 0.3), rgba(123, 88, 255, 0.26));
  border-color: rgba(102, 138, 255, 0.42);
  color: #eef4ff;
}

.qa-dossier-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) minmax(280px, 0.82fr);
  gap: 20px;
  min-height: 0;
}

.qa-shell__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ghost-btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(90, 124, 255, 0.16);
  background: rgba(15, 24, 41, 0.78);
  color: #a9bce0;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.ghost-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(102, 138, 255, 0.3);
  color: #eef4ff;
  box-shadow: 0 14px 32px -24px rgba(40, 78, 189, 0.8);
}

.ghost-btn--primary {
  background: linear-gradient(135deg, #2c63ff, #5669ff 60%, #7a5dff);
  border-color: rgba(122, 147, 255, 0.62);
  color: #f7fbff;
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
  border: 1px solid rgba(224, 92, 120, 0.24);
  background: rgba(51, 18, 34, 0.82);
  color: #ffb4c1;
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
  gap: 18px;
  padding: 20px 20px 14px;
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
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  border: 1px solid rgba(103, 134, 255, 0.18);
  box-shadow: 0 16px 28px -24px rgba(10, 20, 40, 0.94);
}

.avatar-user {
  background: linear-gradient(135deg, rgba(41, 74, 153, 0.92), rgba(70, 42, 133, 0.92));
  color: #eff5ff;
}

.avatar-assistant {
  background: rgba(47, 73, 128, 0.52);
  color: #b8ccff;
}

.avatar-system {
  background: rgba(20, 29, 46, 0.92);
  color: #8fa1c2;
}

.bubble {
  border-radius: 16px;
  padding: 16px 18px;
  background: rgba(14, 22, 37, 0.88);
  color: #d8e5ff;
  border: 1px solid rgba(93, 124, 255, 0.12);
  line-height: 1.78;
  white-space: pre-wrap;
  box-shadow: 0 20px 44px -32px rgba(3, 8, 20, 0.94);
}

.message.user .bubble {
  background: linear-gradient(135deg, rgba(39, 70, 152, 0.92), rgba(68, 48, 144, 0.94));
  color: #eff5ff;
  border-color: rgba(113, 142, 255, 0.28);
}

.message.system .bubble {
  background: rgba(19, 27, 43, 0.9);
  color: #97a8c7;
  border-style: dashed;
}

.bubble-error {
  border-color: rgba(224, 92, 120, 0.26);
  background: rgba(52, 18, 36, 0.86);
  color: #ffc1cc;
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
  background: rgba(132, 156, 255, 0.54);
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
  color: #92a6cb;
}

.duration-info,
.answer-notice {
  margin-top: 10px;
  font-size: 12px;
}

.duration-info {
  color: #8ea4d1;
}

.answer-notice {
  color: #b8c8ec;
}

.citation-jump {
  margin-top: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #86a7ff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.citation-jump::after {
  content: '→';
}

.input-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 46px;
  gap: 12px;
  align-items: center;
  margin: 16px 18px 18px;
  padding: 14px 14px 14px 18px;
  border-radius: 14px;
  border: 1px solid rgba(98, 128, 255, 0.18);
  background:
    linear-gradient(180deg, rgba(12, 20, 34, 0.96), rgba(9, 15, 28, 0.96)),
    radial-gradient(circle at 88% 100%, rgba(90, 111, 255, 0.18), transparent 24%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.02),
    0 20px 44px -30px rgba(6, 12, 26, 0.96);
}

.input-area textarea {
  height: 28px;
  min-height: 28px;
  max-height: 140px;
  resize: none;
  overflow: auto;
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  color: #ecf4ff;
  line-height: 28px;
  outline: none;
}

.input-area textarea::placeholder {
  color: #7387ad;
}

.send-btn {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #2f63ff, #596cff 65%, #785fff);
  color: #f6fbff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 16px 30px -18px rgba(64, 96, 255, 0.78);
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.2s ease,
    filter 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  filter: brightness(1.05);
  transform: translateY(-1px) scale(1.01);
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
  color: #7c93bb;
}

.qa-empty-dossier h3 {
  margin: 0 0 10px;
  font-size: 26px;
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: #eef4ff;
}

.qa-empty-dossier p {
  margin: 0;
  color: #93a8cb;
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
  border-radius: 14px;
  border: 1px solid rgba(96, 126, 255, 0.14);
  background:
    linear-gradient(180deg, rgba(14, 22, 37, 0.86), rgba(10, 17, 30, 0.88)),
    radial-gradient(circle at top right, rgba(94, 90, 255, 0.12), transparent 36%);
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
  color: #7c93bb;
}

.qa-dossier-entry__header span {
  color: #a2b8e8;
  font-size: 12px;
  font-weight: 700;
}

.qa-dossier-entry__body {
  color: #dbe7ff;
  line-height: 1.8;
  white-space: pre-wrap;
}

.qa-dossier-entry__note {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(96, 126, 255, 0.12);
  color: #aabde6;
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
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(92, 124, 255, 0.14);
  background: rgba(14, 23, 39, 0.82);
  color: #c7d6f7;
  font-weight: 700;
  cursor: pointer;
  text-align: left;
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.evidence-action:hover,
.recommendation-item:hover,
.evidence-card--interactive:hover,
.knowledge-graph__node:hover {
  transform: translateY(-1px);
  border-color: rgba(106, 138, 255, 0.28);
  background: rgba(20, 32, 56, 0.92);
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
  color: #eef4ff;
}

.evidence-block__header span {
  color: #8197c1;
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
  border: 1px solid rgba(92, 124, 255, 0.14);
  background: rgba(14, 22, 37, 0.86);
  box-shadow: 0 18px 36px -30px rgba(3, 8, 20, 0.96);
}

.evidence-card--interactive,
.knowledge-graph__node,
.recommendation-item {
  width: 100%;
  border: 1px solid rgba(92, 124, 255, 0.14);
  cursor: pointer;
  text-align: left;
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.evidence-card--interactive {
  display: block;
}

.evidence-card__header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.evidence-card__index {
  color: #89a8ff;
  font-weight: 800;
}

.evidence-card__meta,
.evidence-history-list span {
  margin: 0 0 8px;
  color: #8197c1;
  font-size: 12px;
}

.evidence-card__snippet,
.evidence-history-list p {
  margin: 0;
  color: #c1d1f1;
  line-height: 1.65;
}

.evidence-history-list strong {
  display: block;
  margin-bottom: 6px;
  color: #eef4ff;
}

.evidence-empty {
  margin: 0;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(92, 124, 255, 0.12);
  background: rgba(14, 22, 37, 0.82);
  color: #93a8cb;
  line-height: 1.65;
}

:deep(.qa-history-drawer .el-drawer__body) {
  padding: 18px;
  background: linear-gradient(180deg, #0a1220, #0e1729);
}

.knowledge-graph {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.knowledge-graph__hub {
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(108, 136, 255, 0.22);
  background: linear-gradient(135deg, rgba(44, 99, 255, 0.28), rgba(98, 90, 255, 0.22));
  color: #eef4ff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.knowledge-graph__nodes,
.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.knowledge-graph__node,
.recommendation-item {
  min-height: 44px;
  padding: 0 14px;
  border-radius: 12px;
  background: rgba(14, 22, 37, 0.86);
  color: #d7e5ff;
  font-weight: 600;
}

.knowledge-graph__node--primary {
  color: #eef4ff;
}

.knowledge-graph__empty {
  margin: 0;
  padding: 14px;
  border-radius: 12px;
  border: 1px dashed rgba(92, 124, 255, 0.16);
  color: #93a8cb;
  line-height: 1.65;
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

  .conversation-canvas,
  .answer-dossier,
  .evidence-rail {
    margin-bottom: 16px;
  }
}

@media (max-width: 720px) {
  .input-area {
    grid-template-columns: minmax(0, 1fr) 44px;
    margin-inline: 14px;
  }

  .messages,
  .qa-dossier-list,
  .evidence-rail__body {
    padding-inline: 14px;
  }
}
</style>
