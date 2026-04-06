<script setup>
import { ref, onMounted } from "vue";
import { riskApi } from "../api/risk.js";
import { useFlash } from "../lib/flash.js";

const activeTab = ref("events");
const flash = useFlash();

const events = ref([]);
const isEventsLoading = ref(false);
const eventsErrorMsg = ref("");

const filters = ref({
  company_name: "",
  risk_type: "",
  risk_level: "",
  review_status: ""
});

const fetchEvents = async () => {
  isEventsLoading.value = true;
  eventsErrorMsg.value = "";
  try {
    const data = await riskApi.getEvents(filters.value);
    events.value = data.events || data.data || data || [];
  } catch (error) {
    console.error("Failed to fetch risk events:", error);
    eventsErrorMsg.value = error.message || "加载风险事件失败";
  } finally {
    isEventsLoading.value = false;
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
    flash.error(error.message || "审核失败");
  }
};

const applyFilters = () => {
  fetchEvents();
};

const resetFilters = () => {
  filters.value = {
    company_name: "",
    risk_type: "",
    risk_level: "",
    review_status: ""
  };
  fetchEvents();
};

const getRiskLevelColor = (level) => {
  const colors = {
    high: "#ef4444",
    medium: "#f59e0b",
    low: "#10b981"
  };
  return colors[level?.toLowerCase()] || "#64748b";
};

const getReviewStatusText = (status) => {
  const texts = {
    pending: "待审核",
    approved: "已确认",
    rejected: "已忽略"
  };
  return texts[status?.toLowerCase()] || status || "待审核";
};

const getReviewStatusColor = (status) => {
  const colors = {
    pending: "#f59e0b",
    approved: "#10b981",
    rejected: "#ef4444"
  };
  return colors[status?.toLowerCase()] || "#64748b";
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch (e) {
    return dateStr;
  }
};

const reportType = ref("company");
const isReportLoading = ref(false);
const reportErrorMsg = ref("");
const generatedReport = ref(null);

const reportForm = ref({
  company_name: "",
  period_start: "",
  period_end: ""
});

const generateReport = async () => {
  isReportLoading.value = true;
  reportErrorMsg.value = "";
  generatedReport.value = null;

  try {
    let data;
    if (reportType.value === "company") {
      if (!reportForm.value.company_name) throw new Error("请输入公司名称");
      data = await riskApi.generateCompanyReport({
        company_name: reportForm.value.company_name,
        period_start: reportForm.value.period_start || undefined,
        period_end: reportForm.value.period_end || undefined
      });
    } else {
      if (!reportForm.value.period_start || !reportForm.value.period_end) {
        throw new Error("请输入开始和结束日期");
      }
      data = await riskApi.generateTimeRangeReport({
        period_start: reportForm.value.period_start,
        period_end: reportForm.value.period_end
      });
    }
    generatedReport.value = data.report || data.data?.report || data;
  } catch (error) {
    console.error("Failed to generate report:", error);
    reportErrorMsg.value = error.message || "生成报告失败";
  } finally {
    isReportLoading.value = false;
  }
};
</script>

