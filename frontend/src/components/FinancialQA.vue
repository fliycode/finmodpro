<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { qaApi } from '../api/qa.js';
import {
  getDefaultSessionFilters,
  getCitationDisclosureLabel,
  getSessionLoadFailureNotice,
  normalizeDatasetId,
  normalizeHistoryItems,
  updateMessageAt,
  shouldShowFinancialQaEmptyState,
} from '../lib/workspace-qa.js';
import ChatHistory from './ChatHistory.vue';
import ChatMemoryDrawer from './ChatMemoryDrawer.vue';
import AppIcon from './ui/AppIcon.vue';

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
const evidenceHistoryItems = computed(() => historyItems.value.slice(0, 5));
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

const getAvatarLabel = (role) => {
  if (role === 'user') return '我';
  if (role === 'assistant') return 'AI';
  return '系统';
};

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

const applySuggestedQuestion = (value) => {
  query.value = value;
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
  <div class="qa-shell">
    <!-- Page Hero -->
    <header class="qa-hero">
      <div class="qa-hero__icon">
        <div class="qa-hero__glow" />
        <div class="qa-hero__mic">
          <AppIcon name="mic" :size="22" />
        </div>
      </div>
      <div class="qa-hero__titles">
        <h1 class="qa-hero__title">智能问答</h1>
        <p class="qa-hero__subtitle">基于金融领域知识的精准问答与分析</p>
      </div>
      <div class="qa-hero__actions">
        <button
          type="button"
          class="qa-hero__action"
          title="历史会话"
          @click="historyDrawerOpen = true"
        >
          <AppIcon name="history" :size="18" />
        </button>
        <button
          type="button"
          class="qa-hero__action"
          title="记忆管理"
          @click="memoryDrawerOpen = true"
        >
          <AppIcon name="brain-circuit" :size="18" />
        </button>
        <button
          type="button"
          class="qa-hero__action qa-hero__action--new"
          title="新对话"
          @click="startNewConversation"
        >
          <AppIcon name="plus" :size="18" />
        </button>
      </div>
    </header>

    <!-- 2-Column Layout -->
    <div class="qa-layout">
      <!-- Main Chat Column -->
      <main class="qa-main">
        <div class="qa-main__card">
          <!-- Messages -->
          <div
            ref="messagesContainer"
            class="qa-messages"
            :class="{ 'qa-messages--empty': showEmptyState }"
          >
            <div v-if="sessionLoadFailureNotice" class="qa-notice qa-notice--warn" role="status">
              {{ sessionLoadFailureNotice }}
            </div>

            <!-- Empty State -->
            <div v-if="showEmptyState" class="qa-empty">
              <div class="qa-empty__orb" />
              <h2 class="qa-empty__title">开始新的分析</h2>
              <p class="qa-empty__text">
                输入您关心的金融问题，AI 将基于知识库与实时数据进行深度分析，
                并标注引用来源与推理证据。
              </p>
            </div>

            <template v-for="(msg, index) in visibleMessages" :key="`msg-${index}`">
              <!-- System Message -->
              <div v-if="msg.role === 'system'" class="qa-msg-system">
                <span>{{ msg.content }}</span>
              </div>

              <!-- User Message -->
              <div v-else-if="msg.role === 'user'" class="qa-msg qa-msg--user">
                <div class="qa-msg__body qa-msg__body--user">
                  <div class="qa-msg__bubble qa-msg__bubble--user">
                    {{ msg.content }}
                  </div>
                </div>
                <div class="qa-msg__avatar qa-msg__avatar--user">我</div>
              </div>

              <!-- Assistant Message -->
              <div v-else class="qa-msg qa-msg--assistant">
                <div class="qa-msg__avatar qa-msg__avatar--ai">AI</div>
                <div class="qa-msg__body">
                  <div
                    class="qa-msg__bubble qa-msg__bubble--ai"
                    :class="{ 'qa-msg__bubble--error': msg.isError }"
                  >
                    <!-- Answer header with badges -->
                    <div v-if="!msg.isStreaming && !msg.isError && msg.content" class="qa-answer__meta">
                      <span v-if="msg.answer_mode" class="qa-badge qa-badge--mode">
                        {{ msg.answer_mode === 'direct' ? '直接回答' : '引用回答' }}
                      </span>
                      <span v-if="msg.citations && msg.citations.length > 0" class="qa-badge qa-badge--citations">
                        引用 {{ msg.citations.length }} 篇资料
                      </span>
                      <span v-if="msg.duration_ms" class="qa-badge qa-badge--time">
                        {{ (msg.duration_ms / 1000).toFixed(1) }}s
                      </span>
                    </div>

                    <!-- Answer content -->
                    <div class="qa-answer__content" :class="{ 'qa-answer__content--streaming': msg.isStreaming }">
                      {{ msg.content }}
                      <span v-if="msg.isStreaming" class="qa-cursor" />
                    </div>

                    <!-- Loading indicator -->
                    <div v-if="msg.isStreaming && !msg.content" class="qa-loading">
                      <span /><span /><span />
                    </div>

                    <!-- Answer notice -->
                    <div v-if="msg.answer_notice" class="qa-answer__notice">
                      {{ msg.answer_notice }}
                    </div>

                    <!-- Jump to citations -->
                    <button
                      v-if="msg.citations && msg.citations.length > 0"
                      type="button"
                      class="qa-cite-jump"
                    >
                      {{ getCitationDisclosureLabel(msg.citations) }}
                    </button>
                  </div>
                </div>
              </div>
            </template>

            <!-- Initial loading -->
            <div v-if="isAsking && !hasStreamingAssistant" class="qa-msg qa-msg--assistant">
              <div class="qa-msg__avatar qa-msg__avatar--ai">AI</div>
              <div class="qa-msg__body">
                <div class="qa-msg__bubble qa-msg__bubble--ai qa-msg__bubble--loading">
                  <div class="qa-loading">
                    <span /><span /><span />
                  </div>
                  <p>正在整理结论与证据…</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Input Area -->
          <div class="qa-input-area">
            <div class="qa-input__row">
              <textarea
                v-model="query"
                rows="1"
                class="qa-input__textarea"
                placeholder="请输入您的问题，Enter 发送，Shift + Enter 换行"
                @keydown.enter.exact.prevent="handleAsk"
              />
              <button
                :disabled="isAsking || !query.trim()"
                class="qa-input__send"
                type="button"
                aria-label="发送"
                @click="handleAsk"
              >
                <AppIcon name="send" :size="18" />
              </button>
            </div>
            <div class="qa-input__footer">
              <div class="qa-input__toggles">
                <button type="button" class="qa-toggle">深度思考</button>
                <button type="button" class="qa-toggle">联网搜索</button>
                <button type="button" class="qa-toggle">引用溯源</button>
              </div>
              <button
                type="button"
                class="qa-input__clear"
                @click="resetConversation"
              >
                <AppIcon name="trash" :size="14" />
                清除对话
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Right Sidebar -->
      <aside class="qa-rail">
        <!-- Citations -->
        <section class="qa-rail__card">
          <header class="qa-rail__header">
            <h3><AppIcon name="file" :size="16" /> 引用来源</h3>
            <span class="qa-rail__count">{{ latestCitations.length }}</span>
          </header>
          <div v-if="latestCitations.length > 0" class="qa-rail__list">
            <div
              v-for="(cite, index) in latestCitations.slice(0, 5)"
              :key="`cite-${index}`"
              class="qa-cite-card"
            >
              <div class="qa-cite-card__index" :class="{ 'qa-cite-card__index--active': index === 0 }">
                {{ index + 1 }}
              </div>
              <div class="qa-cite-card__body">
                <div class="qa-cite-card__title">{{ cite.document_title || '未命名文档' }}</div>
                <div class="qa-cite-card__meta">
                  {{ cite.doc_type || '文档' }}
                  <span v-if="cite.page_label && cite.page_label !== 'N/A'">· {{ cite.page_label }}</span>
                </div>
                <div class="qa-cite-card__snippet">{{ cite.snippet || '暂无摘录。' }}</div>
                <div class="qa-cite-card__score" v-if="cite.score > 0">
                  相关度 {{ (cite.score * 100).toFixed(0) }}%
                </div>
              </div>
            </div>
          </div>
          <div v-else class="qa-rail__empty">
            <p>发送问题后，引用依据将在这里展示。</p>
          </div>
        </section>

        <!-- Recommended Questions -->
        <section class="qa-rail__card">
          <header class="qa-rail__header">
            <h3><AppIcon name="zap" :size="16" /> 相关问题推荐</h3>
            <button type="button" class="qa-rail__refresh" title="换一换">
              <AppIcon name="refresh" :size="12" />
            </button>
          </header>
          <div class="qa-rail__questions">
            <button
              v-for="q in recommendedQuestions"
              :key="q"
              type="button"
              class="qa-question-btn"
              @click="applySuggestedQuestion(q)"
            >
              {{ q }}
            </button>
          </div>
        </section>

        <!-- Recent Sessions -->
        <section v-if="evidenceHistoryItems.length > 0" class="qa-rail__card">
          <header class="qa-rail__header">
            <h3><AppIcon name="history" :size="16" /> 最近会话</h3>
            <button type="button" class="qa-rail__action-text" @click="historyDrawerOpen = true">
              查看全部
            </button>
          </header>
          <div class="qa-rail__sessions">
            <button
              v-for="item in evidenceHistoryItems"
              :key="item.id"
              type="button"
              class="qa-session-btn"
              @click="openSession(item.id)"
            >
              <span class="qa-session-btn__title">{{ item.title }}</span>
              <span class="qa-session-btn__time">{{ item.timestamp }}</span>
            </button>
          </div>
        </section>
      </aside>
    </div>

    <!-- History Drawer -->
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

    <!-- Memory Drawer -->
    <ChatMemoryDrawer
      v-model:open="memoryDrawerOpen"
      :dataset-id="activeDatasetId"
    />
  </div>
</template>

<style scoped>
/* ============================================
   QA Shell — Premium Dark Navy Dashboard
   ============================================ */

.qa-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

/* ---- Hero Header ---- */

.qa-hero {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  border: 1px solid rgba(66, 108, 255, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 19, 38, 0.94), rgba(7, 14, 28, 0.94)),
    radial-gradient(circle at top right, rgba(71, 94, 255, 0.14), transparent 38%);
  box-shadow: 0 20px 48px -32px rgba(4, 10, 22, 0.88);
}

