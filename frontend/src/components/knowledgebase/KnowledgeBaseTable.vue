<script setup>
import AppIcon from '../ui/AppIcon.vue';

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  checkedIds: {
    type: Array,
    default: () => [],
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
  'navigate',
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

const showReingest = (item) => {
  const code = item.processStep?.code || '';
  return code !== 'indexing' && code !== 'parsing' && code !== 'cleaning' && code !== 'chunking' && code !== 'queued';
};
</script>

<template>
  <div class="kb-table">
    <div class="kb-table__header">
      <label class="kb-checkbox" @click.stop>
        <input
          type="checkbox"
          :checked="isAllChecked()"
          aria-label="全选当前页文档"
          @change="emit('toggle-all')"
        />
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

    <div
      v-for="item in items"
      :key="item.id"
      class="kb-table__row"
      role="button"
      tabindex="0"
      :aria-label="`打开文档详情：${item.title}`"
      @click="emit('navigate', item)"
      @keydown.enter.self.prevent="emit('navigate', item)"
      @keydown.space.self.prevent="emit('navigate', item)"
    >
      <label class="kb-checkbox" @click.stop>
        <input
          type="checkbox"
          :checked="checkedIds.includes(item.id)"
          :aria-label="`选择文档：${item.title}`"
          @change="emit('toggle-row', item.id)"
        />
      </label>

      <div class="kb-table__title">
        <strong :title="item.title">{{ item.title }}</strong>
        <span class="kb-table__filename" :title="item.filename">{{ item.filename }}</span>
        <span class="kb-table__meta">
          {{ item.uploaderName }}&nbsp;·&nbsp;v{{ item.currentVersion }}
        </span>
      </div>

      <div class="kb-table__cell">
        <span class="kb-table__tag" :title="item.datasetName">{{ item.datasetName }}</span>
      </div>

      <div class="kb-table__cell kb-col-size">{{ item.size }}</div>

      <div class="kb-table__cell kb-col-vector">{{ Number(item.vectorCount || 0).toLocaleString('zh-CN') }}</div>

      <div class="kb-table__cell kb-col-time" :title="item.updateTime">{{ item.updateTime }}</div>

      <div class="kb-table__status kb-col-status">
        <span :class="['kb-status-dot', `tone-${item.statusTone || 'neutral'}`]"></span>
        <div class="kb-table__status-copy">
          <span>{{ item.processStep.label }}</span>
          <small>{{ item.processStep.detail || '等待进一步处理。' }}</small>
        </div>
      </div>

      <div class="kb-table__actions">
        <button
          type="button"
          class="kb-icon-btn"
          title="查看详情"
          :aria-label="`查看${item.title}的详情`"
          @click.stop="emit('row-action', { item, action: 'view-detail' })"
        >
          <AppIcon name="eye" :width="15" :height="15" />
        </button>
        <button
          v-if="showReingest(item)"
          type="button"
          class="kb-icon-btn"
          title="重新入库"
          :aria-label="`重新入库${item.title}`"
          @click.stop="emit('row-action', { item, action: 'reingest' })"
        >
          <AppIcon name="refresh" :width="15" :height="15" />
        </button>
        <button
          type="button"
          class="kb-icon-btn kb-icon-btn--danger"
          title="删除"
          :aria-label="`删除${item.title}`"
          @click.stop="emit('row-action', { item, action: 'delete' })"
        >
          <AppIcon name="trash" :width="15" :height="15" />
        </button>
      </div>
    </div>

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
  overflow-x: auto;
  background: transparent;
}

.kb-table__header,
.kb-table__row {
  display: grid;
  grid-template-columns: 44px minmax(200px, 1fr) 112px 88px 96px 116px 152px 132px;
  gap: 10px;
  align-items: center;
  padding: 12px 18px;
}

