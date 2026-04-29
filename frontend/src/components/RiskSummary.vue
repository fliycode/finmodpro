<script setup>
import { computed, onMounted, ref } from "vue";
import { riskApi } from "../api/risk.js";
import { useFlash } from "../lib/flash.js";
import {
  buildRiskLevelChartOption,
  buildRiskTrendChartOption,
  buildRiskTypeChartOption,
  normalizeRiskAnalytics,
} from "../lib/risk-workspace.js";
import MetaChips from "./ui/MetaChips.vue";
import AdminChart from "./admin/AdminChart.vue";
import DossierPageShell from "./workspace/dossier/DossierPageShell.vue";
import DossierEvidenceStack from "./workspace/dossier/DossierEvidenceStack.vue";

const flash = useFlash();

const buildDefaultFilters = () => ({
  company_name: "",
  risk_type: "",
  risk_level: "",
  review_status: "",
  period_start: "",
  period_end: "",
});

const filters = ref(buildDefaultFilters());

const events = ref([]);
const isEventsLoading = ref(false);
const eventsErrorMsg = ref("");

const analyticsPayload = ref(null);
const isAnalyticsLoading = ref(false);
const analyticsErrorMsg = ref("");

const analytics = computed(() => normalizeRiskAnalytics(analyticsPayload.value));
const analyticsHighlights = computed(() => ([
  { key: "total", label: "事件总量", value: analytics.value.summary.total_events, tone: "brand" },
  { key: "high", label: "高风险/严重", value: analytics.value.summary.high_risk_events, tone: "risk" },
  { key: "pending", label: "待审核", value: analytics.value.summary.pending_reviews, tone: "warning" },
  { key: "company", label: "涉及公司", value: analytics.value.summary.unique_companies, tone: "neutral" },
  { key: "document", label: "来源文档", value: analytics.value.summary.document_count, tone: "neutral" },
]));
const riskLevelOption = computed(() => buildRiskLevelChartOption(analytics.value));
const riskTypeOption = computed(() => buildRiskTypeChartOption(analytics.value));
const riskTrendOption = computed(() => buildRiskTrendChartOption(analytics.value));

const fetchEvents = async () => {
  isEventsLoading.value = true;
  eventsErrorMsg.value = "";
  try {
    const data = await riskApi.getEvents(filters.value);
    events.value = data.data?.risk_events || data.risk_events || [];
  } catch (error) {
    console.error("Failed to fetch risk events:", error);
    eventsErrorMsg.value = error.message || "加载风险事件失败";
  } finally {
    isEventsLoading.value = false;
  }
};

const fetchAnalytics = async () => {
  isAnalyticsLoading.value = true;
  analyticsErrorMsg.value = "";
  try {
    analyticsPayload.value = await riskApi.getAnalytics(filters.value);
  } catch (error) {
    console.error("Failed to fetch analytics:", error);
    analyticsErrorMsg.value = error.message || "加载风险分析失败";
  } finally {
    isAnalyticsLoading.value = false;
  }
};

const refreshWorkspace = async () => {
  await Promise.all([fetchEvents(), fetchAnalytics()]);
};

onMounted(() => {
  refreshWorkspace();
});

const handleReview = async (event, status) => {
  try {
    await riskApi.reviewEvent(event.id || event.event_id, status);
    flash.success(`风险事件已${status === "approved" ? "确认" : "忽略"}`);
    await refreshWorkspace();
  } catch (error) {
    console.error("Failed to review event:", error);
    flash.error(error.message || "审核失败");
  }
};

const applyFilters = () => {
  refreshWorkspace();
};

const resetFilters = () => {
  filters.value = buildDefaultFilters();
  refreshWorkspace();
};

const getReviewStatusText = (status) => {
  const texts = {
    pending: "待审核",
    approved: "已确认",
    rejected: "已忽略",
  };
  return texts[status?.toLowerCase()] || status || "待审核";
};

