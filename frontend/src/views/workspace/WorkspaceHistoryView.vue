<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { chatApi } from '../../api/chat.js';
import ChatHistory from '../../components/ChatHistory.vue';
import { buildSessionExportDownload } from '../../lib/workspace-qa.js';

const route = useRoute();
const router = useRouter();

const historyItems = ref([]);
const isLoading = ref(false);
const keyword = ref(String(route.query.keyword || ''));
const errorMessage = ref('');

const activeSessionId = computed(() => route.query.session ?? null);
const activeDatasetId = computed(() => route.query.dataset ?? null);

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
  <div class="page-stack workspace-page">
    <section class="page-hero workspace-page__hero">
      <div class="workspace-page__hero-copy">
        <div class="page-hero__eyebrow">工作记录</div>
        <h1 class="page-hero__title">历史会话</h1>
        <p class="page-hero__subtitle">
          回看真实会话记录，按关键词筛选，再将完整对话导出为可归档 JSON。
        </p>
      </div>

      <div class="history-filters ui-card">
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
      </div>
    </section>

    <div v-if="errorMessage" class="history-error ui-card">
      {{ errorMessage }}
    </div>

    <ChatHistory
      :items="historyItems"
      :is-loading="isLoading"
      :active-session-id="activeSessionId"
      :enable-export="true"
      @refresh="refreshHistory"
      @open-session="openSession"
      @export-session="exportSession"
    />
  </div>
</template>

<style scoped>
.workspace-page__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(300px, 420px);
  gap: 18px;
  align-items: start;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}

.workspace-page__hero-copy {
  min-width: 0;
}

.history-filters {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.history-filters__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.history-filters__field input {
  min-height: 42px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  padding: 0 14px;
  font: inherit;
}

.history-filters__actions {
  display: flex;
  gap: 10px;
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

.history-filters__hint,
.history-error {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.history-error {
  color: #b42318;
}

@media (max-width: 900px) {
  .workspace-page__hero {
    grid-template-columns: 1fr;
  }

  .history-filters__actions {
    flex-wrap: wrap;
  }
}
</style>
