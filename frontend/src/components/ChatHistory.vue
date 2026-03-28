<script setup>
import { ref, onMounted } from "vue";
import { chatApi } from "../api/chat.js";

const emit = defineEmits(["open-session"]);

const history = ref([]);
const isLoading = ref(false);

const fetchHistory = async () => {
  isLoading.value = true;
  try {
    history.value = await chatApi.listHistory();
  } catch (error) {
    console.error("Failed to fetch history:", error);
  } finally {
    isLoading.value = false;
  }
};

const handleOpenSession = (id) => {
  emit("open-session", id);
};

onMounted(fetchHistory);
</script>

<template>
  <div class="history-shell">
    <div class="header">
      <h3>历史会话记录</h3>
      <button class="refresh-btn" @click="fetchHistory" :disabled="isLoading">刷新</button>
    </div>
    
    <div v-if="isLoading" class="skeleton-list">
      <div v-for="n in 4" :key="n" class="skeleton-item">
        <div class="skeleton-main">
          <div class="skeleton-title"></div>
          <div class="skeleton-preview"></div>
        </div>
        <div class="skeleton-meta"></div>
      </div>
    </div>
    <div v-else-if="history.length === 0" class="state-msg empty">
      <div style="text-align: center;">
        <div>暂无历史记录</div>
        <div style="font-size: 12px; margin-top: 8px; color: #cbd5e1;">(TODO: 后端需要实现 GET /api/chat/sessions)</div>
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
.history-shell { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; min-height: 500px; display: flex; flex-direction: column; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header h3 { margin: 0; color: #1e293b; font-weight: 600; font-size: 18px; }
.refresh-btn { padding: 6px 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; cursor: pointer; font-size: 13px; font-weight: 500; color: #475569; transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.refresh-btn:hover:not(:disabled) { background: #f8fafc; border-color: #cbd5e1; }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.state-msg { flex: 1; display: flex; align-items: center; justify-content: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 12px; background: #f8fafc; font-size: 14px; }

.history-list { display: flex; flex-direction: column; gap: 12px; }
.history-item { display: flex; justify-content: space-between; padding: 16px; border: 1px solid #f1f5f9; border-radius: 12px; transition: all 0.2s; background: #ffffff; cursor: pointer; }
.history-item:hover { border-color: #818cf8; background: #fefeff; box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.1); transform: translateY(-1px); }

.item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.item-title { font-weight: 600; color: #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 15px; }
.item-preview { font-size: 13px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.5; }

.item-meta { display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; margin-left: 16px; flex-shrink: 0; }
.item-time { font-size: 12px; color: #94a3b8; font-weight: 500; }
.view-btn { padding: 6px 14px; background: #f1f5f9; color: #4f46e5; border: none; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.2s; opacity: 0; transform: translateX(10px); }
.history-item:hover .view-btn { opacity: 1; transform: translateX(0); background: #e0e7ff; }
.view-btn:hover { background: #c7d2fe; }

/* Skeleton Loader */
.skeleton-list { display: flex; flex-direction: column; gap: 12px; }
.skeleton-item { display: flex; justify-content: space-between; padding: 16px; border: 1px solid #f1f5f9; border-radius: 12px; background: #ffffff; }
.skeleton-main { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.skeleton-title { height: 18px; width: 40%; background: #e2e8f0; border-radius: 4px; animation: pulse 1.5s infinite ease-in-out; }
.skeleton-preview { height: 14px; width: 70%; background: #f1f5f9; border-radius: 4px; animation: pulse 1.5s infinite ease-in-out; }
.skeleton-meta { height: 14px; width: 60px; background: #f1f5f9; border-radius: 4px; animation: pulse 1.5s infinite ease-in-out; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
</style>