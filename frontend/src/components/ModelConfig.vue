<script setup>
import { ref, onMounted, computed } from "vue";
import { llmApi } from "../api/llm.js";

const configs = ref([]);
const isLoading = ref(false);
const errorMsg = ref("");

const normalizeConfigs = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.model_configs)) return payload.model_configs;
  return [];
};

const fetchConfigs = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getModelConfigs();
    configs.value = normalizeConfigs(data);
  } catch (error) {
    console.error("Failed to fetch model configs:", error);
    errorMsg.value = error.message || "加载模型配置失败";
    configs.value = [];
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchConfigs);

const toggleActivation = async (config) => {
  try {
    const newStatus = !config.is_active;
    await llmApi.activateModelConfig(config.id, newStatus);
    await fetchConfigs(); // Refresh list after successful toggle
  } catch (error) {
    alert(error.message || "操作失败");
  }
};

const chatConfigs = computed(() => configs.value.filter(c => c.capability === "chat"));
const embeddingConfigs = computed(() => configs.value.filter(c => c.capability === "embedding"));

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch (e) {
    return dateStr;
  }
};
</script>

<template>
  <div class="model-config-shell">
    <div class="header">
      <div class="title-group">
        <h3>模型配置管理</h3>
        <span class="badge">管理员模式</span>
      </div>
      <button class="primary-btn" @click="fetchConfigs" :disabled="isLoading">
        {{ isLoading ? "刷新中..." : "刷新配置" }}
      </button>
    </div>

    <div v-if="errorMsg" class="error-state">{{ errorMsg }}</div>

    <div class="config-section">
      <h4>对话模型 (Chat)</h4>
      <p class="section-desc">仅能启用一个对话模型用于问答。启用新模型将自动停用当前启用的模型。</p>
      <div v-if="isLoading && chatConfigs.length === 0" class="loading-state">加载中...</div>
      <div v-else-if="chatConfigs.length === 0" class="empty-state">暂无对话模型配置</div>
      <div v-else class="grid">
        <div v-for="item in chatConfigs" :key="item.id" class="config-card" :class="{ active: item.is_active }">
          <div class="card-header">
            <span class="provider-badge">{{ item.provider }}</span>
            <span v-if="item.is_active" class="status-badge active">● 已启用</span>
            <span v-else class="status-badge inactive">○ 未启用</span>
          </div>
          <div class="card-body">
            <div class="config-name">{{ item.name }}</div>
            <div class="model-name">模型: {{ item.model_name }}</div>
            <div class="endpoint">API: {{ item.endpoint || "默认" }}</div>
            <div class="updated-at">更新时间: {{ formatDate(item.updated_at) }}</div>
          </div>
          <div class="card-footer">
            <button class="toggle-btn" :class="{ 'btn-deactivate': item.is_active, 'btn-activate': !item.is_active }" @click="toggleActivation(item)">
              {{ item.is_active ? "停用" : "启用" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="config-section">
      <h4>向量模型 (Embedding)</h4>
      <p class="section-desc">仅能启用一个向量模型用于知识库处理。启用新模型将自动停用当前启用的模型。</p>
      <div v-if="isLoading && embeddingConfigs.length === 0" class="loading-state">加载中...</div>
      <div v-else-if="embeddingConfigs.length === 0" class="empty-state">暂无向量模型配置</div>
      <div v-else class="grid">
        <div v-for="item in embeddingConfigs" :key="item.id" class="config-card" :class="{ active: item.is_active }">
          <div class="card-header">
            <span class="provider-badge">{{ item.provider }}</span>
            <span v-if="item.is_active" class="status-badge active">● 已启用</span>
            <span v-else class="status-badge inactive">○ 未启用</span>
          </div>
          <div class="card-body">
            <div class="config-name">{{ item.name }}</div>
            <div class="model-name">模型: {{ item.model_name }}</div>
            <div class="endpoint">API: {{ item.endpoint || "默认" }}</div>
            <div class="updated-at">更新时间: {{ formatDate(item.updated_at) }}</div>
          </div>
          <div class="card-footer">
            <button class="toggle-btn" :class="{ 'btn-deactivate': item.is_active, 'btn-activate': !item.is_active }" @click="toggleActivation(item)">
              {{ item.is_active ? "停用" : "启用" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-config-shell { display: flex; flex-direction: column; gap: 24px; }
.header { display: flex; align-items: center; justify-content: space-between; }
.title-group { display: flex; align-items: center; gap: 12px; }
.header h3 { margin: 0; color: #1e293b; }
.badge { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.primary-btn { padding: 8px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
.primary-btn:hover { background: #f8fafc; border-color: #cbd5e1; }

.error-state { padding: 12px; background: #fef2f2; color: #ef4444; border-radius: 8px; font-size: 14px; text-align: center; border: 1px solid #fca5a5; }

.config-section { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.config-section h4 { margin: 0 0 8px 0; color: #1e293b; font-size: 16px; }
.section-desc { color: #64748b; font-size: 13px; margin: 0 0 20px 0; }

.loading-state, .empty-state { text-align: center; padding: 32px; color: #64748b; font-size: 14px; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }

.config-card { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background: white; transition: all 0.2s; display: flex; flex-direction: column; }
.config-card.active { border-color: #6366f1; box-shadow: 0 0 0 1px #6366f1; }
.config-card:hover { box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }

.card-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.config-card.active .card-header { background: #eef2ff; border-bottom-color: #c7d2fe; }

.provider-badge { font-size: 11px; font-weight: 600; color: #475569; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; }
.status-badge { font-size: 12px; font-weight: 600; }
.status-badge.active { color: #10b981; }
.status-badge.inactive { color: #94a3b8; }

.card-body { padding: 16px; flex: 1; display: flex; flex-direction: column; gap: 8px; }
.config-name { font-size: 16px; font-weight: 600; color: #1e293b; margin-bottom: 4px; }
.model-name { font-size: 14px; color: #334155; }
.endpoint { font-size: 13px; color: #64748b; word-break: break-all; font-family: monospace; background: #f1f5f9; padding: 4px 8px; border-radius: 4px; }
.updated-at { font-size: 12px; color: #94a3b8; margin-top: auto; padding-top: 8px; }

.card-footer { padding: 12px 16px; border-top: 1px solid #e2e8f0; display: flex; justify-content: flex-end; background: #fafafa; }
.toggle-btn { padding: 6px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; }
.btn-activate { background: #6366f1; color: white; }
.btn-activate:hover { background: #4f46e5; }
.btn-deactivate { background: white; color: #ef4444; border: 1px solid #fecaca; }
.btn-deactivate:hover { background: #fef2f2; }
</style>
