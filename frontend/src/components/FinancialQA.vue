<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { qaApi } from '../api/qa.js';
import {
  getDefaultSessionFilters,
  getCitationDisclosureLabel,
  getQaMessageAvatar,
  getSessionLoadFailureNotice,
  normalizeDatasetId,
  normalizeHistoryItems,
  updateMessageAt,
  shouldShowFinancialQaEmptyState,
} from '../lib/workspace-qa.js';
import AppIcon from './ui/AppIcon.vue';

const ChatHistory = defineAsyncComponent(() => import('./ChatHistory.vue'));
const ChatMemoryDrawer = defineAsyncComponent(() => import('./ChatMemoryDrawer.vue'));
const MarkdownRenderer = defineAsyncComponent(() => import('./MarkdownRenderer.vue'));

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
const composerInputRef = ref(null);
const evidencePanelRef = ref(null);
const sessionOptions = ref([]);
const isLoadingSessions = ref(false);
const isHydratingSession = ref(false);
const activeSessionLoadFailed = ref(false);
const historyDrawerOpen = ref(false);
const memoryDrawerOpen = ref(false);
const activeSessionFilters = ref({});
const ragSteps = ref([]);
const avatarImageLoaded = ref(false);
const suggestionOffset = ref(0);
let sessionOptionsPromise = null;

const scheduleNonCriticalWork = (work) => {
  const runner = () => Promise.resolve().then(work);

  if (typeof window === 'undefined') {
    return runner();
  }

  return new Promise((resolve, reject) => {
    const run = () => runner().then(resolve).catch(reject);

    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => {
        void run();
      }, { timeout: 500 });
      return;
    }

    window.setTimeout(() => {
      void run();
    }, 0);
  });
};