.qa-hero__icon {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.qa-hero__glow {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1.5px solid rgba(84, 198, 255, 0.25);
  background: rgba(23, 58, 115, 0.65);
  box-shadow: 0 0 28px rgba(54, 150, 255, 0.55);
}

.qa-hero__mic {
  position: absolute;
  inset: 8px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #5fe7ff, #4e6dff);
  box-shadow: inset 0 2px 6px rgba(255, 255, 255, 0.24), 0 0 18px rgba(71, 109, 255, 0.5);
  color: #fff;
}

.qa-hero__titles {
  flex: 1;
  min-width: 0;
}

.qa-hero__title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.01em;
  color: #f4f7ff;
}

.qa-hero__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8597bb;
}

.qa-hero__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.qa-hero__action {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(102, 132, 255, 0.16);
  border-radius: 10px;
  background: rgba(15, 24, 44, 0.78);
  color: #95aacd;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.qa-hero__action:hover {
  border-color: rgba(102, 132, 255, 0.28);
  background: rgba(20, 32, 56, 0.92);
  color: #eef4ff;
  transform: translateY(-1px);
}

.qa-hero__action--new {
  border-color: rgba(100, 140, 255, 0.28);
  background: linear-gradient(135deg, rgba(44, 99, 255, 0.32), rgba(86, 75, 255, 0.26));
  color: #c5d4ff;
}

