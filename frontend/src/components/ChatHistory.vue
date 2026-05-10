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
  currentPage: {
    type: Number,
    default: 1,
  },
  pageSize: {
    type: Number,
    default: 15,
  },
  total: {
    type: Number,
    default: 0,
  },
  totalPages: {
    type: Number,
    default: 1,
  },
});

const emit = defineEmits(['open-session', 'export-session', 'delete-session', 'go-to-page']);

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
    <!-- Loading -->
    <div v-if="isLoading" class="skeleton-list">
      <div v-for="n in 5" :key="n" class="skeleton-item">
        <div class="skeleton-title" />
        <div class="skeleton-preview" />
        <div class="skeleton-meta" />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0 && total === 0" class="history-empty">
      <div class="history-empty__icon">&empty;</div>
      <div class="history-empty__text">暂无历史记录</div>
      <div class="history-empty__hint">新对话创建后会自动出现在这里</div>
    </div>

    <!-- List -->
    <template v-else>
      <div class="history-list">
        <article
          v-for="item in items"
          :key="item.id"
          class="history-item"
          :class="{ 'is-active': String(activeSessionId) === String(item.id) }"
          @click="$emit('open-session', item.id)"
        >
          <div class="item-body">
            <div class="item-title-row">
              <h3 class="item-title">{{ item.title }}</h3>
              <div v-if="showSessionMetadata" class="item-badges">
                <span class="item-badge">{{ getSessionTitleSourceLabel(item.titleSource) }}</span>
                <span v-if="shouldShowTitleStatus(item)" class="item-badge is-warn">
                  {{ getSessionTitleStatusLabel(item.titleStatus) }}
                </span>
                <span v-if="getDatasetLabel(item)" class="item-badge">{{ getDatasetLabel(item) }}</span>
              </div>
            </div>
            <p v-if="showSessionMetadata && shouldShowSummaryPreview(item)" class="item-summary">
              {{ item.summaryPreview }}
            </p>
            <p class="item-preview">{{ item.preview }}</p>
          </div>

          <div class="item-side">
            <time class="item-time">{{ item.timestamp }}</time>
            <span v-if="showSessionMetadata" class="item-count">{{ item.messageCount }} 条</span>
            <div class="item-actions" @click.stop>
              <button type="button" class="item-action-btn is-primary" @click="$emit('open-session', item.id)">继续对话</button>
              <button v-if="enableExport" type="button" class="item-action-btn" @click="$emit('export-session', item.id)">导出</button>
              <button type="button" class="item-action-btn is-danger" @click="$emit('delete-session', item.id)">删除</button>
            </div>
          </div>
        </article>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="history-pagination">
        <span class="history-pagination__info">{{ total }} 条记录</span>
        <div class="history-pagination__controls">
          <button
            class="history-pagination__btn"
            :disabled="currentPage <= 1"
            @click="$emit('go-to-page', currentPage - 1)"
            aria-label="上一页"
          >&lsaquo;</button>
          <template v-for="page in totalPages" :key="page">
            <button
              v-if="page === 1 || page === totalPages || (page >= currentPage - 1 && page <= currentPage + 1)"
              class="history-pagination__btn"
              :class="{ 'is-active': page === currentPage }"
              @click="$emit('go-to-page', page)"
            >{{ page }}</button>
            <span
              v-else-if="page === currentPage - 2 || page === currentPage + 2"
              class="history-pagination__ellipsis"
            >&hellip;</span>
          </template>
          <button
            class="history-pagination__btn"
            :disabled="currentPage >= totalPages"
            @click="$emit('go-to-page', currentPage + 1)"
            aria-label="下一页"
          >&rsaquo;</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.history-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---- Empty State ---- */

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 48px 16px;
  color: var(--text-muted);
}

.history-empty__icon {
  font-size: 28px;
  opacity: 0.4;
  margin-bottom: 4px;
}

.history-empty__text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.history-empty__hint {
  font-size: 12px;
}

/* ---- List ---- */

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.history-item:hover {
  border-color: rgba(36, 87, 197, 0.2);
  background: var(--surface-hover);
}

.history-item.is-active {
  border-color: rgba(36, 87, 197, 0.3);
  background: var(--brand-soft, rgba(36, 87, 197, 0.06));
}

/* ---- Item Body ---- */

.item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.item-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-badges {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  justify-content: flex-end;
  flex-shrink: 0;
}

.item-badge {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.item-badge.is-warn {
  background: rgba(183, 121, 31, 0.1);
  color: var(--warning-amber, #b7791f);
}

.item-summary {
  margin: 0;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
}

.item-preview {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- Item Side ---- */

.item-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  flex-shrink: 0;
  gap: 8px;
}

.item-time {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.item-count {
  font-size: 11px;
  color: var(--text-secondary);
}

.item-actions {
  display: flex;
  gap: 6px;
}

.item-action-btn {
  padding: 4px 10px;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.item-action-btn:hover {
  border-color: var(--line-strong);
  color: var(--text-primary);
}

.item-action-btn.is-primary {
  border-color: rgba(36, 87, 197, 0.2);
  color: var(--brand, #2457c5);
}

.item-action-btn.is-primary:hover {
  border-color: rgba(36, 87, 197, 0.4);
}

.item-action-btn.is-danger {
  color: var(--risk-red, #c4493d);
}

.item-action-btn.is-danger:hover {
  border-color: rgba(196, 73, 61, 0.3);
  background: rgba(196, 73, 61, 0.06);
}

/* ---- Pagination ---- */

.history-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}

.history-pagination__info {
  font-size: 11px;
  color: var(--text-muted);
}

.history-pagination__controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.history-pagination__btn {
  min-width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  padding: 0 4px;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.history-pagination__btn:hover:not(:disabled):not(.is-active) {
  border-color: var(--line-strong);
  color: var(--text-primary);
}

.history-pagination__btn.is-active {
  border-color: var(--brand, #2457c5);
  color: var(--brand, #2457c5);
  background: var(--brand-soft, rgba(36, 87, 197, 0.06));
}

.history-pagination__btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.history-pagination__ellipsis {
  width: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- Skeleton ---- */

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-item {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-title,
.skeleton-preview,
.skeleton-meta {
  border-radius: 4px;
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-title {
  height: 14px;
  width: 35%;
  background: var(--surface-3);
}

.skeleton-preview {
  height: 12px;
  width: 65%;
  background: var(--surface-3);
}

.skeleton-meta {
  height: 12px;
  width: 80px;
  background: var(--surface-3);
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}

/* ---- Responsive ---- */

@media (max-width: 760px) {
  .history-item {
    flex-direction: column;
    gap: 10px;
  }

  .item-title-row {
    flex-direction: column;
    gap: 6px;
  }

  .item-badges {
    justify-content: flex-start;
  }

  .item-side {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .item-actions {
    flex-wrap: wrap;
  }
}
</style>