const getMotionBehavior = () => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'smooth';
  }

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
};

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
const userAvatar = getQaMessageAvatar('user');
const assistantAvatar = getQaMessageAvatar('assistant');
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
const nonSystemMessageCount = computed(() =>
  visibleMessages.value.filter((message) => message.role !== 'system').length,
);
const activeConversationTitle = computed(() => {
  if (!currentSessionId.value) {
    return '新分析线程';
  }

  const matched = historyItems.value.find((item) => String(item.id) === String(currentSessionId.value));
  return matched?.title || '当前会话';
});
const activeDatasetLabel = computed(() =>
  activeDatasetId.value ? `数据集 ${activeDatasetId.value}` : '全局知识范围',
);
const latestAnswerModeLabel = computed(() => {
  const mode = latestAssistantEntry.value?.answer_mode;
  if (!mode) {
    return '';
  }
  return mode === 'direct' ? '直接回答' : '引用回答';
});
const conversationStateLabel = computed(() => {
  if (isHydratingSession.value) {
    return '加载会话中';
  }
  if (isAsking.value) {
    return '正在生成回答';
  }
  if (currentSessionId.value) {
    return '历史会话已接入';
  }
  return '等待首条问题';
});
const conversationDescription = computed(() => {
  if (activeSessionLoadFailed.value) {
    return '当前会话加载失败，仍可继续在当前页面发起新的分析。';
  }

  if (currentSessionId.value) {
    return `围绕「${activeConversationTitle.value}」持续追问，系统会沿用当前线程的证据与上下文。`;
  }

  return '从新的分析线程开始，系统会持续沉淀结论、证据和可回看的追问路径。';
});
const RAG_STEP_LABELS = {
  route: (d) => `路由决策: ${d.route_guard || d.route}`,
  rewrite_query: () => '查询改写完成',
  retrieve: (d) => `检索到 ${d.retrieved_count ?? 0} 条结果`,
  score_filter: (d) => `评分过滤: ${d.filtered_count ?? 0} 条通过`,
  build_context: (d) => `构建上下文: ${d.citation_count ?? 0} 篇引用`,
  direct_context: () => '直接回答模式',
};
const getStepLabel = (step) => {
  const fn = RAG_STEP_LABELS[step?.step];
  return fn ? fn(step) : step?.step || '处理中';
};
const activeStepLabel = computed(() => {
  const lastStep = ragSteps.value[ragSteps.value.length - 1];
  if (lastStep) {
    return getStepLabel(lastStep);
  }
  return isAsking.value ? '正在组织回答' : '等待提问';
});
const latestDurationLabel = computed(() => {
  const duration = latestAssistantEntry.value?.duration_ms;
  return duration ? `${(duration / 1000).toFixed(1)}s` : '—';
});
const summaryItems = computed(() => [
  {
    id: 'message-count',
    label: '消息数量',
    value: `${nonSystemMessageCount.value} 条`,
  },
  {
    id: 'evidence-count',
    label: '当前证据',
    value: latestCitations.value.length > 0 ? `${latestCitations.value.length} 条` : '待生成',
  },
  {
    id: 'pipeline-stage',
    label: '最新阶段',
    value: activeStepLabel.value,
  },
  {
    id: 'response-latency',
    label: '最近耗时',
    value: latestDurationLabel.value,
  },
]);
const overviewText = computed(() => (
  activeDatasetId.value
    ? `当前对话会自动限定在数据集 ${activeDatasetId.value} 的上下文中，适合围绕单个项目做连续追问。`
    : '当前对话默认面向全局金融知识范围，适合先获得结论框架，再逐步收束到具体证据。'
));
const recommendedQuestions = computed(() => {
  if (latestCitations.value.length > 0) {
    const firstTitle = latestCitations.value[0]?.document_title || '当前依据';
    return [
      `基于《${firstTitle}》提炼三条最关键的风险信号`,
      '把当前回答整理成适合汇报的风险摘要',
      '列出还需要补充验证的证据与下一步问题',
      '从现有引用里找出最薄弱的一处论证',
      '把当前分析转成管理层可执行的处置建议',
    ];
  }

  if (activeDatasetId.value) {
    return [
      '围绕当前知识库先给我一个整体判断框架',
      '先列出值得重点追问的三类风险主题',
      '给我一个适合继续深挖的分析提纲',
      '把数据集里的核心实体和关系先梳理出来',
      '先告诉我哪些部分最值得补证据',
    ];
  }

  return [
    '先给我一个适合当前问题的分析框架',
    '把这个问题拆成结论、证据、待验证三部分',
    '给我三个更专业的追问方向',
    '列出分析这个问题时最常见的误判点',
    '先告诉我应该补哪些背景信息',
  ];
});
const visibleRecommendedQuestions = computed(() => {
  if (recommendedQuestions.value.length <= 3) {
    return recommendedQuestions.value;
  }

  const offset = suggestionOffset.value % recommendedQuestions.value.length;
  const rotated = [
    ...recommendedQuestions.value.slice(offset),
    ...recommendedQuestions.value.slice(0, offset),
  ];
  return rotated.slice(0, 3);
});

const preloadAvatarImage = () => {
  if (!assistantAvatar.imageSrc) return;

  const link = document.createElement('link');
  link.rel = 'preload';
  link.as = 'image';
  link.href = assistantAvatar.imageSrcWebp || assistantAvatar.imageSrc;
  if (assistantAvatar.imageSrcWebp) {
    link.type = 'image/webp';
  }
  document.head.appendChild(link);

  const img = new Image();
  img.onload = () => {
    avatarImageLoaded.value = true;
  };
  img.onerror = () => {
    avatarImageLoaded.value = true;
  };
  img.src = assistantAvatar.imageSrcWebp || assistantAvatar.imageSrc;
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

const focusComposer = () => {
  composerInputRef.value?.focus();
};

const syncComposerHeight = async () => {
  await nextTick();
  const element = composerInputRef.value;
  if (!element) {
    return;
  }

  element.style.height = 'auto';
  const nextHeight = Math.min(Math.max(element.scrollHeight, 56), 180);
  element.style.height = `${nextHeight}px`;
};

const rotateRecommendedQuestions = () => {
  if (recommendedQuestions.value.length <= 3) {
    return;
  }
  suggestionOffset.value = (suggestionOffset.value + 1) % recommendedQuestions.value.length;
};

const applySuggestedQuestion = async (value) => {
  query.value = value;
  await syncComposerHeight();
  focusComposer();
};

const scrollToEvidence = () => {
  evidencePanelRef.value?.scrollIntoView({
    behavior: getMotionBehavior(),
    block: 'start',
  });
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: getMotionBehavior(),
    });
  }
};