/* ---- Layout ---- */

.qa-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  min-height: 0;
  flex: 1;
}

/* ---- Main Chat Panel ---- */

.qa-main {
  min-width: 0;
  min-height: 0;
}

.qa-main__card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border: 1px solid rgba(66, 108, 255, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 19, 38, 0.88), rgba(7, 14, 28, 0.88)),
    radial-gradient(circle at top, rgba(71, 94, 255, 0.1), transparent 42%);
  box-shadow: 0 24px 56px -36px rgba(4, 10, 22, 0.86);
  overflow: hidden;
}

/* ---- Messages ---- */

.qa-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px 22px 14px;
}

.qa-messages--empty {
  justify-content: center;
  align-items: center;
}

/* Empty State */

.qa-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 380px;
  padding: 20px;
}

.qa-empty__orb {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(94, 128, 255, 0.18), rgba(124, 94, 255, 0.14));
  border: 1.5px solid rgba(102, 140, 255, 0.18);
  box-shadow: 0 0 40px rgba(71, 109, 255, 0.2);
  margin-bottom: 20px;
}

.qa-empty__title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: #eef4ff;
}

.qa-empty__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #8597bb;
}

/* Notice */

.qa-notice {
  padding: 11px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
}

.qa-notice--warn {
  border: 1px solid rgba(224, 92, 120, 0.24);
  background: rgba(51, 18, 34, 0.82);
  color: #ffb4c1;
}

