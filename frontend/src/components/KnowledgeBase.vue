<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { kbApi } from "../api/knowledgebase.js";
import { useFlash } from "../lib/flash.js";

const items = ref([]);
const isLoading = ref(false);
const fileInput = ref(null);
const isUploading = ref(false);
const flash = useFlash();

let pollInterval = null;

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    items.value = await kbApi.listDocuments();
  } catch (error) {
    console.error("Failed to fetch documents:", error);
  } finally {
    isLoading.value = false;
  }
};

const triggerUpload = () => {
  fileInput.value.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  
  isUploading.value = true;
  try {
    const res = await kbApi.uploadDocument(file);
    if (res.success && res.document && res.document.id) {
      try {
        await kbApi.ingestDocument(res.document.id);
      } catch (ingestError) {
        console.error("Ingest failed:", ingestError);
        flash.error(`文档已上传，但触发入库失败：${ingestError.message || "未知错误"}`);
      }
    }
    await fetchDocuments();
  } catch (error) {
    console.error("Upload failed:", error);
    flash.error(`上传失败：${error.message || "未知错误"}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    const hasActiveItems = items.value.some(item => 
      ['uploaded', 'parsed', 'chunked'].includes(item.status)
    );
    if (hasActiveItems) {
      const updatedItems = await kbApi.listDocuments();
      items.value = updatedItems;
    }
  }, 2000);
};

onMounted(() => {
  fetchDocuments();
  startPolling();
});

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval);
});

const getStatusColor = (status) => {
  const colors = {
    uploaded: '#3b82f6',
    parsed: '#8b5cf6',
    chunked: '#f59e0b',
    indexed: '#10b981',
    failed: '#ef4444'
  };
  return colors[status] || '#64748b';
};

const getStatusText = (status) => {
  const texts = {
    uploaded: '已上传',
    parsed: '解析中',
    chunked: '切块中',
    indexed: '已索引',
    failed: '处理失败'
  };
  return texts[status] || status;
};
</script>

<template>
  <div class="knowledge-base-shell">
    <div class="toolbar">
      <input type="text" placeholder="搜索知识库文档..." class="search-input" />
      <input type="file" ref="fileInput" style="display: none" @change="handleFileChange" />
      <button class="primary-btn" @click="triggerUpload" :disabled="isUploading">
        <span v-if="isUploading" class="loader-small"></span>
        {{ isUploading ? '上传中...' : '上传文档' }}
      </button>
    </div>
    
    <div class="content-area">
      <div v-if="isLoading && items.length === 0" class="state-msg">加载中...</div>
      
      <div v-else-if="items.length === 0" class="state-msg empty">
        <div class="empty-icon">📁</div>
        <p>暂无文档。请点击上方按钮上传文档。</p>
      </div>
      
      <div v-else class="doc-list">
        <div class="doc-list-header">
          <div class="col-name">文档名称</div>
          <div class="col-status">处理状态</div>
          <div class="col-time">上传时间</div>
          <div class="col-size">大小</div>
        </div>
        <div v-for="item in items" :key="item.id" class="doc-list-item">
          <div class="col-name">
            <svg class="file-icon" viewBox="0 0 24 24" fill="none"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9l-7-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 2v7h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <span class="file-name-text">{{ item.name }}</span>
          </div>
          <div class="col-status">
            <span class="status-badge" :style="{ backgroundColor: getStatusColor(item.status) + '1A', color: getStatusColor(item.status), border: `1px solid ${getStatusColor(item.status)}40` }">
              <span class="status-dot" :style="{ backgroundColor: getStatusColor(item.status) }"></span>
              {{ getStatusText(item.status) }}
            </span>
          </div>
          <div class="col-time">{{ item.uploadTime }}</div>
          <div class="col-size">{{ item.size }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-base-shell { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-height: 500px; display: flex; flex-direction: column; }
.toolbar { display: flex; gap: 16px; margin-bottom: 24px; }
.search-input { flex: 1; padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; outline: none; transition: border-color 0.2s; font-family: inherit; }
.search-input:focus { border-color: #6366f1; }
.primary-btn { padding: 0 24px; height: 42px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: background 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; white-space: nowrap; }
.primary-btn:hover:not(:disabled) { background: #4f46e5; }
.primary-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.loader-small { width: 14px; height: 14px; border: 2px solid #ffffff; border-bottom-color: transparent; border-radius: 50%; display: inline-block; animation: rotation 1s linear infinite; }
@keyframes rotation { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

.content-area { flex: 1; display: flex; flex-direction: column; }
.state-msg { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; text-align: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 8px; background: #f8fafc; }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }

.doc-list { display: flex; flex-direction: column; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.doc-list-header { display: flex; background: #f8fafc; padding: 12px 16px; font-weight: 600; color: #475569; font-size: 13px; border-bottom: 1px solid #e2e8f0; }
.doc-list-item { display: flex; padding: 16px; align-items: center; border-bottom: 1px solid #f1f5f9; transition: background 0.2s; }
.doc-list-item:last-child { border-bottom: none; }
.doc-list-item:hover { background: #f8fafc; }

.col-name { flex: 2; display: flex; align-items: center; gap: 12px; font-weight: 500; color: #1e293b; min-width: 0; }
.file-icon { width: 20px; height: 20px; color: #94a3b8; flex-shrink: 0; }
.file-name-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-status { flex: 1; min-width: 120px; }
.col-time { flex: 1; color: #64748b; font-size: 13px; min-width: 140px; }
.col-size { width: 100px; color: #64748b; font-size: 13px; text-align: right; flex-shrink: 0; }

.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
</style>