const resetConversation = async () => {
  messages.value = [{ role: 'system', content: DEFAULT_SYSTEM_MESSAGE, tone: 'info' }];
  ragSteps.value = [];
  await syncComposerHeight();
};

const refreshSessionOptions = async () => {
  if (sessionOptionsPromise) {
    return sessionOptionsPromise;
  }

  isLoadingSessions.value = true;
  sessionOptionsPromise = (async () => {
    try {
      sessionOptions.value = await chatApi.listHistory({
        datasetId: activeDatasetId.value,
      });
      return sessionOptions.value;
    } catch (error) {
      console.error('加载会话列表失败:', error);
      return [];
    } finally {
      isLoadingSessions.value = false;
      sessionOptionsPromise = null;
    }
  })();

  return sessionOptionsPromise;
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
  ragSteps.value = [];
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
      await resetConversation();
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
  suggestionOffset.value = 0;
  activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
  await resetConversation();
  historyDrawerOpen.value = false;
  await clearSessionRoute();
  await refreshSessionOptions();
  focusComposer();
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
    await resetConversation();
  }
});

watch(
  () => route.query.dataset,
  async () => {
    if (!currentSessionId.value) {
      activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
    }
    suggestionOffset.value = 0;
    await refreshSessionOptions();
  },
);

watch(historyDrawerOpen, async (isOpen) => {
  if (!isOpen) {
    return;
  }

  await refreshSessionOptions();
});

watch(query, () => {
  void syncComposerHeight();
});