/* System Messages */

.qa-msg-system {
  align-self: center;
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid rgba(102, 132, 255, 0.12);
  background: rgba(15, 24, 42, 0.72);
  color: #8fa1c2;
  font-size: 12px;
  max-width: 90%;
  text-align: center;
}

/* Message Row */

.qa-msg {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.qa-msg--user {
  flex-direction: row-reverse;
}

/* Avatars */

.qa-msg__avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  border: 1px solid rgba(103, 134, 255, 0.16);
}

.qa-msg__avatar--user {
  background: linear-gradient(135deg, rgba(41, 74, 153, 0.92), rgba(70, 42, 133, 0.92));
  color: #eff5ff;
}

.qa-msg__avatar--ai {
  background: linear-gradient(135deg, rgba(50, 90, 200, 0.55), rgba(98, 70, 220, 0.45));
  color: #b8ccff;
}

/* Message Body */

.qa-msg__body {
  min-width: 0;
  max-width: 85%;
}

.qa-msg__body--user {
  max-width: 78%;
}

/* Bubbles */

.qa-msg__bubble {
  border-radius: 14px;
  padding: 16px 18px;
  line-height: 1.72;
  font-size: 14px;
}

.qa-msg__bubble--ai {
  background: rgba(12, 20, 35, 0.9);
  color: #d8e5ff;
  border: 1px solid rgba(72, 108, 255, 0.12);
  box-shadow: 0 16px 36px -28px rgba(3, 8, 20, 0.9);
}

.qa-msg__bubble--user {
  background: linear-gradient(135deg, rgba(39, 70, 152, 0.9), rgba(68, 48, 144, 0.9));
  color: #eff5ff;
  border: 1px solid rgba(113, 142, 255, 0.24);
}

.qa-msg__bubble--error {
  border-color: rgba(224, 92, 120, 0.24);
  background: rgba(52, 18, 36, 0.84);
  color: #ffc1cc;
}

.qa-msg__bubble--loading {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
  padding: 18px 22px;
}

.qa-msg__bubble--loading p {
  margin: 0;
  font-size: 13px;
  color: #92a6cb;
}

/* Answer Meta Badges */

.qa-answer__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.1);
}

.qa-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 5px;
  letter-spacing: 0.02em;
}

.qa-badge--mode {
  background: rgba(54, 38, 109, 0.7);
  color: #9d87ff;
  border: 1px solid rgba(120, 100, 255, 0.16);
}

.qa-badge--citations {
  background: rgba(18, 63, 77, 0.7);
  color: #55d4bd;
  border: 1px solid rgba(80, 200, 180, 0.16);
}

.qa-badge--time {
  background: rgba(40, 50, 80, 0.6);
  color: #94a8cc;
  border: 1px solid rgba(100, 120, 160, 0.16);
}