const getRiskTagType = (level) => {
  if (level === "high" || level === "critical") return "danger";
  if (level === "medium") return "warning";
  if (level === "low") return "success";
  return "info";
};

const getReviewTagType = (status) => {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  if (status === "pending") return "warning";
  return "info";
};

const getEventMetaChips = (item) => {
  const chips = [];
  if (item.confidence_score !== undefined || item.confidence !== undefined) {
    const value = item.confidence_score !== undefined ? item.confidence_score : item.confidence;
    chips.push({ key: "confidence", label: `置信度: ${Math.round(Number(value) * 100)}%` });
  }
  if (item.document_id) {
    chips.push({ key: "document", label: `文档: ${String(item.document_id)}`, title: String(item.document_id) });
  }
  return chips;
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
};

const reportType = ref("company");
const isReportLoading = ref(false);
const isReportExporting = ref(false);
const reportErrorMsg = ref("");
const generatedReport = ref(null);

const reportForm = ref({
  company_name: "",
  period_start: "",
  period_end: "",
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
        period_end: reportForm.value.period_end || undefined,
      });
    } else {
      if (!reportForm.value.period_start || !reportForm.value.period_end) {
        throw new Error("请输入开始和结束日期");
      }
      data = await riskApi.generateTimeRangeReport({
        period_start: reportForm.value.period_start,
        period_end: reportForm.value.period_end,
      });
    }
    generatedReport.value = data.data?.report || data.report || data;
    flash.success("风险报告生成成功");
    await fetchAnalytics();
  } catch (error) {
    console.error("Failed to generate report:", error);
    reportErrorMsg.value = error.message || "生成报告失败";
  } finally {
    isReportLoading.value = false;
  }
};

const downloadGeneratedReport = async (format = "markdown") => {
  if (!generatedReport.value?.id) {
    flash.error("请先生成报告后再导出");
    return;
  }

  isReportExporting.value = true;
  try {
    const exportPayload = await riskApi.exportReport(generatedReport.value.id, { format });
    const blob = new Blob([exportPayload.content], { type: exportPayload.contentType });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportPayload.filename;
    link.click();
    window.URL.revokeObjectURL(url);
    flash.success(`风险报告已导出为 ${format === "json" ? "JSON" : "Markdown"}`);
  } catch (error) {
    console.error("Failed to export report:", error);
    flash.error(error.message || "导出失败");
  } finally {
    isReportExporting.value = false;
  }
};
</script>