onMounted(async () => {
  activeSessionFilters.value = getDefaultSessionFilters(route.query.dataset);
  await syncComposerHeight();

  void scheduleNonCriticalWork(async () => {
    preloadAvatarImage();
    await Promise.allSettled([
      refreshSessionOptions(),
      import('./MarkdownRenderer.vue'),
      import('./ChatHistory.vue'),
      import('./ChatMemoryDrawer.vue'),
    ]);
  });

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
  ragSteps.value = [];
  await syncComposerHeight();
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
      onStep(stepData) {
        ragSteps.value.push(stepData);
      },
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
    <section class="qa-overview">
      <div class="qa-overview__body">
        <p class="qa-overview__eyebrow">Intelligent conversation</p>
        <h1 class="qa-overview__title">智能对话工作台</h1>
        <p class="qa-overview__text">
          {{ overviewText }}
        </p>
      </div>
      <div class="qa-overview__actions">
        <button type="button" class="qa-action-btn" aria-label="打开历史会话" @click="historyDrawerOpen = true">
          <AppIcon name="history" :size="16" />
          历史会话
        </button>
        <button type="button" class="qa-action-btn" aria-label="打开记忆管理" @click="memoryDrawerOpen = true">
          <AppIcon name="brain-circuit" :size="16" />
          记忆管理
        </button>
        <button type="button" class="qa-action-btn qa-action-btn--primary" @click="startNewConversation">
          <AppIcon name="plus" :size="16" />
          新建对话
        </button>
      </div>
    </section>

    <div class="qa-layout">
      <main class="qa-main">
        <section class="qa-panel qa-panel--conversation">
          <header class="qa-panel__header qa-panel__header--conversation">
            <div class="qa-panel__heading">
              <p class="qa-panel__eyebrow">Current thread</p>
              <h2 class="qa-panel__title">{{ activeConversationTitle }}</h2>
              <p class="qa-panel__desc">{{ conversationDescription }}</p>
            </div>
            <div class="qa-session-pills">
              <span class="qa-pill">{{ conversationStateLabel }}</span>
              <span class="qa-pill qa-pill--warm">{{ activeDatasetLabel }}</span>
              <span v-if="latestAnswerModeLabel" class="qa-pill qa-pill--brand">{{ latestAnswerModeLabel }}</span>
            </div>
          </header>

          <div class="qa-summary-grid">
            <article v-for="item in summaryItems" :key="item.id" class="qa-summary-card">
              <span class="qa-summary-card__label">{{ item.label }}</span>
              <strong class="qa-summary-card__value">{{ item.value }}</strong>
            </article>
          </div>

          <div
            ref="messagesContainer"
            class="qa-transcript"
            :class="{ 'qa-transcript--empty': showEmptyState }"
            role="log"
            aria-live="polite"
          >
            <div v-if="sessionLoadFailureNotice" class="qa-notice qa-notice--warn" role="status">
              {{ sessionLoadFailureNotice }}
            </div>

            <div v-if="showEmptyState" class="qa-empty">
              <div class="qa-empty__badge">
                <AppIcon name="spark" :size="14" />
                先从一个问题开始
              </div>
              <h3 class="qa-empty__title">把问题拆成结论、证据与待验证项</h3>
              <p class="qa-empty__text">
                适合先问结论框架，再追问证据来源和下一步动作。每次回答都会自动保留在同一条会话线程里。
              </p>
              <div class="qa-empty__actions">
                <button
                  v-for="prompt in visibleRecommendedQuestions"
                  :key="prompt"
                  type="button"
                  class="qa-question-btn"
                  @click="applySuggestedQuestion(prompt)"
                >
                  {{ prompt }}
                </button>
              </div>
            </div>

            <TransitionGroup name="qa-msg">
              <div
                v-for="(msg, index) in visibleMessages"
                :key="`msg-${index}`"
                :class="msg.role === 'system' ? 'qa-system-msg' : `qa-message qa-message--${msg.role === 'user' ? 'user' : 'assistant'}`"
              >
                <template v-if="msg.role === 'system'">
                  <span>{{ msg.content }}</span>
                </template>

                <template v-else-if="msg.role === 'user'">
                  <div class="qa-message__body qa-message__body--user">
                    <div class="qa-message__bubble qa-message__bubble--user">
                      {{ msg.content }}
                    </div>
                  </div>
                  <div class="qa-message__avatar qa-message__avatar--user">
                    <img
                      v-if="userAvatar.imageSrc"
                      :src="userAvatar.imageSrc"
                      :alt="userAvatar.imageAlt"
                      class="qa-message__avatar-image"
                    >
                    <span v-else>{{ userAvatar.label }}</span>
                  </div>
                </template>

                <template v-else>
                  <div class="qa-message__avatar qa-message__avatar--assistant">
                    <picture v-if="assistantAvatar.imageSrc">
                      <source
                        v-if="assistantAvatar.imageSrcWebp"
                        :srcset="assistantAvatar.imageSrcWebp"
                        type="image/webp"
                      >
                      <img
                        :src="assistantAvatar.imageSrc"
                        :alt="assistantAvatar.imageAlt"
                        class="qa-message__avatar-image"
                        :class="{ 'qa-message__avatar-image--loading': !avatarImageLoaded }"
                      >
                    </picture>
                    <span v-else>AI</span>
                  </div>
                  <div class="qa-message__body">
                    <div
                      class="qa-message__bubble qa-message__bubble--assistant"
                      :class="{ 'qa-message__bubble--error': msg.isError }"
                    >
                      <div v-if="!msg.isStreaming && !msg.isError && msg.content" class="qa-answer__meta">
                        <span v-if="msg.answer_mode" class="qa-badge">
                          {{ msg.answer_mode === 'direct' ? '直接回答' : '引用回答' }}
                        </span>
                        <span v-if="msg.citations && msg.citations.length > 0" class="qa-badge">
                          引用 {{ msg.citations.length }} 篇资料
                        </span>
                        <span v-if="msg.duration_ms" class="qa-badge">
                          {{ (msg.duration_ms / 1000).toFixed(1) }}s
                        </span>
                      </div>

                      <div class="qa-answer__content" :class="{ 'qa-answer__content--streaming': msg.isStreaming }">
                        <MarkdownRenderer
                          v-if="msg.content"
                          :content="msg.content"
                          :streaming="msg.isStreaming"
                        />
                        <span v-if="msg.isStreaming" class="qa-cursor" />
                      </div>

                      <div v-if="msg.isStreaming && !msg.content && ragSteps.length === 0" class="qa-loading">
                        <span /><span /><span />
                      </div>

                      <div v-if="msg.isStreaming && ragSteps.length > 0" class="qa-steps">
                        <div v-for="(step, i) in ragSteps" :key="i" class="qa-step">
                          <span class="qa-step__dot" />
                          <span class="qa-step__label">{{ getStepLabel(step) }}</span>
                        </div>
                      </div>

                      <div v-if="msg.answer_notice" class="qa-answer__notice">
                        {{ msg.answer_notice }}
                      </div>

                      <button
                        v-if="msg.citations && msg.citations.length > 0"
                        type="button"
                        class="qa-cite-jump"
                        @click="scrollToEvidence"
                      >
                        {{ getCitationDisclosureLabel(msg.citations) }}
                      </button>
                    </div>
                  </div>
                </template>
              </div>
            </TransitionGroup>

            <div v-if="isAsking && !hasStreamingAssistant" class="qa-message qa-message--assistant">
              <div class="qa-message__avatar qa-message__avatar--assistant">
                <img
                  v-if="assistantAvatar.imageSrc"
                  :src="assistantAvatar.imageSrc"
                  :alt="assistantAvatar.imageAlt"
                  class="qa-message__avatar-image"
                >
                <span v-else>AI</span>
              </div>
              <div class="qa-message__body">
                <div class="qa-message__bubble qa-message__bubble--assistant qa-message__bubble--loading">
                  <div class="qa-loading">
                    <span /><span /><span />
                  </div>
                  <p class="qa-loading__text">正在整理结论与证据…</p>
                </div>
              </div>
            </div>
          </div>

          <footer class="qa-composer">
            <div class="qa-composer__frame">
              <textarea
                ref="composerInputRef"
                v-model="query"
                rows="1"
                class="qa-composer__textarea"
                placeholder="请输入您的问题，Enter 发送，Shift + Enter 换行"
                aria-label="智能对话输入框"
                @input="syncComposerHeight"
                @keydown.enter.exact.prevent="handleAsk"
              />
              <button
                :disabled="isAsking || !query.trim()"
                class="qa-composer__send"
                type="button"
                @click="handleAsk"
              >
                <AppIcon name="send" :size="16" />
                发送
              </button>
            </div>
            <div class="qa-composer__meta">
              <div class="qa-composer__hints">
                <span class="qa-hint-chip">Enter 发送</span>
                <span class="qa-hint-chip">Shift + Enter 换行</span>
                <span class="qa-hint-chip qa-hint-chip--status">{{ activeStepLabel }}</span>
              </div>
              <button type="button" class="qa-link-btn" @click="resetConversation">
                清空画布
              </button>
            </div>
          </footer>
        </section>
      </main>

      <aside class="qa-rail">
        <section ref="evidencePanelRef" class="qa-panel">
          <header class="qa-panel__header qa-panel__header--compact">
            <div class="qa-panel__heading">
              <p class="qa-panel__eyebrow">Evidence</p>
              <h3 class="qa-panel__title qa-panel__title--sm">证据依据</h3>
            </div>
            <span class="qa-count-pill">{{ latestCitations.length }}</span>
          </header>
          <div v-if="latestCitations.length > 0" class="qa-citation-list">
            <article
              v-for="(cite, index) in latestCitations.slice(0, 5)"
              :key="`cite-${index}`"
              class="qa-citation-card"
            >
              <div class="qa-citation-card__index">{{ index + 1 }}</div>
              <div class="qa-citation-card__body">
                <div class="qa-citation-card__title">{{ cite.document_title || '未命名文档' }}</div>
                <div class="qa-citation-card__meta">
                  {{ cite.doc_type || '文档' }}
                  <span v-if="cite.page_label && cite.page_label !== 'N/A'">· {{ cite.page_label }}</span>
                </div>
                <p class="qa-citation-card__snippet">{{ cite.snippet || '暂无摘录。' }}</p>
                <div v-if="cite.score > 0" class="qa-citation-card__score">
                  相关度 {{ (cite.score * 100).toFixed(0) }}%
                </div>
              </div>
            </article>
          </div>
          <div v-else class="qa-empty-block">
            <p>发送问题后，引用依据会在这里聚合展示。</p>
          </div>
        </section>

        <section class="qa-panel">
          <header class="qa-panel__header qa-panel__header--compact">
            <div class="qa-panel__heading">
              <p class="qa-panel__eyebrow">Next prompts</p>
              <h3 class="qa-panel__title qa-panel__title--sm">相关问题推荐</h3>
            </div>
            <button type="button" class="qa-icon-btn" aria-label="刷新推荐问题" @click="rotateRecommendedQuestions">
              <AppIcon name="refresh" :size="14" />
            </button>
          </header>
          <div class="qa-question-list">
            <button
              v-for="prompt in visibleRecommendedQuestions"
              :key="prompt"
              type="button"
              class="qa-question-btn"
              @click="applySuggestedQuestion(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
        </section>

        <section v-if="evidenceHistoryItems.length > 0" class="qa-panel">
          <header class="qa-panel__header qa-panel__header--compact">
            <div class="qa-panel__heading">
              <p class="qa-panel__eyebrow">Recent sessions</p>
              <h3 class="qa-panel__title qa-panel__title--sm">最近会话</h3>
            </div>
            <button type="button" class="qa-link-btn" @click="historyDrawerOpen = true">
              查看全部
            </button>
          </header>
          <div class="qa-session-list">
            <button
              v-for="item in evidenceHistoryItems"
              :key="item.id"
              type="button"
              class="qa-session-btn"
              @click="openSession(item.id)"
            >
              <span class="qa-session-btn__title">{{ item.title }}</span>
              <span class="qa-session-btn__meta">{{ item.timestamp }}</span>
            </button>
          </div>
        </section>
      </aside>
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
.qa-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.qa-overview,
.qa-panel {
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.qa-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  background: rgba(253, 249, 239, 0.94);
}

.qa-overview__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 760px;
}

.qa-overview__eyebrow,
.qa-panel__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.qa-overview__title,
.qa-panel__title {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.1;
}

.qa-overview__title {
  font-size: clamp(2rem, 3vw, 2.6rem);
  font-family: var(--heading);
}

.qa-overview__text,
.qa-panel__desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.qa-overview__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.qa-action-btn,
.qa-icon-btn,
.qa-link-btn,
.qa-question-btn,
.qa-session-btn,
.qa-cite-jump,
.qa-composer__send {
  border: 1px solid transparent;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.qa-action-btn {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  border-radius: var(--radius-pill);
  border-color: var(--line-strong);
  background: rgba(255, 255, 255, 0.88);
  color: var(--text-primary);
  cursor: pointer;
}

.qa-action-btn:hover,
.qa-question-btn:hover,
.qa-session-btn:hover,
.qa-cite-jump:hover,
.qa-icon-btn:hover,
.qa-link-btn:hover,
.qa-composer__send:hover:not(:disabled) {
  border-color: rgba(36, 87, 197, 0.28);
  box-shadow: var(--shadow-xs);
}

.qa-action-btn--primary,
.qa-composer__send {
  border-color: rgba(36, 87, 197, 0.2);
  background: var(--brand);
  color: var(--text-inverse);
}

.qa-action-btn--primary:hover,
.qa-composer__send:hover:not(:disabled) {
  background: var(--brand-hover);
}

.qa-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  min-height: 0;
  align-items: start;
}

.qa-main,
.qa-rail,
.qa-panel--conversation {
  min-width: 0;
  min-height: 0;
}

.qa-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.qa-panel--conversation {
  height: 100%;
}

.qa-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 24px 18px;
}

