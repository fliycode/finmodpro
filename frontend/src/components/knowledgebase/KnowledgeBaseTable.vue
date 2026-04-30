<script setup>
const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  checkedIds: {
    type: Array,
    default: () => [],
  },
  selectedDocumentId: {
    type: [String, Number],
    default: '',
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  page: {
    type: Number,
    default: 1,
  },
  totalPages: {
    type: Number,
    default: 0,
  },
  total: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits([
  'select',
  'toggle-row',
  'toggle-all',
  'row-action',
  'change-page',
]);

const isAllChecked = () => {
  if (!Array.isArray(props.items) || props.items.length === 0) {
    return false;
  }
  return props.items.every((item) => props.checkedIds.includes(item.id));
};
</script>

<template>
  <div class="kb-table ui-card">
    <div class="kb-table__header">
      <label class="kb-checkbox" @click.stop>
        <input type="checkbox" :checked="isAllChecked()" @change="emit('toggle-all')" />
      </label>
      <span>文档名称</span>
      <span>数据集</span>
      <span class="kb-col-size">数据大小</span>
      <span class="kb-col-vector">向量数量</span>
      <span class="kb-col-time">更新时间</span>
      <span class="kb-col-status">状态</span>
      <span>操作</span>
    </div>

    <div v-if="isLoading && items.length === 0" class="kb-empty">正在加载知识库...</div>
    <div v-else-if="items.length === 0" class="kb-empty">当前没有符合条件的文档。</div>

    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      :class="['kb-table__row', { active: item.id === selectedDocumentId }]"
      @click="emit('select', item)"
    >
      <label class="kb-checkbox" @click.stop>
        <input
          type="checkbox"
          :checked="checkedIds.includes(item.id)"
          @change="emit('toggle-row', item.id)"
        />
      </label>

      <div class="kb-table__title">
        <strong>{{ item.title }}</strong>
        <span :title="item.filename">{{ item.filename }}</span>
        <span class="kb-table__meta">
          {{ item.uploaderName }} · v{{ item.currentVersion }}
        </span>
      </div>

      <div class="kb-table__cell">
        <span class="kb-table__tag">{{ item.datasetName }}</span>
      </div>

      <div class="kb-table__cell kb-col-size">{{ item.size }}</div>

      <div class="kb-table__cell kb-col-vector">{{ Number(item.vectorCount || 0).toLocaleString('zh-CN') }}</div>

      <div class="kb-table__cell kb-col-time">{{ item.updateTime }}</div>

      <div class="kb-table__status kb-col-status">
        <span :class="['kb-status-dot', `tone-${item.statusTone || 'neutral'}`]"></span>
        <span>{{ item.processStep.label }}</span>
        <div v-if="!item.processStep.isTerminal" class="kb-inline-progress">
          <span :style="{ width: `${item.processStep.progress}%` }"></span>
        </div>
      </div>

      <div class="kb-table__actions">
        <button
          v-for="action in item.rowActions"
          :key="action.id"
          type="button"
          class="kb-link-btn"
          @click.stop="emit('row-action', { item, action })"
        >
          {{ action.label }}
        </button>
      </div>
    </button>

    <div v-if="totalPages > 1" class="kb-pagination">
      <span>共 {{ total }} 条</span>
      <div class="kb-pagination__controls">
        <button class="kb-secondary-btn" :disabled="page <= 1" @click="emit('change-page', page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="kb-secondary-btn" :disabled="page >= totalPages" @click="emit('change-page', page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-table {
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.kb-table__header,
.kb-table__row {
  display: grid;
  grid-template-columns: 34px minmax(220px, 1.7fr) 132px 96px 120px 136px 136px 118px;
  gap: 12px;
  align-items: center;
  padding: 13px 18px;
}

.kb-table__header {
  border-top: 1px solid var(--line-soft);
  border-bottom: 1px solid var(--line-soft);
  background: var(--surface-3);
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.kb-table__row {
  width: 100%;
  border: none;
  border-bottom: 1px solid var(--line-soft);
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease;
}

.kb-table__row:hover,
.kb-table__row.active {
  background: color-mix(in srgb, var(--brand-soft) 55%, transparent);
}

.kb-checkbox {
  display: flex;
  justify-content: center;
}

.kb-table__title {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.kb-table__title strong {
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__title span,
.kb-table__cell {
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__meta {
  font-size: 12px;
}

.kb-table__tag {
  display: inline-flex;
  max-width: 100%;
  padding: 5px 9px;
  border-radius: 8px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.kb-table__status {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.kb-status-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--text-muted);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--text-muted) 14%, transparent);
}

.kb-status-dot.tone-accent {
  background: var(--brand);
  box-shadow: 0 0 0 4px var(--brand-soft);
}

.kb-status-dot.tone-success {
  background: var(--success);
  box-shadow: 0 0 0 4px var(--success-50);
}

.kb-status-dot.tone-danger {
  background: var(--risk);
  box-shadow: 0 0 0 4px var(--risk-50);
}

.kb-inline-progress {
  width: 52px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-3);
}

.kb-inline-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--brand);
}

.kb-table__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kb-link-btn,
.kb-secondary-btn {
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--text-primary);
  cursor: pointer;
}

.kb-link-btn {
  padding: 6px 10px;
  font-size: 12px;
}

.kb-secondary-btn {
  height: 36px;
  padding: 0 14px;
}

.kb-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  color: var(--text-muted);
}

.kb-pagination__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-empty {
  padding: 32px 24px;
  color: var(--text-secondary);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.tone-neutral {
  background: #eef2f7;
  color: #516176;
}

.tone-accent {
  background: rgba(36, 87, 197, 0.12);
  color: #2457c5;
}

.tone-success {
  background: rgba(35, 138, 86, 0.12);
  color: #238a56;
}

.tone-danger {
  background: rgba(204, 61, 61, 0.12);
  color: #b53a3a;
}

@media (max-width: 1160px) {
  .kb-table__header,
  .kb-table__row {
    grid-template-columns: 34px minmax(220px, 1fr) 132px 96px 120px;
  }

  .kb-col-size,
  .kb-col-vector,
  .kb-col-time,
  .kb-col-status {
    display: none;
  }

  .kb-table__actions {
    grid-column: 2 / -1;
  }
}
</style>