.kb-table__header {
  border-bottom: 1px solid var(--line-soft);
  background: color-mix(in oklab, var(--brand) 4%, var(--surface-3));
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.kb-table__row {
  width: 100%;
  border-bottom: 1px solid var(--line-soft);
  background: transparent;
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.kb-table__row:hover,
.kb-table__row:focus-visible {
  background: color-mix(in srgb, var(--brand-soft) 40%, transparent);
  outline: none;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--brand) 20%, transparent);
}

.kb-checkbox {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 40px;
  min-height: 40px;
}

.kb-checkbox input {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  margin: 0;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in oklab, var(--brand) 18%, var(--line-strong));
  border-radius: 6px;
  background: color-mix(in oklab, var(--brand) 3%, var(--surface-2));
  cursor: pointer;
  transition: border-color 0.14s ease, background 0.14s ease, box-shadow 0.14s ease;
}

.kb-checkbox input::before {
  content: '';
  width: 4px;
  height: 8px;
  border-right: 2px solid var(--text-inverse);
  border-bottom: 2px solid var(--text-inverse);
  transform: rotate(45deg) scale(0);
  transition: transform 0.12s ease;
}

.kb-checkbox input:hover {
  border-color: color-mix(in oklab, var(--brand) 42%, var(--line-strong));
  background: color-mix(in oklab, var(--brand) 8%, var(--surface-2));
}

.kb-checkbox input:checked {
  border-color: var(--brand);
  background: var(--brand);
}

.kb-checkbox input:checked::before {
  transform: rotate(45deg) scale(1);
}

.kb-checkbox input:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--brand) 48%, transparent);
  outline-offset: 2px;
}

.kb-table__title {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.kb-table__title strong {
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  font-weight: 600;
}

.kb-table__title span,
.kb-table__cell {
  overflow: hidden;
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-col-vector {
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

.kb-table__filename {
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
  font-size: 12px;
}

.kb-table__meta {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted) !important;
}

.kb-table__tag {
  display: inline-flex;
  max-width: 100%;
  padding: 3px 7px;
  border-radius: 6px;
  background: color-mix(in oklab, var(--brand) 4%, var(--surface-3));
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__status {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}

.kb-status-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--text-muted);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--text-muted) 14%, transparent);
}

.kb-status-dot.tone-accent {
  background: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}

.kb-status-dot.tone-success {
  background: var(--success);
  box-shadow: 0 0 0 3px var(--success-50);
}

.kb-status-dot.tone-danger {
  background: var(--risk);
  box-shadow: 0 0 0 3px var(--risk-50);
}

.kb-table__status-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.kb-table__status-copy span {
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 600;
}

.kb-table__status-copy small {
  overflow: hidden;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-table__actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.kb-icon-btn {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}

.kb-icon-btn:hover {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: color-mix(in srgb, var(--brand) 18%, var(--line-soft));
}

.kb-icon-btn--danger:hover {
  background: rgba(181, 58, 58, 0.1);
  color: #b53a3a;
}

.kb-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--line-soft);
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
}

.kb-pagination__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-secondary-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.kb-empty {
  display: grid;
  place-items: center;
  min-height: 140px;
  padding: 28px 20px;
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  text-align: center;
}

@media (max-width: 1160px) {
  .kb-table__header,
  .kb-table__row {
    grid-template-columns: 44px minmax(180px, 1fr) 112px 96px 116px 132px;
  }

  .kb-col-size,
  .kb-col-vector,
  .kb-table__status-copy small {
    display: none;
  }
}

@media (max-width: 900px) {
  .kb-table__header,
  .kb-table__row {
    grid-template-columns: 44px minmax(160px, 1fr) 112px 132px;
  }

  .kb-col-time,
  .kb-col-status {
    display: none;
  }
}

@media (max-width: 600px) {
  .kb-table__header,
  .kb-table__row {
    grid-template-columns: 44px minmax(150px, 1fr) 132px;
  }

  .kb-col-vector,
  .kb-col-time,
  .kb-col-size {
    display: none;
  }
}
</style>