.qa-panel__header--conversation {
  padding-bottom: 16px;
}

.qa-panel__header--compact {
  padding-bottom: 14px;
}

.qa-panel__heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.qa-panel__title {
  font-size: 1.5rem;
}

.qa-panel__title--sm {
  font-size: 1.125rem;
}

.qa-session-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.qa-pill,
.qa-count-pill,
.qa-badge,
.qa-hint-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
}

.qa-pill,
.qa-count-pill,
.qa-badge,
.qa-hint-chip {
  border: 1px solid var(--line-soft);
  background: var(--surface-3);
  color: var(--text-secondary);
}

.qa-pill--brand {
  border-color: rgba(36, 87, 197, 0.18);
  background: var(--brand-soft);
  color: var(--brand);
}

.qa-pill--warm {
  border-color: rgba(183, 121, 31, 0.16);
  background: var(--warning-50);
  color: var(--warning-600);
}

.qa-count-pill {
  color: var(--brand);
}

.qa-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 24px 20px;
}

.qa-summary-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 92px;
  padding: 16px 18px;
  border: 1px solid rgba(183, 121, 31, 0.12);
  border-radius: 18px;
  background: rgba(253, 249, 239, 0.74);
}

.qa-summary-card__label {
  font-size: 12px;
  color: var(--text-muted);
}

