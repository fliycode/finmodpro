<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../../api/chat.js';
import ChatHistory from '../../components/ChatHistory.vue';
import HistoryWorkbench from '../../components/workspace/support/HistoryWorkbench.vue';
import {
  buildSessionExportDownload,
  getSessionTitleSourceLabel,
  getSessionTitleStatusLabel,
} from '../../lib/workspace-qa.js';

const route = useRoute();
const router = useRouter();

const historyItems = ref([]);
const isLoading = ref(false);
const keyword = ref(String(route.query.keyword || ''));
const errorMessage = ref('');

const activeSessionId = computed(() => route.query.session ?? null);
const activeDatasetId = computed(() => route.query.dataset ?? null);
const selectedSession = computed(() =>
  historyItems.value.find((item) => String(item.id) === String(activeSessionId.value)) || null,
);

const refreshHistory = async () => {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    historyItems.value = await chatApi.listHistory({
      datasetId: activeDatasetId.value,
      keyword: keyword.value,
    });
  } catch (error) {
    console.error('加载历史会话失败:', error);
    errorMessage.value = '加载历史会话失败，请稍后重试。';
    historyItems.value = [];
  } finally {
    isLoading.value = false;
  }
};

const applySearch = async () => {
  const nextQuery = { ...route.query };
  const normalizedKeyword = keyword.value.trim();

  if (normalizedKeyword) {
    nextQuery.keyword = normalizedKeyword;
  } else {
    delete nextQuery.keyword;
  }

  await router.replace({ query: nextQuery });
  await refreshHistory();
};

const clearSearch = async () => {
  keyword.value = '';
  const nextQuery = { ...route.query };
  delete nextQuery.keyword;
  await router.replace({ query: nextQuery });
  await refreshHistory();
};

const openSession = (sessionId) => {
  router.push({
    path: '/workspace/qa',
    query: {
      ...route.query,
      session: sessionId,
    },
  });
};

const downloadExportPayload = ({ filename, content }) => {
  if (typeof window === 'undefined') {
    return;
  }

  const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = filename;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

const exportSession = async (sessionId) => {
  try {
    const payload = await chatApi.exportSession(sessionId);
    downloadExportPayload(buildSessionExportDownload(payload));
  } catch (error) {
    console.error('导出会话失败:', error);
    errorMessage.value = '导出会话失败，请稍后重试。';
  }
};

const deleteSession = async (sessionId) => {
  const confirmed = typeof window === 'undefined'
    ? true
    : window.confirm('确定删除这条历史会话吗？删除后不可恢复。');
  if (!confirmed) {
    return;
  }

  try {
    await chatApi.deleteSession(sessionId);
    if (String(activeSessionId.value) === String(sessionId)) {
      const nextQuery = { ...route.query };
      delete nextQuery.session;
      await router.replace({ query: nextQuery });
    }
    await refreshHistory();
  } catch (error) {
    console.error('删除会话失败:', error);
    errorMessage.value = '删除会话失败，请稍后重试。';
  }
};


watch(
  () => route.query.keyword,
  (value) => {
    keyword.value = String(value || '');
  },
);

watch(
  () => route.query.dataset,
  async () => {
    await refreshHistory();
  },
);

onMounted(async () => {
  await refreshHistory();
});
</script>

<template>
  <section class="workspace-support-page">
    <header class="workspace-support-page__header">
      <div>
        <p class="workspace-support-page__eyebrow">Support surface</p>
        <h1>历史会话</h1>
      </div>
    </header>

    <HistoryWorkbench>
      <template #filters>
        <div class="history-filters">
          <div class="history-filters__copy">
            <p class="history-filters__eyebrow">Session continuity</p>
            <h2>检索、回看、导出真实会话记录</h2>
          </div>

          <label class="history-filters__field">
            <span>关键词筛选</span>
            <input
              v-model="keyword"
              type="text"
              placeholder="搜索会话标题或消息内容"
              @keydown.enter.prevent="applySearch"
            />
          </label>

          <div class="history-filters__actions">
            <button type="button" class="ghost-btn ghost-btn--primary" @click="applySearch">
              搜索
            </button>
            <button type="button" class="ghost-btn" @click="clearSearch">清空</button>
          </div>

          <p v-if="activeDatasetId" class="history-filters__hint">
            当前按数据集 {{ activeDatasetId }} 查看相关会话。
          </p>

          <div v-if="selectedSession" class="history-session-summary">
            <span class="history-session-summary__eyebrow">当前选中会话</span>
            <strong>{{ selectedSession.title }}</strong>
            <div class="history-session-summary__meta">
              <span>{{ getSessionTitleSourceLabel(selectedSession.titleSource) }}</span>
              <span>{{ getSessionTitleStatusLabel(selectedSession.titleStatus) }}</span>
              <span>{{ selectedSession.messageCount }} 条消息</span>
              <span v-if="selectedSession.contextFilters?.dataset_id">
                数据集 {{ selectedSession.contextFilters.dataset_id }}
              </span>
            </div>
          </div>

          <div v-if="errorMessage" class="history-error">
            {{ errorMessage }}
          </div>
        </div>
      </template>

      <ChatHistory
        :items="historyItems"
        :is-loading="isLoading"
        :active-session-id="activeSessionId"
        :enable-export="true"
        :show-session-metadata="true"
        @refresh="refreshHistory"
        @open-session="openSession"
        @export-session="exportSession"
        @delete-session="deleteSession"
      />
    </HistoryWorkbench>
  </section>
</template>

<style scoped>
.workspace-support-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workspace-support-page__eyebrow,
.history-filters__eyebrow,
.history-session-summary__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.history-filters {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workspace-support-page h1,
.history-filters__copy h2 {
  margin: 0;
  color: #2f2418;
  letter-spacing: -0.03em;
}

.workspace-support-page h1 {
  font-size: 34px;
  line-height: 1.06;
}

.history-filters__copy h2 {
  font-size: 22px;
  line-height: 1.2;
}

.history-filters__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #6f5a42;
  font-size: 13px;
}

.history-filters__field input {
  min-height: 42px;
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 12px;
  padding: 0 14px;
  font: inherit;
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
}

.history-filters__actions {
  display: flex;
  gap: 10px;
}

.ghost-btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(95, 69, 35, 0.14);
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
  font-weight: 700;
  cursor: pointer;
}

.ghost-btn--primary {
  background: #8b5f2d;
  border-color: #8b5f2d;
  color: #fbf6ed;
}

.history-filters__hint,
.history-error {
  margin: 0;
  color: #6f5a42;
  font-size: 13px;
}

.history-session-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
  border: 1px solid rgba(95, 69, 35, 0.12);
}

.history-session-summary__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #6f5a42;
  font-size: 12px;
}

.history-error {
  color: #9b3131;
}

@media (max-width: 720px) {
  .history-filters__actions {
    flex-wrap: wrap;
  }
}
</style>
