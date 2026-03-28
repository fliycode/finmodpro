const fs = require('fs');

const qaApiContent = `import { createApiConfig, joinUrl } from './config.js';

const apiConfig = createApiConfig();

export const qaApi = {
  // Mock ask question
  async askQuestion(query) {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({
          answer: '根据相关资料，这里是您需要的答案。',
          citations: [
            {
              document_title: '2025年第一季度财务报表.pdf',
              doc_type: 'pdf',
              source_date: '2025-04-10',
              page_label: 'Page 12',
              snippet: '营业收入较上一季度增长了15%，主要由于核心业务的强劲表现。',
              score: 0.95
            },
            {
              document_title: '行业分析报告.docx',
              doc_type: 'docx',
              source_date: '2025-05-01',
              page_label: 'Section 3',
              snippet: '市场整体趋势向好，预计下半年将保持平稳增长。',
              score: 0.88
            }
          ]
        });
      }, 1000);
    });
  }
};
`;

const kbApiContent = `import { createApiConfig, joinUrl } from './config.js';

const apiConfig = createApiConfig();

// Mock data store
let mockDocuments = [
  { id: 1, name: '2024年度总结.pdf', status: 'indexed', uploadTime: '2026-03-24 10:00:00', size: '2.4MB' },
  { id: 2, name: 'Q1财务报表.xlsx', status: 'parsed', uploadTime: '2026-03-24 11:30:00', size: '1.1MB' },
  { id: 3, name: '损坏的文档.docx', status: 'failed', uploadTime: '2026-03-24 14:20:00', size: '0.5MB' }
];

export const kbApi = {
  // Mock listing documents
  async listDocuments() {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve([...mockDocuments]);
      }, 500);
    });
  },
  
  // Mock upload document (Single file)
  async uploadDocument(file) {
    return new Promise(resolve => {
      setTimeout(() => {
        const newDoc = {
          id: Date.now(),
          name: file.name,
          status: 'uploaded',
          uploadTime: new Date().toLocaleString(),
          size: (file.size / 1024 / 1024).toFixed(2) + 'MB'
        };
        mockDocuments.unshift(newDoc);
        
        // Simulate background processing
        setTimeout(() => { 
          const doc = mockDocuments.find(d => d.id === newDoc.id);
          if (doc) doc.status = 'parsed'; 
        }, 2000);
        setTimeout(() => { 
          const doc = mockDocuments.find(d => d.id === newDoc.id);
          if (doc) doc.status = 'chunked'; 
        }, 4000);
        setTimeout(() => { 
          const doc = mockDocuments.find(d => d.id === newDoc.id);
          if (doc) doc.status = 'indexed'; 
        }, 6000);

        resolve({ success: true, document: newDoc });
      }, 800);
    });
  }
};
`;