.qa-summary-card__value {
  font-size: 18px;
  line-height: 1.45;
  color: var(--text-primary);
}

.qa-transcript {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  padding: 4px 24px 20px;
  background: rgba(248, 249, 251, 0.92);
  border-top: 1px solid var(--line-soft);
  border-bottom: 1px solid var(--line-soft);
}

.qa-transcript--empty {
  justify-content: center;
}

.qa-empty {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 640px;
  padding: 28px;
  border: 1px dashed rgba(183, 121, 31, 0.28);
  border-radius: 24px;
  background: rgba(253, 249, 239, 0.78);
}

.qa-empty__badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-pill);
  background: rgba(36, 87, 197, 0.08);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

.qa-empty__title {
  margin: 0;
  font-size: 26px;
  line-height: 1.25;
  color: var(--text-primary);
}

.qa-empty__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.qa-empty__actions,
.qa-question-list,
.qa-session-list,
.qa-citation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.qa-notice {
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 13px;
  line-height: 1.65;
}

.qa-notice--warn {
  border: 1px solid rgba(196, 73, 61, 0.2);
  background: var(--risk-50);
  color: var(--risk-600);
}

.qa-system-msg {
  align-self: center;
  padding: 8px 14px;
  border-radius: var(--radius-pill);
  background: var(--surface-3);
  color: var(--text-muted);
  font-size: 12px;
}