/* Answer Content */

.qa-answer__content {
  white-space: pre-wrap;
  min-height: 20px;
}

.qa-answer__content--streaming {
  color: #c8d8f8;
}

.qa-cursor {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background: #7b9fff;
  vertical-align: text-bottom;
  margin-left: 1px;
  animation: cursorBlink 0.9s step-end infinite;
}

@keyframes cursorBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Loading Dots */

.qa-loading {
  display: inline-flex;
  gap: 5px;
}

.qa-loading span {
  width: 14px;
  height: 4px;
  border-radius: 999px;
  background: rgba(116, 144, 255, 0.5);
  animation: dotPulse 1.1s ease-in-out infinite;
}

.qa-loading span:nth-child(2) { animation-delay: 0.14s; }
.qa-loading span:nth-child(3) { animation-delay: 0.28s; }

@keyframes dotPulse {
  0%, 100% { opacity: 0.4; transform: scaleX(0.8); }
  50% { opacity: 1; transform: scaleX(1); }
}

/* Answer Notice */

.qa-answer__notice {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(72, 108, 255, 0.1);
  font-size: 12px;
  color: #a2b4d8;
  line-height: 1.6;
}

/* Citation Jump */

.qa-cite-jump {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #7b9fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.qa-cite-jump::after {
  content: '→';
}

/* ---- Input Area ---- */

.qa-input-area {
  border-top: 1px solid rgba(72, 108, 255, 0.12);
  padding: 14px 20px 16px;
  background: rgba(8, 15, 28, 0.7);
}

.qa-input__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: 10px;
  align-items: center;
  padding: 10px 10px 10px 18px;
  border-radius: 12px;
  border: 1px solid rgba(72, 108, 255, 0.16);
  background:
    linear-gradient(180deg, rgba(12, 20, 34, 0.94), rgba(9, 15, 28, 0.94)),
    radial-gradient(circle at 88% 100%, rgba(71, 94, 255, 0.14), transparent 24%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.qa-input__textarea {
  height: 26px;
  min-height: 26px;
  max-height: 140px;
  resize: none;
  overflow: auto;
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  font-size: 13.5px;
  color: #ecf4ff;
  line-height: 26px;
  outline: none;
}

.qa-input__textarea::placeholder {
  color: #637394;
}

.qa-input__send {
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #2f63ff, #596cff 65%, #785fff);
  color: #f6fbff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: 0 14px 28px -16px rgba(64, 96, 255, 0.7);
  transition:
    transform 0.2s ease,
    opacity 0.2s ease,
    filter 0.2s ease;
}

.qa-input__send:hover:not(:disabled) {
  filter: brightness(1.06);
  transform: translateY(-1px);
}

.qa-input__send:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.qa-input__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.qa-input__toggles {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.qa-toggle {
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid rgba(72, 108, 255, 0.16);
  border-radius: 7px;
  background: rgba(15, 24, 44, 0.7);
  color: #99accb;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.qa-toggle:hover {
  border-color: rgba(102, 138, 255, 0.26);
  background: rgba(20, 32, 56, 0.9);
  color: #d0dcff;
}

.qa-toggle:first-child {
  border-color: rgba(80, 130, 255, 0.28);
  background: rgba(30, 70, 200, 0.18);
  color: #a0bfff;
}

.qa-input__clear {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #7485a8;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.2s ease;
}

.qa-input__clear:hover {
  color: #b0c0e4;
}

/* ---- Right Sidebar ---- */

.qa-rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
}

.qa-rail__card {
  border: 1px solid rgba(66, 108, 255, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 19, 38, 0.9), rgba(7, 14, 28, 0.9)),
    radial-gradient(circle at top right, rgba(71, 94, 255, 0.08), transparent 36%);
  box-shadow: 0 20px 48px -36px rgba(4, 10, 22, 0.84);
  overflow: hidden;
}

.qa-rail__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.1);
}

.qa-rail__header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #eef4ff;
}

