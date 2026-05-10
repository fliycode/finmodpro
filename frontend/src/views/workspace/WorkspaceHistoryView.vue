<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../../api/chat.js';
import ChatHistory from '../../components/ChatHistory.vue';
import HistoryWorkbench from '../../components/workspace/support/HistoryWorkbench.vue';
import AppIcon from '../../components/ui/AppIcon.vue';
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

/* ---- Pagination ---- */

const currentPage = ref(1);
const pageSize = ref(15);

const totalPages = computed(() => Math.max(1, Math.ceil(historyItems.value.length / pageSize.value)));
const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return historyItems.value.slice(start, start + pageSize.value);
});
const goToPage = (page) => {
  if (page < 1 || page > totalPages.value) return;
  currentPage.value = page;
};

/* ---- Data ---- */

const refreshHistory = async () => {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    historyItems.value = await chatApi.listHistory({
      datasetId: activeDatasetId.value,
      keyword: keyword.value,
    });
    currentPage.value = 1;
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
    query: { ...route.query, session: sessionId },
  });
};

const downloadExportPayload = ({ filename, content }) => {
  if (typeof window === 'undefined') return;
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
  if (!confirmed) return;

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

watch(() => route.query.keyword, (value) => {
  keyword.value = String(value || '');
});

watch(() => route.query.dataset, async () => {
  await refreshHistory();
});

onMounted(() => refreshHistory());
</script>

<template>
  <section class="workspace-support-page">
    <HistoryWorkbench>
      <template #filters>
        <div class="history-filters">
          <div class="history-search">
            <AppIcon name="search" :size="14" class="history-search__icon" aria-hidden="true" />
            <input
              v-model="keyword"
              type="text"
              class="history-search__input"
              placeholder="搜索会话标题或消息内容"
              @keydown.enter.prevent="applySearch"
            />
            <button v-if="keyword" type="button" class="history-search__clear" @click="clearSearch" aria-label="清空搜索">&times;</button>
          </div>

          <p v-if="activeDatasetId" class="history-filters__hint">
            当前按数据集 {{ activeDatasetId }} 查看相关会话
          </p>

          <div v-if="selectedSession" class="history-selected">
            <span class="history-selected__eyebrow">当前选中</span>
            <strong class="history-selected__title">{{ selectedSession.title }}</strong>
            <div class="history-selected__meta">
              <span>{{ getSessionTitleSourceLabel(selectedSession.titleSource) }}</span>
              <span>{{ getSessionTitleStatusLabel(selectedSession.titleStatus) }}</span>
              <span>{{ selectedSession.messageCount }} 条消息</span>
              <span v-if="selectedSession.contextFilters?.dataset_id">
                数据集 {{ selectedSession.contextFilters.dataset_id }}
              </span>
            </div>
          </div>

          <div v-if="errorMessage" class="history-error" role="alert">
            {{ errorMessage }}
          </div>
        </div>
      </template>

      <ChatHistory
        :items="pagedItems"
        :is-loading="isLoading"
        :active-session-id="activeSessionId"
        :enable-export="true"
        :show-session-metadata="true"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="historyItems.length"
        :total-pages="totalPages"
        @open-session="openSession"
        @export-session="exportSession"
        @delete-session="deleteSession"
        @go-to-page="goToPage"
      />
    </HistoryWorkbench>
  </section>
</template>

<style scoped>
.workspace-support-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---- Search ---- */

.history-filters {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-search {
  position: relative;
  display: flex;
  align-items: center;
}

.history-search__icon {
  position: absolute;
  left: 12px;
  color: var(--text-muted);
  pointer-events: none;
}

.history-search__input {
  width: 100%;
  height: 36px;
  padding: 0 32px 0 34px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-3);
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.history-search__input::placeholder {
  color: var(--text-muted);
}

.history-search__input:focus {
  border-color: var(--brand, #2457c5);
}

.history-search__clear {
  position: absolute;
  right: 8px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  transition: color 0.15s;
}

.history-search__clear:hover {
  color: var(--text-primary);
}

.history-filters__hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
}

/* ---- Selected Session ---- */

.history-selected {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 6px;
  border: 1px solid var(--line-soft);
  background: var(--surface-3);
}

.history-selected__eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.history-selected__title {
  font-size: 13px;
  color: var(--text-primary);
}

.history-selected__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.history-error {
  margin: 0;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid rgba(196, 73, 61, 0.2);
  background: rgba(196, 73, 61, 0.06);
  color: var(--risk-red, #c4493d);
  font-size: 12px;
}

@media (max-width: 720px) {
  .history-selected__meta {
    gap: 6px;
  }
}
</style>
