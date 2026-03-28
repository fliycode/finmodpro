<script setup>
import { ref, onMounted } from "vue";
import { riskApi } from "../api/risk.js";

const events = ref([]);
const isLoading = ref(false);
const errorMsg = ref("");

// Filter states
const filters = ref({
  company_name: '',
  risk_type: '',
  risk_level: '',
  review_status: ''
});

const fetchEvents = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await riskApi.getEvents(filters.value);
    events.value = data.events || data.data || data || [];
  } catch (error) {
    console.error("Failed to fetch risk events:", error);
    errorMsg.value = error.message || "加载风险事件失败";
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchEvents();
});

const handleReview = async (event, status) => {
  try {
    await riskApi.reviewEvent(event.id || event.event_id, status);
    event.review_status = status;
  } catch (error) {
    console.error("Failed to review event:", error);
    alert(error.message || "审核失败");
  }
};

const applyFilters = () => {
  fetchEvents();
};

const resetFilters = () => {
  filters.value = {
    company_name: '',
    risk_type: '',
    risk_level: '',
    review_status: ''
  };
  fetchEvents();
};

const getRiskLevelColor = (level) => {
  const colors = {
    high: '#ef4444',
    medium: '#f59e0b',
    low: '#10b981'
  };
  return colors[level?.toLowerCase()] || '#64748b';
};

const getReviewStatusText = (status) => {
  const texts = {
    pending: '待审核',
    approved: '已确认',
    rejected: '已忽略'
  };
  return texts[status?.toLowerCase()] || status || '待审核';
};

const getReviewStatusColor = (status) => {
  const colors = {
    pending: '#f59e0b',
    approved: '#10b981',
    rejected: '#ef4444'
  };
  return colors[status?.toLowerCase()] || '#64748b';
};

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleString();
  } catch (e) {
    return dateStr;
  }
};
</script>