.qa-rail__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  border-radius: 999px;
  border: 1px solid rgba(93, 130, 255, 0.22);
  background: rgba(49, 68, 130, 0.24);
  color: #a9beff;
  font-size: 11px;
  font-weight: 700;
}

.qa-rail__refresh {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(102, 132, 255, 0.14);
  border-radius: 7px;
  background: rgba(15, 24, 44, 0.6);
  color: #8597bb;
  cursor: pointer;
  transition: color 0.2s ease;
}

.qa-rail__refresh:hover {
  color: #c5d4ff;
}

.qa-rail__action-text {
  border: 0;
  background: transparent;
  color: #7180a0;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.2s ease;
}

.qa-rail__action-text:hover {
  color: #b0c0e4;
}

.qa-rail__list {
  display: flex;
  flex-direction: column;
}

.qa-rail__empty {
  padding: 28px 16px;
  text-align: center;
}

.qa-rail__empty p {
  margin: 0;
  font-size: 13px;
  color: #6f7e9c;
  line-height: 1.6;
}

/* Citation Cards */

.qa-cite-card {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.06);
  transition: background-color 0.2s ease;
}

.qa-cite-card:last-child {
  border-bottom: 0;
}

.qa-cite-card__index {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(80, 96, 125, 0.5);
  color: #8796b5;
  font-size: 12px;
  font-weight: 700;
}

.qa-cite-card__index--active {
  border-color: rgba(66, 120, 255, 0.5);
  background: rgba(66, 120, 255, 0.2);
  color: #a0bfff;
}

.qa-cite-card__title {
  font-size: 13px;
  font-weight: 600;
  color: #dce5ff;
  line-height: 1.4;
  margin-bottom: 4px;
}

.qa-cite-card__meta {
  font-size: 11px;
  color: #6f7e9c;
  margin-bottom: 6px;
}

.qa-cite-card__snippet {
  font-size: 12px;
  color: #97a8cc;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.qa-cite-card__score {
  margin-top: 6px;
  font-size: 11px;
  color: #8896b6;
  font-weight: 600;
}

/* Question Buttons */

.qa-rail__questions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 14px 16px;
}

.qa-question-btn {
  width: 100%;
  text-align: left;
  padding: 11px 14px;
  border: 1px solid rgba(72, 108, 255, 0.14);
  border-radius: 10px;
  background: rgba(15, 24, 44, 0.7);
  color: #c7d3ee;
  font-size: 13px;
  line-height: 1.55;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
}

.qa-question-btn:hover {
  border-color: rgba(102, 138, 255, 0.24);
  background: rgba(20, 32, 56, 0.92);
  transform: translateY(-1px);
}

/* Session Buttons */

.qa-rail__sessions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px 14px;
}

.qa-session-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #c7d3ee;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.qa-session-btn:hover {
  border-color: rgba(72, 108, 255, 0.14);
  background: rgba(15, 24, 44, 0.7);
}

.qa-session-btn__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.qa-session-btn__time {
  font-size: 11px;
  color: #6f7e9c;
  flex-shrink: 0;
}

/* History Drawer Override */

:deep(.qa-history-drawer .el-drawer__body) {
  padding: 18px;
  background: linear-gradient(180deg, #0a1220, #0e1729);
}

/* ---- Responsive ---- */

@media (max-width: 1100px) {
  .qa-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .qa-rail {
    display: none;
  }
}

@media (max-width: 720px) {
  .qa-hero {
    flex-wrap: wrap;
    gap: 14px;
    padding: 16px 18px;
  }

  .qa-hero__title {
    font-size: 20px;
  }

  .qa-hero__icon {
    width: 48px;
    height: 48px;
  }

  .qa-hero__actions {
    width: 100%;
    justify-content: flex-end;
  }

  .qa-messages {
    padding: 14px 14px 10px;
  }

  .qa-input-area {
    padding: 12px 14px 14px;
  }

  .qa-input__toggles {
    gap: 4px;
  }

  .qa-toggle {
    padding: 0 9px;
    font-size: 11px;
  }
}
</style>
