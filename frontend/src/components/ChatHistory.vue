<script setup>
import { getSessionTitleSourceLabel, getSessionTitleStatusLabel } from '../lib/workspace-qa.js';

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  activeSessionId: {
    type: [String, Number],
    default: null,
  },
  enableExport: {
    type: Boolean,
    default: false,
  },
  showSessionMetadata: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['open-session', 'refresh', 'export-session', 'delete-session']);

const handleOpenSession = (id) => {
  emit('open-session', id);
};

const handleExportSession = (id) => {
  emit('export-session', id);
};

const handleDeleteSession = (id) => {
  emit('delete-session', id);
};

const shouldShowSummaryPreview = (item) =>
  Boolean(item?.summaryPreview) && item.summaryPreview !== item.preview;

const shouldShowTitleStatus = (item) =>
  Boolean(item?.titleStatus) && item.titleStatus !== 'ready';

const getDatasetLabel = (item) => {
  const datasetId = item?.contextFilters?.dataset_id;
  return datasetId === null || datasetId === undefined || datasetId === ''
    ? ''
    : `数据集 ${datasetId}`;
};
</script>

<template>
  <div class="history-shell">
    <div class="history-shell__toolbar">
      <div>
        <span class="history-shell__eyebrow">历史会话</span>
        <p class="history-shell__subtitle">按最近使用时间继续之前的问答上下文。</p>
      </div>
      <button class="refresh-btn" @click="$emit('refresh')" :disabled="isLoading">刷新</button>
    </div>

    <div v-if="isLoading" class="skeleton-list">
      <div v-for="n in 4" :key="n" class="skeleton-item">
        <div class="skeleton-main">
          <div class="skeleton-title" />
          <div class="skeleton-preview" />
        </div>
        <div class="skeleton-meta" />
      </div>
    </div>
    <div v-else-if="items.length === 0" class="state-msg empty">
      <div class="state-msg__stack">
        <div>暂无历史记录</div>
        <div class="state-msg__footnote">新对话创建后会自动出现在这里。</div>
      </div>
    </div>
    <div v-else class="history-list">
      <article
        v-for="item in items"
        :key="item.id"
        class="history-item"
        :class="{ 'is-active': String(activeSessionId) === String(item.id) }"
      >
        <div class="item-main">
          <div class="item-title-row">
            <div class="item-title">{{ item.title }}</div>
            <div v-if="showSessionMetadata" class="item-badges">
              <span class="item-badge">
                {{ getSessionTitleSourceLabel(item.titleSource) }}
              </span>
              <span
                v-if="shouldShowTitleStatus(item)"
                class="item-badge item-badge--status"
              >
                {{ getSessionTitleStatusLabel(item.titleStatus) }}
              </span>
              <span v-if="getDatasetLabel(item)" class="item-badge">
                {{ getDatasetLabel(item) }}
              </span>
            </div>
          </div>
          <div v-if="showSessionMetadata && shouldShowSummaryPreview(item)" class="item-summary">
            {{ item.summaryPreview }}
          </div>
          <div class="item-preview">{{ item.preview }}</div>
        </div>
        <div class="item-meta">
          <div class="item-time">{{ item.timestamp }}</div>
          <div v-if="showSessionMetadata" class="item-count">{{ item.messageCount }} 条消息</div>
          <div class="item-actions">
            <button type="button" class="view-btn" @click="handleOpenSession(item.id)">继续对话</button>
            <button
              v-if="enableExport"
              type="button"
              class="export-btn"
              @click="handleExportSession(item.id)"
            >
              导出
            </button>
            <button
              type="button"
              class="delete-btn"
              @click="handleDeleteSession(item.id)"
            >
              删除
            </button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.history-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.history-shell__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.history-shell__eyebrow {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.history-shell__subtitle {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.refresh-btn {
  padding: 8px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.state-msg {
  flex: 1;
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border: 1px dashed var(--line-strong);
  border-radius: 16px;
  background: var(--surface-3);
  font-size: 14px;
}

.state-msg__stack {
  text-align: center;
}

.state-msg__footnote {
  font-size: 12px;
  margin-top: 8px;
  color: #9aa5b5;
}

.history-list,
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item,
.skeleton-item {
  display: flex;
  justify-content: space-between;
  width: 100%;
  padding: 15px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: #fff;
}

.history-item {
  text-align: left;
  transition: all 0.2s;
}

.history-item:hover,
.history-item.is-active {
  border-color: rgba(36, 87, 197, 0.18);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 12px 24px -20px rgba(36, 87, 197, 0.18);
}

.item-main,
.skeleton-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.item-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.item-title {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
}

.item-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.item-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.item-badge--status {
  background: rgba(176, 125, 12, 0.12);
  color: #8a5a00;
}

.item-summary,
.item-preview {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.item-summary {
  color: var(--text-primary);
}

.item-preview {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  margin-left: 14px;
  flex-shrink: 0;
}

.item-time {
  font-size: 12px;
  color: var(--text-muted);
}

.item-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.item-actions {
  display: flex;
  gap: 8px;
}

.view-btn,
.export-btn,
.delete-btn {
  border: none;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.view-btn {
  background: var(--surface-3);
  color: var(--brand);
}

.export-btn {
  background: rgba(16, 35, 61, 0.08);
  color: var(--text-secondary);
}

.delete-btn {
  background: rgba(185, 28, 28, 0.08);
  color: #991b1b;
}

.skeleton-title,
.skeleton-preview,
.skeleton-meta {
  border-radius: 4px;
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-title {
  height: 18px;
  width: 40%;
  background: #e2e8f0;
}

.skeleton-preview {
  height: 14px;
  width: 70%;
  background: #f1f5f9;
}

.skeleton-meta {
  height: 14px;
  width: 60px;
  background: #f1f5f9;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.45; }
  100% { opacity: 1; }
}

@media (max-width: 760px) {
  .history-item,
  .skeleton-item {
    flex-direction: column;
    gap: 12px;
  }

  .item-title-row,
  .item-meta {
    align-items: flex-start;
  }

  .item-badges,
  .item-actions {
    justify-content: flex-start;
  }

  .item-meta {
    margin-left: 0;
    gap: 10px;
  }
}
</style>
