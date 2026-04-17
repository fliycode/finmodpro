<script setup>
import { computed, ref, watch } from 'vue';

import { createApiConfig } from '../api/config.js';
import { normalizeMemoryItems } from '../lib/chat-memory.js';

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  datasetId: {
    type: [String, Number],
    default: null,
  },
});

const emit = defineEmits(['update:open']);

const api = createApiConfig();
const items = ref([]);
const isLoading = ref(false);
const loadError = ref('');
const actionError = ref('');
const activeActionId = ref(null);
const activeActionKind = ref('');
const evidencePreview = ref(null);
const refreshRequestId = ref(0);
const lastRefreshHadSuccess = ref(false);

const drawerOpen = computed({
  get() {
    return props.open;
  },
  set(value) {
    emit('update:open', value);
  },
});

const hasDatasetScope = computed(() =>
  props.datasetId !== '' && props.datasetId !== null && props.datasetId !== undefined,
);

const scopeSummary = computed(() =>
  hasDatasetScope.value ? `全局记忆 + 数据集 ${props.datasetId}` : '仅全局记忆',
);
const scopeFootnote = computed(() =>
  hasDatasetScope.value
    ? '范围会跟随当前问答会话的数据集过滤自动切换。'
    : '当前问答未限制数据集，因此这里只展示全局记忆范围。',
);

const clearTransientState = () => {
  loadError.value = '';
  actionError.value = '';
  activeActionId.value = null;
  activeActionKind.value = '';
  evidencePreview.value = null;
};

const sortedItems = computed(() =>
  [...items.value].sort((left, right) => {
    if (left.pinned !== right.pinned) {
      return left.pinned ? -1 : 1;
    }

    const leftTime = Date.parse(left.updatedAt || '') || 0;
    const rightTime = Date.parse(right.updatedAt || '') || 0;
    if (leftTime !== rightTime) {
      return rightTime - leftTime;
    }

    return String(left.title || '').localeCompare(String(right.title || ''), 'zh-CN');
  }),
);

const memoryGroups = computed(() => {
  const pinned = sortedItems.value.filter((item) => item.pinned);
  const recent = sortedItems.value.filter((item) => !item.pinned);
  const groups = [];

  if (pinned.length > 0) {
    groups.push({ id: 'pinned', title: '置顶记忆', items: pinned });
  }

  if (recent.length > 0) {
    groups.push({
      id: 'recent',
      title: pinned.length > 0 ? '最近记忆' : '全部记忆',
      items: recent,
    });
  }

  return groups;
});

const loadErrorBlocksState = computed(() =>
  Boolean(loadError.value) && !sortedItems.value.length && !lastRefreshHadSuccess.value,
);

const normalizeMemoryResponse = (payload) =>
  normalizeMemoryItems(payload?.data?.memories ?? payload?.memories ?? []);

const mergeMemoryItems = (groups) => {
  const merged = new Map();

  groups.flat().forEach((item) => {
    const key = item?.id === null || item?.id === undefined ? `${item.title}-${item.updatedAt}` : String(item.id);
    if (!merged.has(key)) {
      merged.set(key, item);
    }
  });

  return Array.from(merged.values());
};