const financialQaContent = `<script setup>
import { ref } from "vue";
import { qaApi } from "../api/qa.js";

const query = ref("");
const messages = ref([{ role: "system", content: "您好，我是您的金融助手。请输入您的问题。" }]);
const isAsking = ref(false);

const handleAsk = async () => {
  if (!query.value.trim() || isAsking.value) return;
  messages.value.push({ role: "user", content: query.value });
  const currentQuery = query.value;
  query.value = "";
  isAsking.value = true;
  
  try {
    const response = await qaApi.askQuestion(currentQuery);
    messages.value.push({
      role: "assistant",
      content: response.answer,
      citations: response.citations
    });
  } catch (error) {
    messages.value.push({ role: "assistant", content: "（请求失败，请稍后重试）" });
  } finally {
    isAsking.value = false;
  }
};

const toggleCitation = (citation) => {
  citation.expanded = !citation.expanded;
};
</script>

<template>
  <div class="qa-shell">
    <div class="chat-window">
      <div class="messages">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
          <div class="avatar">{{ msg.role === "user" ? "🧑" : "🤖" }}</div>
          <div class="message-content">
            <div class="bubble">{{ msg.content }}</div>
            
            <!-- Citations Block -->
            <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
              <div class="citations-title">
                <svg viewBox="0 0 24 24" fill="none" class="icon-small"><path d="M12 2L2 22h20L12 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
                参考来源 ({{ msg.citations.length }})
              </div>
              <div class="citations-list">
                <div v-for="(cite, i) in msg.citations" :key="i" class="citation-card">
                  <div class="citation-header" @click="toggleCitation(cite)">
                    <span class="cite-index">[{{ i + 1 }}]</span>
                    <span class="cite-title">{{ cite.document_title }}</span>
                    <span class="cite-type">{{ cite.doc_type }}</span>
                    <span class="cite-score" v-if="cite.score">相关度: {{ (cite.score * 100).toFixed(0) }}%</span>
                    <svg :class="['expand-icon', { 'expanded': cite.expanded }]" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </div>
                  <div class="citation-body" v-show="cite.expanded">
                    <div class="cite-meta">
                      <span>页码/位置: {{ cite.page_label }}</span>
                      <span>日期: {{ cite.source_date }}</span>
                    </div>
                    <div class="cite-snippet">"{{ cite.snippet }}"</div>
                  </div>
                </div>
              </div>
            </div>
            
          </div>
        </div>
        <div v-if="isAsking" class="message assistant">
          <div class="avatar">🤖</div>
          <div class="message-content"><div class="bubble typing">正在思考...</div></div>
        </div>
      </div>
      <div class="input-area">
        <textarea v-model="query" placeholder="输入您的金融分析问题... (Shift+Enter 换行，Enter 发送)" @keydown.enter.exact.prevent="handleAsk"></textarea>
        <button @click="handleAsk" :disabled="isAsking || !query.trim()" class="send-btn">发送</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qa-shell { height: calc(100vh - 160px); display: flex; flex-direction: column; }
.chat-window { flex: 1; background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
.messages { flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; }
.message { display: flex; gap: 12px; max-width: 85%; }
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.message-content { display: flex; flex-direction: column; gap: 8px; flex: 1; max-width: 100%; }
.bubble { padding: 12px 16px; border-radius: 12px; line-height: 1.6; word-break: break-word; }
.assistant .bubble { background: #f8fafc; color: #1e293b; border-top-left-radius: 4px; border: 1px solid #e2e8f0; }
.user .bubble { background: #6366f1; color: white; border-top-right-radius: 4px; }
.typing { color: #64748b; font-style: italic; }

.citations-container { margin-top: 4px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; max-width: 100%; }
.citations-title { display: flex; align-items: center; gap: 6px; color: #64748b; font-weight: 600; font-size: 12px; }
.icon-small { width: 14px; height: 14px; }
.citations-list { display: flex; flex-direction: column; gap: 8px; }
.citation-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; transition: all 0.2s; }
.citation-card:hover { border-color: #cbd5e1; }
.citation-header { padding: 8px 12px; display: flex; align-items: center; gap: 8px; cursor: pointer; background: #f8fafc; user-select: none; }
.cite-index { color: #6366f1; font-weight: 700; }
.cite-title { flex: 1; font-weight: 600; color: #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.cite-type { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 11px; text-transform: uppercase; color: #475569; flex-shrink: 0; }
.cite-score { color: #10b981; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.expand-icon { width: 16px; height: 16px; color: #94a3b8; transition: transform 0.2s; flex-shrink: 0; }
.expand-icon.expanded { transform: rotate(180deg); }
.citation-body { padding: 12px; border-top: 1px dashed #e2e8f0; display: flex; flex-direction: column; gap: 8px; }
.cite-meta { display: flex; gap: 16px; color: #64748b; font-size: 12px; flex-wrap: wrap; }
.cite-snippet { color: #475569; line-height: 1.5; background: #f1f5f9; padding: 8px; border-radius: 6px; border-left: 3px solid #6366f1; word-break: break-word; }

.input-area { padding: 16px; border-top: 1px solid #e2e8f0; display: flex; gap: 12px; background: white; }
textarea { flex: 1; height: 60px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; resize: none; font-family: inherit; transition: border-color 0.2s; }
textarea:focus { outline: none; border-color: #6366f1; }
.send-btn { padding: 0 24px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: background 0.2s; }
.send-btn:hover:not(:disabled) { background: #4f46e5; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
`;

const kbContent = `<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { kbApi } from "../api/knowledgebase.js";

const items = ref([]);
const isLoading = ref(false);
const fileInput = ref(null);
const isUploading = ref(false);

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
    await kbApi.uploadDocument(file);
    // Refresh list immediately after upload request completes
    await fetchDocuments();
  } catch (error) {
    console.error("Upload failed:", error);
    alert("上传失败");
  } finally {
    isUploading.value = false;
    event.target.value = ''; // Reset input
  }
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    // Only poll if there are items not in a terminal state
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
    uploaded: '#3b82f6', // blue
    parsed: '#8b5cf6', // purple
    chunked: '#f59e0b', // amber
    indexed: '#10b981', // green
    failed: '#ef4444' // red
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
            <span class="status-badge" :style="{ backgroundColor: getStatusColor(item.status) + '1A', color: getStatusColor(item.status), border: \`1px solid \${getStatusColor(item.status)}40\` }">
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
`;

fs.writeFileSync('src/api/qa.js', qaApiContent);
fs.writeFileSync('src/api/knowledgebase.js', kbApiContent);
fs.writeFileSync('src/components/FinancialQA.vue', financialQaContent);
fs.writeFileSync('src/components/KnowledgeBase.vue', kbContent);
console.log('Update successful');