.qa-message {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.qa-message--user {
  justify-content: flex-end;
}

.qa-message--user .qa-message__body {
  order: 1;
}

.qa-message--user .qa-message__avatar {
  order: 2;
}

.qa-message__avatar {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: var(--surface-3);
  border: 1px solid var(--line-soft);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  overflow: hidden;
}

.qa-message__avatar--assistant {
  background: rgba(253, 249, 239, 0.88);
  border-color: rgba(183, 121, 31, 0.14);
}

.qa-message__avatar--user {
  background: var(--brand);
  border-color: rgba(36, 87, 197, 0.22);
  color: var(--text-inverse);
}

.qa-message__avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.qa-message__avatar-image--loading {
  opacity: 0.8;
}

.qa-message__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  max-width: min(840px, calc(100% - 52px));
}

.qa-message__body--user {
  align-items: flex-end;
}

.qa-message__bubble {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid var(--line-soft);
  box-shadow: var(--shadow-xs);
}

.qa-message__bubble--assistant {
  background: var(--surface-2);
}

.qa-message__bubble--user {
  background: rgba(36, 87, 197, 0.08);
  border-color: rgba(36, 87, 197, 0.14);
  color: var(--text-primary);
}

.qa-message__bubble--error {
  border-color: rgba(196, 73, 61, 0.18);
  background: rgba(254, 242, 241, 0.92);
}

.qa-message__bubble--loading {
  min-height: 96px;
  justify-content: center;
}

.qa-answer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-answer__content {
  min-width: 0;
  color: var(--text-primary);
}

.qa-answer__content--streaming {
  min-height: 24px;
}

.qa-answer__notice {
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--warning-50);
  color: var(--warning-600);
  font-size: 13px;
  line-height: 1.6;
}

.qa-cite-jump {
  align-self: flex-start;
  min-height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-pill);
  border-color: rgba(36, 87, 197, 0.18);
  background: rgba(36, 87, 197, 0.06);
  color: var(--brand);
  cursor: pointer;
}

.qa-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 2px;
}

.qa-step {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.qa-step__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--brand);
  flex: 0 0 8px;
}

.qa-loading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.qa-loading span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--brand);
  animation: qa-bounce 1s infinite ease-in-out;
}

.qa-loading span:nth-child(2) {
  animation-delay: 0.12s;
}

.qa-loading span:nth-child(3) {
  animation-delay: 0.24s;
}

