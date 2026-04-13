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
      <span>文档</span>
      <span>上传者</span>
      <span>当前状态</span>
      <span>上传时间</span>
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
          {{ item.datasetName }} · v{{ item.currentVersion }}
        </span>
      </div>

      <div class="kb-table__cell">{{ item.uploaderName }}</div>

      <div class="kb-table__status">
        <span :class="['status-chip', `tone-${item.statusTone || 'neutral'}`]">
          {{ item.processStep.label }}
        </span>
      </div>

      <div class="kb-table__cell">{{ item.uploadTime }}</div>

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
  background: #fff;
}

.kb-table__header,
.kb-table__row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1.8fr) 120px 120px 140px 140px;
  gap: 12px;
  align-items: center;
  padding: 13px 18px;
}

.kb-table__header {
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  background: #f7f9fc;
  color: #6b7b93;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.kb-table__row {
  width: 100%;
  border: none;
  border-bottom: 1px solid rgba(20, 32, 51, 0.06);
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.kb-table__row:hover,
.kb-table__row.active {
  background: #f4f7fb;
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
  color: #142033;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__title span,
.kb-table__cell {
  overflow: hidden;
  color: #5a677d;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__meta {
  font-size: 12px;
}

.kb-table__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kb-link-btn,
.kb-secondary-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  border-radius: 12px;
  background: #fff;
  color: #142033;
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
}

.kb-pagination__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-empty {
  padding: 32px 24px;
  color: #5a677d;
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
    grid-template-columns: 36px minmax(0, 1.6fr) 110px 110px 120px;
  }

  .kb-table__actions {
    grid-column: 2 / -1;
  }
}
</style>