<template>
  <div class="risk-events-shell">
    <div class="toolbar">
      <input type="text" v-model="filters.company_name" placeholder="公司名称" class="filter-input" @keyup.enter="applyFilters" />
      <input type="text" v-model="filters.risk_type" placeholder="风险类型" class="filter-input" @keyup.enter="applyFilters" />
      
      <select v-model="filters.risk_level" class="filter-select" @change="applyFilters">
        <option value="">全部等级</option>
        <option value="high">高风险</option>
        <option value="medium">中风险</option>
        <option value="low">低风险</option>
      </select>
      
      <select v-model="filters.review_status" class="filter-select" @change="applyFilters">
        <option value="">全部状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已确认</option>
        <option value="rejected">已忽略</option>
      </select>

      <button class="primary-btn" @click="applyFilters" :disabled="isLoading">查询</button>
      <button class="secondary-btn" @click="resetFilters" :disabled="isLoading">重置</button>
    </div>
    
    <div class="content-area">
      <div v-if="isLoading && events.length === 0" class="state-msg">加载中...</div>
      
      <div v-else-if="errorMsg" class="state-msg error">
        <div class="error-icon">⚠️</div>
        <p>{{ errorMsg }}</p>
        <button class="primary-btn mt-4" @click="fetchEvents">重试</button>
      </div>
      
      <div v-else-if="events.length === 0" class="state-msg empty">
        <div class="empty-icon">🛡️</div>
        <p>暂无风险事件。</p>
      </div>
      
      <div v-else class="table-container">
        <table class="risk-table">
          <thead>
            <tr>
              <th>公司名</th>
              <th>风险类型</th>
              <th>风险等级</th>
              <th>事件时间</th>
              <th>摘要 / 证据</th>
              <th>审核状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in events" :key="item.id || item.event_id || index">
              <td class="company-name">{{ item.company_name || '未知公司' }}</td>
              <td><span class="risk-type">{{ item.risk_type }}</span></td>
              <td>
                <span class="risk-level" :style="{ backgroundColor: getRiskLevelColor(item.risk_level) }">
                  {{ (item.risk_level || 'UNKNOWN').toUpperCase() }}
                </span>
              </td>
              <td class="event-date">{{ formatDate(item.event_date || item.created_at) }}</td>
              <td class="summary-cell">
                <div class="summary-text" :title="item.summary">{{ item.summary }}</div>
                <div class="evidence-text" v-if="item.evidence_text" :title="item.evidence_text">"{{ item.evidence_text }}"</div>
                <div class="meta-tags" v-if="item.confidence !== undefined || item.document_id">
                  <span v-if="item.confidence !== undefined" class="meta-tag">置信度: {{ item.confidence }}</span>
                  <span v-if="item.document_id" class="meta-tag" :title="item.document_id">文档: {{ item.document_id.substring(0,8) }}...</span>
                </div>
              </td>
              <td>
                <span class="review-status" :style="{ color: getReviewStatusColor(item.review_status) }">
                  {{ getReviewStatusText(item.review_status) }}
                </span>
              </td>
              <td class="action-cell">
                <div class="actions" v-if="(item.review_status || 'pending').toLowerCase() === 'pending'">
                  <button class="action-btn approve" @click="handleReview(item, 'approved')">确认</button>
                  <button class="action-btn reject" @click="handleReview(item, 'rejected')">忽略</button>
                </div>
                <div v-else class="actions-done">-</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-events-shell { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-height: 500px; display: flex; flex-direction: column; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
.filter-input { flex: 1; min-width: 150px; padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; outline: none; transition: border-color 0.2s; font-family: inherit; }
.filter-input:focus { border-color: #6366f1; }
.filter-select { padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; outline: none; transition: border-color 0.2s; font-family: inherit; background: white; min-width: 120px; }
.filter-select:focus { border-color: #6366f1; }

.primary-btn { padding: 0 24px; height: 42px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: background 0.2s; white-space: nowrap; }
.primary-btn:hover:not(:disabled) { background: #4f46e5; }
.primary-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.secondary-btn { padding: 0 24px; height: 42px; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; white-space: nowrap; }
.secondary-btn:hover:not(:disabled) { background: #e2e8f0; }

.content-area { flex: 1; display: flex; flex-direction: column; }
.state-msg { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; text-align: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 8px; background: #f8fafc; }
.empty-icon, .error-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.error-icon { color: #ef4444; opacity: 1; }
.mt-4 { margin-top: 16px; }

/* Table Styles */
.table-container {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
}

.risk-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}

.risk-table th {
  background: #f8fafc;
  padding: 14px 16px;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.risk-table td {
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
  color: #1e293b;
}

.risk-table tr:last-child td {
  border-bottom: none;
}

.risk-table tr:hover {
  background: #f8fafc;
}

.company-name {
  font-weight: 600;
  white-space: nowrap;
}

.risk-type {
  background: #e2e8f0;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
  color: #475569;
  white-space: nowrap;
}

.risk-level {
  font-size: 11px;
  font-weight: 700;
  color: white;
  padding: 3px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

.event-date {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.summary-cell {
  min-width: 250px;
  max-width: 400px;
}

.summary-text {
  font-weight: 500;
  margin-bottom: 8px;
  color: #334155;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.evidence-text {
  font-size: 13px;
  color: #475569;
  font-style: italic;
  background: #f1f5f9;
  padding: 8px 10px;
  border-left: 3px solid #cbd5e1;
  border-radius: 0 4px 4px 0;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
}

.review-status {
  font-weight: 600;
  white-space: nowrap;
}

.action-cell {
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
}

.actions-done {
  color: #94a3b8;
  font-weight: 500;
  padding-left: 8px;
}

.action-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.action-btn.approve {
  background: #10b981;
  color: white;
}

.action-btn.approve:hover {
  background: #059669;
}

.action-btn.reject {
  background: white;
  color: #ef4444;
  border: 1px solid #fecaca;
}

.action-btn.reject:hover {
  background: #fef2f2;
}
</style>