.qa-loading__text {
  margin: 12px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.qa-cursor {
  display: inline-block;
  width: 8px;
  height: 18px;
  margin-left: 4px;
  vertical-align: middle;
  border-radius: 999px;
  background: var(--brand);
  animation: qa-caret 1s step-end infinite;
}

.qa-composer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 24px 22px;
  background: rgba(255, 255, 255, 0.96);
}

.qa-composer__frame {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(183, 121, 31, 0.14);
  border-radius: 22px;
  background: rgba(253, 249, 239, 0.72);
}

.qa-composer__textarea {
  flex: 1;
  min-height: 56px;
  max-height: 180px;
  resize: none;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.65;
}

.qa-composer__textarea::placeholder {
  color: var(--text-muted);
}

.qa-composer__send {
  min-width: 96px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border-radius: var(--radius-pill);
  cursor: pointer;
}

.qa-composer__send:disabled {
  background: var(--surface-3);
  border-color: var(--line-soft);
  color: var(--text-muted);
  cursor: not-allowed;
  box-shadow: none;
}

.qa-composer__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.qa-composer__hints {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qa-hint-chip--status {
  color: var(--brand);
  border-color: rgba(36, 87, 197, 0.16);
  background: rgba(36, 87, 197, 0.05);
}

.qa-icon-btn,
.qa-link-btn {
  min-height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.qa-icon-btn {
  width: 40px;
  justify-content: center;
  display: inline-flex;
  align-items: center;
}

.qa-link-btn {
  display: inline-flex;
  align-items: center;
  border-color: var(--line-soft);
}

.qa-rail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 0;
}

.qa-citation-card,
.qa-session-btn,
.qa-question-btn {
  width: 100%;
  text-align: left;
}

.qa-citation-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.qa-citation-card__index {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.1);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

.qa-citation-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.qa-citation-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.qa-citation-card__meta,
.qa-citation-card__score,
.qa-session-btn__meta {
  font-size: 12px;
  color: var(--text-muted);
}

.qa-citation-card__snippet {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}

.qa-question-btn,
.qa-session-btn {
  min-height: 44px;
  display: inline-flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 14px 16px;
  border-radius: 18px;
  border-color: var(--line-soft);
  background: var(--surface-2);
  color: var(--text-primary);
  cursor: pointer;
}

.qa-question-btn {
  font-size: 14px;
  line-height: 1.55;
}

.qa-session-btn {
  flex-direction: column;
  gap: 4px;
}

.qa-session-btn__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.qa-empty-block {
  padding: 0 24px 24px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.qa-msg-enter-active,
.qa-msg-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.qa-msg-enter-from,
.qa-msg-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.qa-action-btn:focus-visible,
.qa-icon-btn:focus-visible,
.qa-link-btn:focus-visible,
.qa-question-btn:focus-visible,
.qa-session-btn:focus-visible,
.qa-cite-jump:focus-visible,
.qa-composer__send:focus-visible,
.qa-composer__textarea:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}

@keyframes qa-bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes qa-caret {
  50% {
    opacity: 0;
  }
}

@media (max-width: 1200px) {
  .qa-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .qa-rail {
    position: static;
  }
}

@media (max-width: 900px) {
  .qa-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .qa-overview,
  .qa-panel__header,
  .qa-summary-grid,
  .qa-transcript,
  .qa-composer,
  .qa-empty-block {
    padding-left: 18px;
    padding-right: 18px;
  }

  .qa-overview {
    padding-top: 20px;
    padding-bottom: 20px;
    flex-direction: column;
  }

  .qa-overview__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .qa-panel__header {
    flex-direction: column;
  }

  .qa-session-pills {
    justify-content: flex-start;
  }

  .qa-summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .qa-message__body {
    max-width: 100%;
  }

  .qa-composer__frame,
  .qa-composer__meta {
    flex-direction: column;
    align-items: stretch;
  }

  .qa-composer__send {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .qa-action-btn,
  .qa-icon-btn,
  .qa-link-btn,
  .qa-question-btn,
  .qa-session-btn,
  .qa-cite-jump,
  .qa-composer__send,
  .qa-msg-enter-active,
  .qa-msg-leave-active,
  .qa-loading span,
  .qa-cursor {
    animation: none !important;
    transition: none !important;
  }
}
</style>