const formatDateTime = (value) => {
  if (!value) {
    return '时间未知';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const getConfirmationLabel = (status) => {
  if (status === 'confirmed') {
    return '已确认';
  }

  if (status === 'rejected') {
    return '已拒绝';
  }

  return '待确认';
};

const fetchMemoryGroup = async (scopeType, scopeKey = '') => {
  const params = new URLSearchParams({ scope_type: scopeType });
  if (scopeKey) {
    params.set('scope_key', scopeKey);
  }

  const payload = await api.fetchJson(`/api/chat/memories?${params.toString()}`, {
    method: 'GET',
    auth: true,
  });

  return normalizeMemoryResponse(payload);
};

const refreshMemories = async () => {
  const requestId = refreshRequestId.value + 1;
  refreshRequestId.value = requestId;
  isLoading.value = true;
  clearTransientState();

  try {
    const scopes = [{ label: '全局', loader: () => fetchMemoryGroup('user_global') }];
    if (hasDatasetScope.value) {
      scopes.push({
        label: `数据集 ${props.datasetId}`,
        loader: () => fetchMemoryGroup('dataset', String(props.datasetId)),
      });
    }

    const results = await Promise.allSettled(scopes.map((scope) => scope.loader()));
    if (requestId !== refreshRequestId.value || !props.open) {
      return;
    }

    const succeededLabels = [];
    const failedLabels = [];
    const succeededItems = [];

    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        succeededLabels.push(scopes[index].label);
        succeededItems.push(result.value);
        return;
      }

      failedLabels.push(scopes[index].label);
    });

    lastRefreshHadSuccess.value = succeededItems.length > 0;

    if (succeededItems.length > 0) {
      items.value = mergeMemoryItems(succeededItems);
      actionError.value = '';
    }

    if (failedLabels.length > 0) {
      loadError.value = succeededLabels.length > 0
        ? `部分记忆加载失败，当前仅显示${succeededLabels.join('、')}范围。`
        : failedLabels.length === 1
          ? `${failedLabels[0]}范围记忆加载失败，请稍后重试。`
          : '全局和数据集范围记忆都加载失败，请稍后重试。';
    }

    if (
      succeededItems.length > 0 &&
      evidencePreview.value &&
      !items.value.some((item) => String(item.id) === String(evidencePreview.value.memoryId))
    ) {
      evidencePreview.value = null;
    }
  } catch (error) {
    if (requestId !== refreshRequestId.value || !props.open) {
      return;
    }

    lastRefreshHadSuccess.value = false;
    loadError.value = String(error?.message || '加载记忆失败，请稍后重试。');
  } finally {
    if (requestId === refreshRequestId.value) {
      isLoading.value = false;
    }
  }
};

const setActiveAction = (itemId, kind) => {
  activeActionId.value = itemId;
  activeActionKind.value = kind;
  actionError.value = '';
};

const clearActiveAction = () => {
  activeActionId.value = null;
  activeActionKind.value = '';
};

const isItemBusy = (itemId, kind = '') =>
  String(activeActionId.value) === String(itemId) && (!kind || activeActionKind.value === kind);

const replaceMemoryItem = (memory) => {
  if (!memory || memory.id === null || memory.id === undefined) {
    return;
  }

  const next = items.value.map((item) => (String(item.id) === String(memory.id) ? memory : item));
  items.value = mergeMemoryItems([next]);
};

const handleTogglePin = async (item) => {
  if (!item?.id) {
    return;
  }

  setActiveAction(item.id, 'pin');
  try {
    const payload = await api.fetchJson(`/api/chat/memories/${item.id}/pin`, {
      method: 'POST',
      auth: true,
      body: JSON.stringify({ pinned: !item.pinned }),
    });
    const updated = normalizeMemoryItems([payload?.data?.memory ?? payload?.memory ?? null]).filter(Boolean)[0];
    replaceMemoryItem(updated);
  } catch (error) {
    actionError.value = String(error?.message || '更新置顶状态失败，请稍后重试。');
  } finally {
    clearActiveAction();
  }
};

const handleDelete = async (item) => {
  if (!item?.id) {
    return;
  }

  if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
    const confirmed = window.confirm(`确定删除“${item.title || '未命名记忆'}”吗？`);
    if (!confirmed) {
      return;
    }
  }

  setActiveAction(item.id, 'delete');
  try {
    await api.fetchJson(`/api/chat/memories/${item.id}`, {
      method: 'DELETE',
      auth: true,
    });
    items.value = items.value.filter((entry) => String(entry.id) !== String(item.id));
    if (String(evidencePreview.value?.memoryId || '') === String(item.id)) {
      evidencePreview.value = null;
    }
  } catch (error) {
    actionError.value = String(error?.message || '删除记忆失败，请稍后重试。');
  } finally {
    clearActiveAction();
  }
};

