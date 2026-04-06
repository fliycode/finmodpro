<script setup>
import { ref, onMounted } from "vue";
import { riskApi } from "../api/risk.js";
import { useFlash } from "../lib/flash.js";
import AppSectionCard from "./ui/AppSectionCard.vue";
import AppToolbar from "./ui/AppToolbar.vue";
import MetaChips from "./ui/MetaChips.vue";

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
    flash.success(`风险事件已${status === 'approved' ? '确认' : '忽略'}`);
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

const getReviewStatusText = (status) => {
  const texts = {
    pending: "待审核",
    approved: "已确认",
    rejected: "已忽略"
  };
  return texts[status?.toLowerCase()] || status || "待审核";
};

const getRiskTagType = (level) => {
  if (level === 'high') return 'danger';
  if (level === 'medium') return 'warning';
  if (level === 'low') return 'success';
  return 'info';
};

const getReviewTagType = (status) => {
  if (status === 'approved') return 'success';
  if (status === 'rejected') return 'danger';
  if (status === 'pending') return 'warning';
  return 'info';
};

const getEventMetaChips = (item) => {
  const chips = [];
  if (item.confidence_score !== undefined || item.confidence !== undefined) {
    const value = item.confidence_score !== undefined ? item.confidence_score : item.confidence;
    chips.push({ key: 'confidence', label: `置信度: ${Math.round(value * 100)}%` });
  }
  if (item.document_id) {
    chips.push({ key: 'document', label: `文档: ${item.document_id.substring(0, 8)}...`, title: item.document_id });
  }
  return chips;
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
    flash.success('风险报告生成成功');
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

    <el-card class="ui-card risk-summary-shell" shadow="never">
      <el-tabs v-model="activeTab" class="risk-tabs">
        <el-tab-pane label="风险事件审核" name="events">
          <div class="tab-content risk-events-content">
            <AppSectionCard title="待处理风险事件" desc="按公司、类型、等级和审核状态快速缩小范围，减少表格视觉噪音。" shadow="never">
              <AppToolbar>
                <el-form :inline="true" class="admin-form-row">
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
                    <el-button type="primary" @click="applyFilters" :loading="isEventsLoading">查询</el-button>
                    <el-button @click="resetFilters" :disabled="isEventsLoading">重置</el-button>
                  </el-form-item>
                </el-form>
              </AppToolbar>

              <el-alert v-if="eventsErrorMsg" :title="eventsErrorMsg" type="error" show-icon :closable="false" />

              <el-table v-else :data="events" stripe style="width: 100%" v-loading="isEventsLoading">
                <el-table-column prop="company_name" label="公司名" min-width="160">
                  <template #default="scope">
                    <span class="company-name">{{ scope.row.company_name || '未知公司' }}</span>
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
                      {{ (scope.row.risk_level || 'unknown').toUpperCase() }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="事件时间" min-width="180">
                  <template #default="scope">
                    <span class="muted-text">{{ formatDate(scope.row.event_date || scope.row.created_at) }}</span>
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
                    <div v-if="((scope.row.review_status || 'pending').toLowerCase() === 'pending')" class="inline-actions">
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
            </AppSectionCard>
          </div>
        </el-tab-pane>

        <el-tab-pane label="风险报告生成" name="reports">
          <div class="tab-content risk-reports-content">
            <AppSectionCard title="生成风险报告" desc="支持按公司或时间区间生成，便于给管理层或业务侧直接复用。" shadow="never">
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
            </AppSectionCard>

            <el-card v-if="generatedReport" class="report-result ui-card" shadow="never">
              <div class="report-header">
                <h2>{{ generatedReport.title }}</h2>
                <div class="report-meta">
                  <span class="meta-item">生成时间: {{ formatDate(generatedReport.created_at || generatedReport.generated_at) }}</span>
                  <span class="meta-item">包含事件数: {{ generatedReport.source_metadata?.event_count || 0 }}</span>
                  <span v-if="generatedReport.source_metadata?.document_ids" class="meta-item">涉及文档数: {{ generatedReport.source_metadata.document_ids.length }}</span>
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
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.risk-summary-shell { min-height: 760px; }
.tab-content { display: flex; flex-direction: column; gap: 22px; }
.company-name { font-weight: 700; white-space: nowrap; color: #1e293b; }
.summary-text { font-weight: 600; color: #334155; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.risk-reports-content { gap: 22px; }
.risk-report-form :deep(.el-date-editor),
.risk-report-form :deep(.el-input) { width: 100%; max-width: 360px; }
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
  .report-result { padding: 20px; }
}
</style>