<template>
  <div class="page-stack risk-page">
    <section class="page-hero">
      <div>
        <div class="page-hero__eyebrow">Workspace / Risk Control</div>
        <h1 class="page-hero__title">风险监测与报告工作台</h1>
        <p class="page-hero__subtitle">
          统一风险事件审核与报告生成两类操作。这里强调筛选效率、表格可读性与报告沉浸阅读，整体密度比管理后台更克制一些。
        </p>
      </div>
    </section>

    <div class="risk-summary-shell ui-card">
      <div class="tabs">
        <button :class="['tab-btn', { active: activeTab === 'events' }]" @click="activeTab = 'events'">风险事件审核</button>
        <button :class="['tab-btn', { active: activeTab === 'reports' }]" @click="activeTab = 'reports'">风险报告生成</button>
      </div>

      <div v-if="activeTab === 'events'" class="tab-content risk-events-content">
        <div class="section-heading">
          <h3 class="section-heading__title">待处理风险事件</h3>
          <p class="section-heading__desc">按公司、类型、等级和审核状态快速缩小范围，减少表格视觉噪音。</p>
        </div>

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

          <button class="primary-btn" @click="applyFilters" :disabled="isEventsLoading">查询</button>
          <button class="secondary-btn" @click="resetFilters" :disabled="isEventsLoading">重置</button>
        </div>

        <div class="content-area">
          <div v-if="isEventsLoading && events.length === 0" class="state-msg">加载中...</div>

          <div v-else-if="eventsErrorMsg" class="state-msg error">
            <div class="error-icon">⚠️</div>
            <p>{{ eventsErrorMsg }}</p>
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
                    <div class="meta-tags" v-if="item.confidence_score !== undefined || item.confidence !== undefined || item.document_id">
                      <span v-if="item.confidence_score !== undefined || item.confidence !== undefined" class="meta-tag">置信度: {{ Math.round((item.confidence_score !== undefined ? item.confidence_score : item.confidence) * 100) }}%</span>
                      <span v-if="item.document_id" class="meta-tag" :title="item.document_id">文档: {{ item.document_id.substring(0,8) }}...</span>
                    </div>
                  </td>
                  <td>
                    <span class="review-status" :style="{ color: getReviewStatusColor(item.review_status) }">
                      {{ getReviewStatusText(item.review_status) }}
                    </span>
                  </td>
                  <td class="action-cell">
                    <div class="actions" v-if="((item.review_status || 'pending').toLowerCase() === 'pending')">
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

      <div v-else-if="activeTab === 'reports'" class="tab-content risk-reports-content">
        <div class="report-form-card">
          <div class="section-heading">
            <h3 class="section-heading__title">生成风险报告</h3>
            <p class="section-heading__desc">支持按公司或时间区间生成，便于给管理层或业务侧直接复用。</p>
          </div>

          <div class="form-group row-group">
            <label>报告类型:</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" v-model="reportType" value="company" />
                按公司维度
              </label>
              <label class="radio-label">
                <input type="radio" v-model="reportType" value="time-range" />
                按时间区间
              </label>
            </div>
          </div>

          <div class="form-group" v-if="reportType === 'company'">
            <label>公司名称 <span class="required">*</span>:</label>
            <input type="text" v-model="reportForm.company_name" placeholder="例如: 某某科技公司" class="form-input" />
          </div>

          <div class="form-group row-group-inputs">
            <div class="input-col">
              <label>开始日期 <span v-if="reportType === 'time-range'" class="required">*</span>:</label>
              <input type="date" v-model="reportForm.period_start" class="form-input" />
            </div>
            <div class="input-col">
              <label>结束日期 <span v-if="reportType === 'time-range'" class="required">*</span>:</label>
              <input type="date" v-model="reportForm.period_end" class="form-input" />
            </div>
          </div>

          <div class="form-actions">
            <button class="primary-btn generate-btn" @click="generateReport" :disabled="isReportLoading">
              {{ isReportLoading ? '正在生成中...' : '生成报告' }}
            </button>
          </div>
          <div v-if="reportErrorMsg" class="error-text mt-4">{{ reportErrorMsg }}</div>
        </div>

        <div class="report-result ui-card" v-if="generatedReport">
          <div class="report-header">
            <h2>{{ generatedReport.title }}</h2>
            <div class="report-meta">
              <span class="meta-item">生成时间: {{ formatDate(generatedReport.created_at || generatedReport.generated_at) }}</span>
              <span class="meta-item">包含事件数: {{ generatedReport.source_metadata?.event_count || 0 }}</span>
              <span class="meta-item" v-if="generatedReport.source_metadata?.document_ids">涉及文档数: {{ generatedReport.source_metadata.document_ids.length }}</span>
            </div>
          </div>

          <div class="report-section summary-section">
            <h3>高管摘要</h3>
            <p class="summary-content">{{ generatedReport.summary }}</p>
          </div>

          <div class="report-section metadata-section" v-if="generatedReport.source_metadata">
            <h3>风险概况</h3>
            <div class="stats-grid">
              <div class="stat-card" v-if="generatedReport.source_metadata.risk_level_counts">
                <h4>风险等级分布</h4>
                <ul>
                  <li v-for="(count, level) in generatedReport.source_metadata.risk_level_counts" :key="level">
                    <span class="stat-label">{{ String(level).toUpperCase() }}</span>
                    <span class="stat-value">{{ count }}</span>
                  </li>
                </ul>
              </div>
              <div class="stat-card" v-if="generatedReport.source_metadata.risk_type_counts">
                <h4>风险类型分布</h4>
                <ul>
                  <li v-for="(count, type) in generatedReport.source_metadata.risk_type_counts" :key="type">
                    <span class="stat-label">{{ type }}</span>
                    <span class="stat-value">{{ count }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div class="report-section content-section">
            <h3>报告详情</h3>
            <div class="markdown-content">{{ generatedReport.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-summary-shell { display: flex; flex-direction: column; min-height: 760px; overflow: hidden; }
.tabs { display: flex; border-bottom: 1px solid #e2e8f0; padding: 0 28px; background: linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%); }
.tab-btn { padding: 18px 24px; border: none; background: transparent; font-size: 14px; font-weight: 700; color: #64748b; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; margin-right: 8px; }
.tab-btn:hover { color: #334155; }
.tab-btn.active { color: #4f46e5; border-bottom-color: #4f46e5; }
.tab-content { padding: 28px; flex: 1; display: flex; flex-direction: column; gap: 22px; overflow-y: auto; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; }
.filter-input, .filter-select, .form-input { padding: 11px 14px; border: 1px solid #dbe4f0; border-radius: 12px; outline: none; transition: border-color 0.2s, box-shadow 0.2s; font-family: inherit; background: #fff; }
.filter-input { flex: 1; min-width: 160px; }
.filter-select { min-width: 132px; }
.filter-input:focus, .filter-select:focus, .form-input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08); }
.primary-btn { padding: 0 22px; height: 44px; background: linear-gradient(135deg, #4f46e5, #4338ca); color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 700; transition: background 0.2s, transform 0.2s; white-space: nowrap; }
.primary-btn:hover:not(:disabled) { transform: translateY(-1px); }
.primary-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.secondary-btn { padding: 0 22px; height: 44px; background: #f8fafc; color: #475569; border: 1px solid #dbe4f0; border-radius: 12px; cursor: pointer; font-weight: 600; transition: all 0.2s; white-space: nowrap; }
.secondary-btn:hover:not(:disabled) { background: #eef2f7; }
.content-area { flex: 1; display: flex; flex-direction: column; }
.state-msg { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; text-align: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 16px; background: #f8fafc; }
.empty-icon, .error-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.error-icon { color: #ef4444; opacity: 1; }
.mt-4 { margin-top: 16px; }
.table-container { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 16px; background: white; }
.risk-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
.risk-table th { background: #f8fafc; padding: 14px 16px; font-weight: 700; color: #475569; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.risk-table td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; vertical-align: top; color: #1e293b; line-height: 1.55; }
.risk-table tr:last-child td { border-bottom: none; }
.risk-table tr:hover { background: #fafcff; }
.company-name { font-weight: 700; white-space: nowrap; }
.risk-type { background: #eef2ff; padding: 4px 8px; border-radius: 999px; font-size: 12px; color: #4f46e5; white-space: nowrap; }
.risk-level { font-size: 11px; font-weight: 700; color: white; padding: 4px 8px; border-radius: 999px; white-space: nowrap; }
.event-date { color: #64748b; font-size: 12px; white-space: nowrap; }
.summary-cell { min-width: 260px; max-width: 420px; }
.summary-text { font-weight: 600; margin-bottom: 8px; color: #334155; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.evidence-text { font-size: 12px; color: #475569; font-style: italic; background: #f8fafc; padding: 8px 10px; border-left: 3px solid #cbd5e1; border-radius: 0 8px 8px 0; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.meta-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.meta-tag { font-size: 11px; color: #64748b; background: #f1f5f9; padding: 3px 7px; border-radius: 999px; }
.review-status { font-weight: 700; white-space: nowrap; }
.action-cell { white-space: nowrap; }
.actions { display: flex; gap: 8px; }
.actions-done { color: #94a3b8; font-weight: 500; padding-left: 8px; }
.action-btn { padding: 7px 14px; border-radius: 10px; font-size: 12px; font-weight: 700; cursor: pointer; transition: all 0.2s; border: none; }
.action-btn.approve { background: #10b981; color: white; }
.action-btn.approve:hover { background: #059669; }
.action-btn.reject { background: white; color: #ef4444; border: 1px solid #fecaca; }
.action-btn.reject:hover { background: #fef2f2; }
.risk-reports-content { gap: 22px; }
.report-form-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 24px; }
.form-group { margin-bottom: 16px; }
.row-group { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.row-group label { margin-bottom: 0; min-width: 80px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #475569; font-size: 14px; }
.required { color: #ef4444; }
.form-input { width: 100%; max-width: 420px; font-size: 14px; }
.row-group-inputs { display: flex; gap: 16px; max-width: 460px; }
.input-col { flex: 1; }
.radio-group { display: flex; gap: 20px; flex-wrap: wrap; }
.radio-label { display: flex; align-items: center; gap: 8px; font-weight: 500 !important; cursor: pointer; font-size: 14px; }
.radio-label input[type="radio"] { accent-color: #6366f1; width: 16px; height: 16px; cursor: pointer; }
.form-actions { margin-top: 24px; }
.generate-btn { height: 46px; font-size: 14px; padding: 0 28px; }
.error-text { color: #ef4444; font-size: 14px; }
.report-result { padding: 30px; }
.report-header { margin-bottom: 28px; border-bottom: 1px solid #f1f5f9; padding-bottom: 22px; }
.report-header h2 { margin: 0 0 16px 0; color: #0f172a; font-size: 24px; line-height: 1.3; }
.report-meta { display: flex; gap: 12px; flex-wrap: wrap; }
.meta-item { background: #f8fafc; color: #64748b; padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid #e2e8f0; }
.report-section { margin-bottom: 28px; }
.report-section h3 { margin: 0 0 16px 0; color: #1e293b; font-size: 18px; display: flex; align-items: center; gap: 8px; }
.report-section h3::before { content: ''; display: block; width: 4px; height: 16px; background: #6366f1; border-radius: 2px; }
.summary-content { font-size: 14px; line-height: 1.75; color: #334155; background: #f8fafc; padding: 20px; border-radius: 12px; border-left: 4px solid #818cf8; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }
.stat-card { background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px; }
.stat-card h4 { margin: 0 0 12px 0; color: #475569; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.stat-card li { display: flex; justify-content: space-between; align-items: center; font-size: 14px; border-bottom: 1px dashed #f1f5f9; padding-bottom: 6px; }
.stat-card li:last-child { border-bottom: none; padding-bottom: 0; }
.stat-label { color: #64748b; }
.stat-value { font-weight: 700; color: #1e293b; background: #f1f5f9; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.markdown-content { font-size: 14px; line-height: 1.78; color: #334155; white-space: pre-wrap; font-family: inherit; background: white; padding: 24px; border: 1px solid #e2e8f0; border-radius: 14px; }
@media (max-width: 900px) {
  .tabs { padding: 0 18px; }
  .tab-content { padding: 20px; }
  .row-group-inputs { flex-direction: column; max-width: none; }
}
</style>