const handleOpenEvidence = async (item) => {
  if (!item?.id) {
    return;
  }

  setActiveAction(item.id, 'evidence');
  try {
    const payload = await api.fetchJson(`/api/chat/memories/${item.id}/evidence`, {
      method: 'GET',
      auth: true,
    });
    const evidence = Array.isArray(payload?.data?.evidence ?? payload?.evidence)
      ? (payload?.data?.evidence ?? payload?.evidence)
      : [];

    evidencePreview.value = {
      memoryId: item.id,
      title: payload?.data?.memory?.title ?? item.title ?? '未命名记忆',
      items: evidence.slice(0, 3).map((entry, index) => ({
        id: entry?.id ?? `${item.id}-${index}`,
        excerpt: entry?.evidence_excerpt || item.content || '暂无证据片段。',
        statusLabel: getConfirmationLabel(entry?.confirmation_status),
        sessionId: entry?.session_id ?? null,
        messageId: entry?.message_id ?? null,
        createdAt: formatDateTime(entry?.created_at),
      })),
    };
  } catch (error) {
    actionError.value = String(error?.message || '加载证据失败，请稍后重试。');
  } finally {
    clearActiveAction();
  }
};

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      await refreshMemories();
      return;
    }

    refreshRequestId.value += 1;
    isLoading.value = false;
    clearTransientState();
  },
);

watch(
  () => props.datasetId,
  async (nextValue, previousValue) => {
    if (!props.open || nextValue === previousValue) {
      return;
    }

    clearTransientState();
    await refreshMemories();
  },
);
</script>

<template>
  <el-drawer
    v-model="drawerOpen"
    direction="rtl"
    size="400px"
    :with-header="false"
    class="qa-memory-drawer"
  >
    <div class="memory-shell">
      <div class="memory-shell__toolbar">
        <div>
          <span class="memory-shell__eyebrow">长期记忆</span>
          <p class="memory-shell__subtitle">查看当前问答可命中的用户记忆，并在这里做轻量治理。</p>
        </div>
        <button class="refresh-btn" type="button" @click="refreshMemories" :disabled="isLoading">
          刷新
        </button>
      </div>

      <div class="memory-shell__meta">
        <span>范围：{{ scopeSummary }}</span>
        <span>共 {{ sortedItems.length }} 条</span>
      </div>
      <p class="memory-shell__scope-note">{{ scopeFootnote }}</p>

      <div v-if="actionError" class="state-msg state-msg--error">
        {{ actionError }}
      </div>

      <div v-if="loadError && !loadErrorBlocksState" class="state-msg state-msg--error">
        {{ loadError }}
      </div>

      <section v-if="evidencePreview" class="evidence-card">
        <div class="evidence-card__header">
          <div>
            <span class="evidence-card__eyebrow">记忆证据</span>
            <h3>{{ evidencePreview.title }}</h3>
          </div>
          <button class="refresh-btn" type="button" @click="evidencePreview = null">收起</button>
        </div>

        <div v-if="evidencePreview.items.length === 0" class="evidence-card__empty">
          暂无更多证据，当前先展示记忆本身内容。
        </div>
        <div v-else class="evidence-list">
          <article
            v-for="entry in evidencePreview.items"
            :key="entry.id"
            class="evidence-item"
          >
            <div class="evidence-item__meta">
              <span>{{ entry.statusLabel }}</span>
              <span>{{ entry.createdAt }}</span>
              <span v-if="entry.sessionId">会话 {{ entry.sessionId }}</span>
              <span v-if="entry.messageId">消息 {{ entry.messageId }}</span>
            </div>
            <p>{{ entry.excerpt }}</p>
          </article>
        </div>
      </section>

      <div v-if="isLoading" class="skeleton-list">
        <div v-for="n in 4" :key="n" class="skeleton-item">
          <div class="skeleton-pill" />
          <div class="skeleton-title" />
          <div class="skeleton-copy" />
          <div class="skeleton-copy skeleton-copy--short" />
        </div>
      </div>

      <div v-else-if="loadErrorBlocksState" class="state-msg state-msg--error">
        <div class="state-msg__stack">
          <div>{{ loadError }}</div>
          <button class="refresh-btn" type="button" @click="refreshMemories">重试</button>
        </div>
      </div>

      <div v-else-if="sortedItems.length === 0" class="state-msg">
        <div class="state-msg__stack">
          <div>暂无长期记忆</div>
          <div class="state-msg__footnote">后端提取到稳定偏好或工作规则后，会出现在这里。</div>
        </div>
      </div>

      <div v-else class="memory-groups">
        <section v-for="group in memoryGroups" :key="group.id" class="memory-group">
          <div class="memory-group__title">{{ group.title }}</div>
          <article v-for="item in group.items" :key="item.id" class="memory-item">
            <div class="memory-item__header">
              <div class="memory-item__title-row">
                <h3>{{ item.title }}</h3>
                <span v-if="item.pinned" class="memory-badge memory-badge--pinned">置顶</span>
              </div>
              <div class="memory-item__meta">
                <span class="memory-badge">{{ item.memoryTypeLabel }}</span>
                <span class="memory-badge">{{ item.scopeLabel }}</span>
                <span class="memory-badge">{{ item.sourceLabel }}</span>
              </div>
            </div>

            <p class="memory-item__content">{{ item.content }}</p>

            <div class="memory-item__footer">
              <span class="memory-item__time">更新于 {{ formatDateTime(item.updatedAt) }}</span>
              <div class="memory-item__actions">
                <button
                  class="memory-action"
                  type="button"
                  :disabled="isItemBusy(item.id)"
                  @click="handleOpenEvidence(item)"
                >
                  {{ isItemBusy(item.id, 'evidence') ? '加载中...' : '证据' }}
                </button>
                <button
                  class="memory-action"
                  type="button"
                  :disabled="isItemBusy(item.id)"
                  @click="handleTogglePin(item)"
                >
                  {{ isItemBusy(item.id, 'pin') ? '处理中...' : item.pinned ? '取消置顶' : '置顶' }}
                </button>
                <button
                  class="memory-action memory-action--danger"
                  type="button"
                  :disabled="isItemBusy(item.id)"
                  @click="handleDelete(item)"
                >
                  {{ isItemBusy(item.id, 'delete') ? '删除中...' : '删除' }}
                </button>
              </div>
            </div>
          </article>
        </section>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.memory-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.memory-shell__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.memory-shell__eyebrow,