<template>
  <div class="risk-dossier-page">
    <DossierPageShell title="风险摘要与报告" eyebrow="Risk dossier">
      <template #summary>
        <section class="risk-dossier-panel">
          <header class="risk-dossier-panel__header">
            <p>Conclusion first</p>
            <h3>风险概览</h3>
          </header>

          <el-alert
            v-if="analyticsErrorMsg"
            :title="analyticsErrorMsg"
            type="error"
            show-icon
            :closable="false"
          />

          <div v-else class="analytics-shell" v-loading="isAnalyticsLoading">
            <div class="analytics-highlight-grid">
              <article
                v-for="item in analyticsHighlights"
                :key="item.key"
                class="analytics-highlight"
                :class="`analytics-highlight--${item.tone}`"
              >
                <span class="analytics-highlight__label">{{ item.label }}</span>
                <strong class="analytics-highlight__value">{{ item.value }}</strong>
              </article>
            </div>

            <section class="risk-company-brief">
              <header class="risk-company-brief__header">
                <h4>重点公司</h4>
                <span>按事件数量排序</span>
              </header>
              <ul class="analytics-company-list">
                <li v-for="item in analytics.top_companies" :key="item.key">
                  <span>{{ item.key }}</span>
                  <strong>{{ item.value }}</strong>
                </li>
                <li v-if="analytics.top_companies.length === 0" class="analytics-company-list__empty">
                  当前筛选条件下暂无公司分布数据。
                </li>
              </ul>
            </section>
          </div>
        </section>
      </template>

      <template #evidence>
        <DossierEvidenceStack>
          <section class="risk-dossier-panel risk-dossier-panel--charts">
            <header class="risk-dossier-panel__header">
              <p>Evidence & sources</p>
              <h3>分布与趋势</h3>
            </header>
            <div class="analytics-chart-grid">
              <div class="analytics-chart-card">
                <div class="analytics-chart-card__head">
                  <h4>风险等级分布</h4>
                  <span>按筛选结果统计</span>
                </div>
                <AdminChart :option="riskLevelOption" height="280px" />
              </div>
              <div class="analytics-chart-card">
                <div class="analytics-chart-card__head">
                  <h4>风险类型分布</h4>
                  <span>观察当前聚焦点</span>
                </div>
                <AdminChart :option="riskTypeOption" height="280px" />
              </div>
              <div class="analytics-chart-card analytics-chart-card--wide">
                <div class="analytics-chart-card__head">
                  <h4>事件时间趋势</h4>
                  <span>近期风险集中区间</span>
                </div>
                <AdminChart :option="riskTrendOption" height="300px" />
              </div>
            </div>
          </section>

          <section class="risk-dossier-panel">
            <header class="risk-dossier-panel__header">
              <p>Review queue</p>
              <h3>待处理风险事件</h3>
            </header>

            <el-form :inline="true" class="admin-form-row risk-filter-row">
              <el-form-item>
                <el-input v-model="filters.company_name" placeholder="公司名称" clearable @keyup.enter="applyFilters" />
              </el-form-item>
              <el-form-item>
                <el-input v-model="filters.risk_type" placeholder="风险类型" clearable @keyup.enter="applyFilters" />
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.risk_level" placeholder="全部等级" clearable>
                  <el-option label="高风险" value="high" />
                  <el-option label="中风险" value="medium" />
                  <el-option label="低风险" value="low" />
                  <el-option label="严重" value="critical" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="filters.review_status" placeholder="全部状态" clearable>
                  <el-option label="待审核" value="pending" />
                  <el-option label="已确认" value="approved" />
                  <el-option label="已忽略" value="rejected" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-date-picker v-model="filters.period_start" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
              </el-form-item>
              <el-form-item>
                <el-date-picker v-model="filters.period_end" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="applyFilters" :loading="isEventsLoading || isAnalyticsLoading">查询</el-button>
                <el-button @click="resetFilters" :disabled="isEventsLoading || isAnalyticsLoading">重置</el-button>
              </el-form-item>
            </el-form>

            <el-alert v-if="eventsErrorMsg" :title="eventsErrorMsg" type="error" show-icon :closable="false" />

            <el-table v-else :data="events" stripe style="width: 100%" v-loading="isEventsLoading">
              <el-table-column prop="company_name" label="公司名" min-width="160">
                <template #default="scope">
                  <span class="company-name">{{ scope.row.company_name || "未知公司" }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="risk_type" label="风险类型" width="140">
                <template #default="scope">
                  <el-tag effect="plain">{{ scope.row.risk_type }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="风险等级" width="120">
                <template #default="scope">
                  <el-tag :type="getRiskTagType(scope.row.risk_level)">
                    {{ (scope.row.risk_level || "unknown").toUpperCase() }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="事件时间" min-width="180">
                <template #default="scope">
                  <span class="muted-text">{{ formatDate(scope.row.event_time || scope.row.created_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="摘要 / 证据" min-width="320">
                <template #default="scope">
                  <div class="summary-block">
                    <div class="summary-text">{{ scope.row.summary }}</div>
                    <div v-if="scope.row.evidence_text" class="summary-block__quote">"{{ scope.row.evidence_text }}"</div>
                    <MetaChips :items="getEventMetaChips(scope.row)" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="审核状态" width="120">
                <template #default="scope">
                  <el-tag :type="getReviewTagType((scope.row.review_status || 'pending').toLowerCase())">
                    {{ getReviewStatusText(scope.row.review_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="160" fixed="right">
                <template #default="scope">
                  <div v-if="(scope.row.review_status || 'pending').toLowerCase() === 'pending'" class="inline-actions">
                    <el-button type="success" plain size="small" @click="handleReview(scope.row, 'approved')">确认</el-button>
                    <el-button type="danger" plain size="small" @click="handleReview(scope.row, 'rejected')">忽略</el-button>
                  </div>
                  <span v-else class="muted-text">-</span>
                </template>
              </el-table-column>
              <template #empty>
                <div class="admin-empty-state">暂无风险事件。</div>
              </template>
            </el-table>
          </section>
        </DossierEvidenceStack>
      </template>

      <template #actions>
        <section class="risk-dossier-panel risk-dossier-panel--actions">
          <header class="risk-dossier-panel__header">
            <p>Actions last</p>
            <h3>生成报告</h3>
          </header>

          <el-form label-width="92px" class="risk-report-form">
            <el-form-item label="报告类型">
              <el-radio-group v-model="reportType">
                <el-radio value="company">按公司维度</el-radio>
                <el-radio value="time-range">按时间区间</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="reportType === 'company'" label="公司名称">
              <el-input v-model="reportForm.company_name" placeholder="例如: 某某科技公司" clearable />
            </el-form-item>

            <el-form-item label="开始日期">
              <el-date-picker v-model="reportForm.period_start" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" />
            </el-form-item>

            <el-form-item label="结束日期">
              <el-date-picker v-model="reportForm.period_end" type="date" value-format="YYYY-MM-DD" placeholder="选择结束日期" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="generateReport" :loading="isReportLoading">生成报告</el-button>
            </el-form-item>
          </el-form>

          <el-alert v-if="reportErrorMsg" :title="reportErrorMsg" type="error" show-icon :closable="false" />

          <div v-if="generatedReport" class="risk-report-quick-actions">
            <button type="button" class="risk-sheet-btn" :disabled="isReportExporting" @click="downloadGeneratedReport('markdown')">
              导出 Markdown
            </button>
            <button type="button" class="risk-sheet-btn" :disabled="isReportExporting" @click="downloadGeneratedReport('json')">
              导出 JSON
            </button>
          </div>
        </section>
      </template>
    </DossierPageShell>

    <section v-if="generatedReport" class="report-result">
      <div class="report-header">
        <div>
          <p class="report-eyebrow">Generated report</p>
          <h2>{{ generatedReport.title }}</h2>
          <div class="report-meta">
            <span class="meta-item">生成时间: {{ formatDate(generatedReport.created_at || generatedReport.generated_at) }}</span>
            <span class="meta-item">包含事件数: {{ generatedReport.source_metadata?.event_count || 0 }}</span>
            <span v-if="generatedReport.source_metadata?.document_ids" class="meta-item">
              涉及文档数: {{ generatedReport.source_metadata.document_ids.length }}
            </span>
          </div>
        </div>
      </div>

      <div class="report-section summary-section">
        <h3>高管摘要</h3>
        <p class="summary-content">{{ generatedReport.summary }}</p>
      </div>

      <div v-if="generatedReport.source_metadata" class="report-section metadata-section">
        <h3>风险概况</h3>
        <div class="stats-grid">
          <div v-if="generatedReport.source_metadata.risk_level_counts" class="stat-card">
            <h4>风险等级分布</h4>
            <ul>
              <li v-for="(count, level) in generatedReport.source_metadata.risk_level_counts" :key="level">
                <span class="stat-label">{{ String(level).toUpperCase() }}</span>
                <span class="stat-value">{{ count }}</span>
              </li>
            </ul>
          </div>
          <div v-if="generatedReport.source_metadata.risk_type_counts" class="stat-card">
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
    </section>
  </div>
</template>

<style scoped>
.risk-dossier-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.risk-dossier-panel,
.report-result {
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 22px;
  background: rgba(251, 246, 237, 0.94);
  box-shadow: 0 18px 52px -42px rgba(80, 54, 20, 0.28);
}

.risk-dossier-panel {
  padding: 20px;
}

.risk-dossier-panel__header {
  margin-bottom: 16px;
}

.risk-dossier-panel__header p,
.report-eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.risk-dossier-panel__header h3,
.report-header h2 {
  margin: 0;
  color: #2f2418;
  letter-spacing: -0.02em;
}

.analytics-shell,
.summary-block {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.analytics-highlight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.analytics-highlight {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  background: rgba(255, 251, 245, 0.94);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.analytics-highlight--brand {
  border-color: rgba(154, 106, 44, 0.18);
}

.analytics-highlight--risk {
  border-color: rgba(196, 73, 61, 0.22);
}

.analytics-highlight--warning {
  border-color: rgba(183, 121, 31, 0.22);
}

.analytics-highlight__label,
.analytics-chart-card__head span,
.risk-company-brief__header span {
  color: #8b7358;
  font-size: 12px;
  font-weight: 700;
}

.analytics-highlight__value {
  color: #2f2418;
  font-size: 28px;
  line-height: 1;
}

.risk-company-brief {
  border-top: 1px solid rgba(95, 69, 35, 0.12);
  padding-top: 14px;
}

.risk-company-brief__header,
.analytics-chart-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.risk-company-brief__header h4,
.analytics-chart-card__head h4,
.report-section h3 {
  margin: 0;
  color: #2f2418;
}

.analytics-company-list {
  list-style: none;
  padding: 0;
  margin: 12px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.analytics-company-list li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #4d3d2a;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(95, 69, 35, 0.14);
}

.analytics-company-list li:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.analytics-company-list__empty {
  color: #8b7358;
}

.analytics-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.analytics-chart-card {
  border: 1px solid rgba(95, 69, 35, 0.12);
  border-radius: 18px;
  padding: 18px;
  background: rgba(255, 251, 245, 0.94);
}

.analytics-chart-card--wide {
  grid-column: 1 / -1;
}

.risk-filter-row {
  margin-bottom: 16px;
}

.company-name {
  font-weight: 700;
  white-space: nowrap;
  color: #2f2418;
}

.summary-text {
  font-weight: 600;
  color: #4d3d2a;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.summary-block__quote {
  color: #8b7358;
  font-size: 13px;
  line-height: 1.7;
}

.risk-report-form :deep(.el-date-editor),
.risk-report-form :deep(.el-input) {
  width: 100%;
  max-width: 360px;
}

.risk-report-quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 18px;
}

.risk-sheet-btn {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(95, 69, 35, 0.14);
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
  font-weight: 700;
  cursor: pointer;
  text-align: left;
}

.report-result {
  padding: 26px;
}

.report-header {
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.report-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.meta-item {
  background: rgba(255, 251, 245, 0.96);
  color: #6f5a42;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(95, 69, 35, 0.12);
}

.report-section {
  margin-bottom: 24px;
}

.summary-content,
.markdown-content {
  font-size: 14px;
  line-height: 1.78;
  color: #4d3d2a;
  white-space: pre-wrap;
  background: rgba(255, 251, 245, 0.96);
  padding: 22px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  border-radius: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  background: rgba(255, 251, 245, 0.96);
  border: 1px solid rgba(95, 69, 35, 0.12);
  border-radius: 16px;
  padding: 16px;
}

.stat-card h4 {
  margin: 0 0 12px;
  color: #6f5a42;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.stat-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-card li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  border-bottom: 1px dashed rgba(95, 69, 35, 0.12);
  padding-bottom: 6px;
}

.stat-card li:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.stat-label {
  color: #6f5a42;
}

.stat-value {
  font-weight: 700;
  color: #2f2418;
  background: rgba(154, 106, 44, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
}

@media (max-width: 1100px) {
  .analytics-highlight-grid,
  .analytics-chart-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .report-result {
    padding: 20px;
  }
}
</style>
