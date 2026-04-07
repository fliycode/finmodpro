<script setup>
import { onMounted, ref } from 'vue';

import { chatApi } from '../api/chat.js';

const emit = defineEmits(['open-session']);

const history = ref([]);
const isLoading = ref(false);

const fetchHistory = async () => {
  isLoading.value = true;
  try {
    history.value = await chatApi.listHistory();
  } catch (error) {
    console.error('Failed to fetch history:', error);
  } finally {
    isLoading.value = false;
  }
};

const handleOpenSession = (id) => {
  emit('open-session', id);
};

onMounted(fetchHistory);
</script>

<template>
  <div class="history-shell">
    <div class="history-shell__toolbar">
      <span class="history-shell__eyebrow">会话记录</span>
      <button class="refresh-btn" @click="fetchHistory" :disabled="isLoading">刷新</button>
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
    <div v-else-if="history.length === 0" class="state-msg empty">
      <div class="state-msg__stack">
        <div>暂无历史记录</div>
        <div class="state-msg__footnote">(后端仍需实现 `GET /api/chat/sessions` 的完整返回)</div>
      </div>
    </div>
    <div v-else class="history-list">
      <div v-for="item in history" :key="item.id" class="history-item" @click="handleOpenSession(item.id)">
        <div class="item-main">
          <div class="item-title">{{ item.title }}</div>
          <div class="item-preview">{{ item.lastMessage }}</div>
        </div>
        <div class="item-meta">
          <div class="item-time">{{ item.timestamp }}</div>
          <button class="view-btn">继续对话</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-shell {
  background: #fff;
  border-radius: 20px;
  padding: 24px;
  box-shadow: var(--shadow-soft);
  border: 1px solid var(--line-soft);
  min-height: 500px;
  display: flex;
  flex-direction: column;
}

.history-shell__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.history-shell__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.refresh-btn {
  padding: 8px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--surface-3);
  border-color: var(--line-strong);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.state-msg {
  flex: 1;
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
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: #fff;
}

.history-item {
  transition: all 0.2s;
  cursor: pointer;
}

.history-item:hover {
  border-color: rgba(36, 87, 197, 0.18);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 12px 24px -20px rgba(36, 87, 197, 0.18);
  transform: translateY(-1px);
}

.item-main,
.skeleton-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.item-title {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 15px;
}

.item-preview {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.5;
}

.item-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  margin-left: 16px;
  flex-shrink: 0;
}

.item-time {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.view-btn {
  padding: 6px 14px;
  background: var(--surface-3);
  color: var(--brand);
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0;
  transform: translateX(10px);
}

.history-item:hover .view-btn {
  opacity: 1;
  transform: translateX(0);
  background: var(--brand-soft);
}

.view-btn:hover {
  background: var(--brand-soft);
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
  0% {
    opacity: 1;
  }

  50% {
    opacity: 0.5;
  }

  100% {
    opacity: 1;
  }
}
</style>