.evidence-card__eyebrow {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.memory-shell__subtitle {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.memory-shell__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 12px;
}

.memory-shell__scope-note {
  margin: -8px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.refresh-btn,
.memory-action {
  padding: 8px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.memory-action {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
}

.memory-action--danger {
  color: #b42318;
  border-color: rgba(180, 35, 24, 0.18);
  background: rgba(254, 242, 242, 0.9);
}

.refresh-btn:disabled,
.memory-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.state-msg {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border: 1px dashed var(--line-strong);
  border-radius: 16px;
  background: var(--surface-3);
  font-size: 14px;
  padding: 18px;
}

.state-msg--error {
  min-height: auto;
  justify-content: flex-start;
  border-style: solid;
  border-color: rgba(180, 35, 24, 0.14);
  color: #8a1c16;
  background: #fff7f7;
}

.state-msg__stack {
  text-align: center;
}

.state-msg__footnote {
  font-size: 12px;
  margin-top: 8px;
  color: #9aa5b5;
}

.evidence-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid rgba(36, 87, 197, 0.12);
  box-shadow: 0 18px 36px -28px rgba(36, 87, 197, 0.28);
}

.evidence-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.evidence-card__header h3 {
  margin: 6px 0 0;
  font-size: 16px;
  color: var(--text-primary);
}

.evidence-card__empty {
  color: var(--text-secondary);
  font-size: 13px;
}

.evidence-list,
.memory-groups,
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-item,
.memory-item,
.skeleton-item {
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--line-soft);
}

.evidence-item {
  padding: 12px 14px;
}

.evidence-item__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 8px;
}

.evidence-item p {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.memory-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.memory-group__title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.memory-item {
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.memory-item__title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.memory-item__title-row h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text-primary);
}

.memory-item__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.memory-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.memory-badge--pinned {
  background: rgba(36, 87, 197, 0.12);
  color: #1d4ed8;
}

.memory-item__content {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.memory-item__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.memory-item__time {
  color: var(--text-muted);
  font-size: 12px;
}

.memory-item__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.skeleton-item {
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-pill,
.skeleton-title,
.skeleton-copy {
  border-radius: 999px;
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-pill {
  width: 92px;
  height: 24px;
  background: #e2e8f0;
}

.skeleton-title {
  width: 50%;
  height: 18px;
  border-radius: 6px;
  background: #cbd5e1;
}

.skeleton-copy {
  width: 100%;
  height: 12px;
  border-radius: 6px;
  background: #f1f5f9;
}

.skeleton-copy--short {
  width: 68%;
}

:deep(.qa-memory-drawer .el-drawer__body) {
  padding: 18px;
  background: #f7f9fb;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.45; }
  100% { opacity: 1; }
}

@media (max-width: 720px) {
  .memory-item__footer,
  .evidence-card__header,
  .memory-shell__toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
