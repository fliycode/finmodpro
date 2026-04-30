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
import AdminChart from "./admin/AdminChart.vue";
import AppIcon from "./ui/AppIcon.vue";

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

const riskLevelDist = computed(() => analytics.value.risk_level_distribution || []);
const riskTypeDist = computed(() => analytics.value.risk_type_distribution || []);
const topCompanies = computed(() => analytics.value.top_companies || []);

const highRiskEvents = computed(() =>
  events.value
    .filter((e) => e.risk_level === "high" || e.risk_level === "critical")
    .slice(0, 5)
);

const sourceDocument = computed(() => {
  const docId = events.value[0]?.document_id;
  const companyName = events.value[0]?.company_name || "未知公司";
  return { id: docId, title: `${companyName}年度报告.pdf`, company: companyName, size: "23.4 MB", date: "2024-03-20" };
});

const riskLevelCounts = computed(() => {
  const map = { high: 0, medium: 0, low: 0, critical: 0 };
  riskLevelDist.value.forEach((item) => {
    map[item.key] = (map[item.key] || 0) + item.value;
  });
  return map;
});

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
  const texts = { pending: "待审核", approved: "已确认", rejected: "已忽略" };
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
    chips.push({ key: "document", label: `文档: ${String(item.document_id)}` });
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

const getRiskLevelClass = (level) => {
  if (level === "high" || level === "critical") return "lv-high";
  if (level === "medium") return "lv-mid";
  return "lv-low";
};

const getRiskLevelText = (level) => {
  if (level === "critical") return "严重";
  if (level === "high") return "高";
  if (level === "medium") return "中";
  return "低";
};

const getRiskIconClass = (riskType, index) => {
  const classes = ["ri-red", "ri-orange", "ri-blue", "ri-green", "ri-purple", "ri-blue", "ri-brown", "ri-blue"];
  return classes[index % classes.length];
};

const getRiskTagClass = (index) => {
  const classes = ["tag-red", "tag-orange", "tag-blue", "tag-cyan"];
  return classes[index % classes.length];
};

const trendNodes = computed(() => {
  const trend = analytics.value.trend || [];
  return trend.slice(-4).map((item) => ({
    date: item.key || item.date,
    label: item.label || "",
    count: item.value || item.count || 0,
    active: item === trend[trend.length - 1],
  }));
});

const activeStep = ref(1);

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

const visibleEvents = computed(() => events.value.slice(0, 20));
</script>

<template>
  <div class="risk-shell">
    <!-- Hero -->
    <header class="risk-hero">
      <div class="risk-hero__icon">
        <div class="risk-hero__glow" />
        <div class="risk-hero__shield">
          <AppIcon name="shield" :size="22" />
        </div>
      </div>
      <div class="risk-hero__titles">
        <h1>风险信息提取</h1>
        <p>智能识别文档中的风险要素，结构化呈现关键信息</p>
      </div>
    </header>

    <!-- 2-Column Layout -->
    <div class="risk-layout">
      <!-- LEFT COLUMN -->
      <div class="risk-left">
        <!-- Document Source -->
        <section class="risk-card risk-source">
          <h3 class="risk-card__title">文档来源</h3>
          <div class="risk-source__file">
            <div class="risk-source__info">
              <div class="risk-source__pdf-badge">PDF</div>
              <div>
                <strong>{{ sourceDocument.title }}</strong>
                <p>PDF · {{ sourceDocument.size }} · {{ sourceDocument.date }}</p>
              </div>
            </div>
            <button type="button" class="risk-source__upload">重新上传</button>
          </div>
        </section>

        <!-- Steps -->
        <div class="risk-steps">
          <div
            v-for="(step, i) in [{ n: 1, label: '风险识别' }, { n: 2, label: '信息提取' }, { n: 3, label: '风险总结' }]"
            :key="step.n"
            class="risk-step"
            :class="{ 'risk-step--active': activeStep >= step.n }"
            @click="activeStep = step.n"
          >
            <span class="risk-step__num">{{ step.n }}</span>
            {{ step.label }}
          </div>
        </div>

        <!-- Work Area: Doc Viewer + Extraction -->
        <div class="risk-work">
          <!-- Document Panel -->
          <div class="risk-doc">
            <div class="risk-doc__top">
              <span>已识别 {{ riskTypeDist.length }} 类风险，共 {{ analytics.summary.total_events }} 条风险信息</span>
              <span class="risk-doc__pager">
                <button class="risk-pager-btn">&lt;</button>
                <span class="risk-pager-num">{{ events.length ? `1 / ${Math.max(1, Math.ceil(events.length / 5))}` : '- / -' }}</span>
                <button class="risk-pager-btn">&gt;</button>
              </span>
            </div>
            <div class="risk-doc__body">
              <div class="risk-doc__page">
                <h3>风险因素分析</h3>
                <p>基于已提取的风险事件，以下列出主要风险类别及证据：</p>
                <template v-for="(group, gi) in riskTypeDist.slice(0, 5)" :key="group.key">
                  <h4>{{ gi + 1 }}. {{ group.key }}</h4>
                  <p class="risk-doc__hl" :class="`risk-doc__hl--${gi}`">
                    {{ events.filter(e => e.risk_type === group.key).slice(0, 1).map(e => e.evidence_text || e.summary).join('') || '暂无证据文本。' }}
                  </p>
                </template>
                <p v-if="riskTypeDist.length === 0" class="risk-doc__empty">
                  暂无风险数据。上传文档并执行提取后，风险信息将在此展示。
                </p>
              </div>
            </div>
          </div>

          <!-- Extraction Panel -->
          <div class="risk-extract">
            <div class="risk-extract__head">
              <div class="risk-extract__tabs">
                <span class="risk-extract__tab risk-extract__tab--active">提取结果</span>
                <span class="risk-extract__tab">原文片段</span>
              </div>
              <div class="risk-extract__actions">
                <span>高亮显示</span>
                <span class="risk-extract__toggle" />
                <button type="button" class="risk-extract__export" @click="downloadGeneratedReport('json')">
                  <AppIcon name="download" :size="13" /> 导出结果
                </button>
              </div>
            </div>

            <div class="risk-extract__list">
              <div
                v-for="(item, index) in riskTypeDist"
                :key="item.key"
                class="risk-extract__item"
                :class="{ 'risk-extract__item--active': index === 0 }"
              >
                <div class="risk-extract__icon" :class="getRiskIconClass(item.key, index)">
                  <AppIcon name="alert-triangle" :size="15" />
                </div>
                <div class="risk-extract__body">
                  <div class="risk-extract__name">{{ item.key }}</div>
                  <div class="risk-extract__desc">
                    {{ events.filter(e => e.risk_type === item.key).slice(0, 1).map(e => e.summary).join('') || '暂无描述' }}
                  </div>
                </div>
                <div class="risk-extract__count">
                  {{ item.value }} 条信息
                  <span class="risk-extract__level" :class="getRiskLevelClass(item.key)">
                    {{ getRiskLevelText(item.key) }}
                  </span>
                </div>
                <span class="risk-extract__chev">&gt;</span>
              </div>
              <div v-if="riskTypeDist.length === 0" class="risk-extract__empty">
                等待风险提取完成...
              </div>
            </div>
          </div>
        </div>

        <!-- Timeline -->
        <section class="risk-card risk-timeline">
          <h3 class="risk-card__title">风险信息时间轴</h3>
          <div class="risk-timeline__track">
            <button class="risk-timeline__arrow">&lt;</button>
            <template v-for="(node, i) in trendNodes" :key="i">
              <div class="risk-timeline__node" :class="{ 'risk-timeline__node--active': node.active }">
                <strong>{{ node.date }}</strong>
                <span>{{ node.label || '报告期' }}</span>
                <span>识别出 {{ node.count }} 条风险</span>
              </div>
            </template>
            <div v-if="trendNodes.length === 0" class="risk-timeline__empty">
              暂无时间轴数据。
            </div>
            <button class="risk-timeline__arrow">&gt;</button>
          </div>
        </section>
      </div>

      <!-- RIGHT COLUMN -->
      <div class="risk-right">
        <!-- Risk Overview -->
        <section class="risk-card risk-overview">
          <div class="risk-card__head">
            <h3 class="risk-card__title">风险概览</h3>
            <span class="risk-card__update">更新时间：{{ formatDate(new Date().toISOString()) }}</span>
          </div>

          <div v-if="analyticsErrorMsg" class="risk-notice risk-notice--error">{{ analyticsErrorMsg }}</div>

          <div v-else class="risk-overview__body" v-loading="isAnalyticsLoading">
            <div class="risk-overview__total">
              <div class="risk-overview__num">{{ analytics.summary.total_events }}</div>
              <p>风险信息总数</p>
            </div>
            <div class="risk-overview__donut-area">
              <div class="risk-overview__donut" :style="{
                background: `conic-gradient(#e94c59 0 ${riskLevelCounts.high + riskLevelCounts.critical > 0 ? Math.round((riskLevelCounts.high + riskLevelCounts.critical) / Math.max(analytics.summary.total_events, 1) * 100) : 0}%, #f0a51a ${riskLevelCounts.high + riskLevelCounts.critical > 0 ? Math.round((riskLevelCounts.high + riskLevelCounts.critical) / Math.max(analytics.summary.total_events, 1) * 100) : 0}% ${riskLevelCounts.medium > 0 ? Math.round((riskLevelCounts.high + riskLevelCounts.critical + riskLevelCounts.medium) / Math.max(analytics.summary.total_events, 1) * 100) : 0}%, #2f7bff ${riskLevelCounts.medium > 0 ? Math.round((riskLevelCounts.high + riskLevelCounts.critical + riskLevelCounts.medium) / Math.max(analytics.summary.total_events, 1) * 100) : 0}% 100%)`
              }" />
              <div class="risk-overview__legend">
                <div><span class="risk-dot" style="background:#e94c59" />高风险　{{ riskLevelCounts.high + riskLevelCounts.critical }} ({{ analytics.summary.total_events > 0 ? Math.round((riskLevelCounts.high + riskLevelCounts.critical) / analytics.summary.total_events * 100) : 0 }}%)</div>
                <div><span class="risk-dot" style="background:#f0a51a" />中风险　{{ riskLevelCounts.medium }} ({{ analytics.summary.total_events > 0 ? Math.round(riskLevelCounts.medium / analytics.summary.total_events * 100) : 0 }}%)</div>
                <div><span class="risk-dot" style="background:#2f7bff" />低风险　{{ riskLevelCounts.low }} ({{ analytics.summary.total_events > 0 ? Math.round(riskLevelCounts.low / analytics.summary.total_events * 100) : 0 }}%)</div>
              </div>
            </div>
          </div>

          <div class="risk-overview__metrics">
            <div class="risk-metric">
              <strong>{{ riskTypeDist.length }}</strong>
              <span>风险类别</span>
            </div>
            <div class="risk-metric">
              <strong>{{ analytics.summary.total_events }}</strong>
              <span>风险信息</span>
            </div>
            <div class="risk-metric">
              <strong>{{ analytics.summary.pending_reviews }}</strong>
              <span>待审核</span>
            </div>
          </div>
        </section>

        <!-- Bar Chart -->
        <section class="risk-card risk-bar">
          <h3 class="risk-card__title">风险等级分布</h3>
          <div class="risk-bar__chart">
            <AdminChart :option="riskLevelOption" height="200px" v-if="riskLevelDist.length > 0" />
            <div v-else class="risk-bar__empty">暂无等级分布数据</div>
          </div>
        </section>

        <!-- TOP5 High Risks -->
        <section class="risk-card risk-top">
          <div class="risk-card__head">
            <h3 class="risk-card__title">高风险信息 TOP5</h3>
            <button type="button" class="risk-card__see-all">查看全部</button>
          </div>
          <div class="risk-top__list">
            <div
              v-for="(event, index) in highRiskEvents"
              :key="event.id || index"
              class="risk-top__item"
            >
              <div class="risk-top__rank">{{ index + 1 }}</div>
              <div class="risk-top__text">{{ event.summary || event.evidence_text || '无描述' }}</div>
              <div class="risk-top__tags">
                <span class="risk-top__tag" :class="getRiskTagClass(index)">{{ event.risk_type }}</span>
                <span class="risk-top__page">{{ event.document_id ? `P.${event.document_id}` : '' }}</span>
              </div>
            </div>
            <div v-if="highRiskEvents.length === 0" class="risk-top__empty">
              暂无高风险事件。
            </div>
          </div>
        </section>

        <!-- Export -->
        <section class="risk-card risk-export-card">
          <h3 class="risk-card__title">导出与分享</h3>
          <div class="risk-export__grid">
            <button type="button" class="risk-export__btn" @click="downloadGeneratedReport('markdown')" :disabled="!generatedReport">
              <AppIcon name="download" :size="16" />
              <div>导出结构化数据<span>Excel / CSV</span></div>
            </button>
            <button type="button" class="risk-export__btn" @click="generateReport">
              <AppIcon name="file-text" :size="16" />
              <div>生成风险报告<span>PDF 报告</span></div>
            </button>
            <button type="button" class="risk-export__btn">
              <AppIcon name="external-link" :size="16" />
              <div>分享结果<span>创建分享链接</span></div>
            </button>
          </div>
        </section>
      </div>
    </div>

    <!-- Events Table & Filters -->
    <section class="risk-card risk-events">
      <div class="risk-card__head">
        <h3 class="risk-card__title">待处理风险事件</h3>
        <span class="risk-card__count">{{ events.length }} 条</span>
      </div>

      <el-form :inline="true" class="risk-filter-row">
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
          <el-button type="primary" @click="applyFilters" :loading="isEventsLoading">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="eventsErrorMsg" :title="eventsErrorMsg" type="error" show-icon :closable="false" />

      <div v-else class="risk-events__table-wrap">
        <el-table :data="visibleEvents" stripe style="width: 100%" v-loading="isEventsLoading" size="small">
          <el-table-column prop="company_name" label="公司名" min-width="160" />
          <el-table-column prop="risk_type" label="风险类型" width="140">
            <template #default="scope">
              <el-tag effect="plain" size="small">{{ scope.row.risk_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险等级" width="110">
            <template #default="scope">
              <el-tag :type="getRiskTagType(scope.row.risk_level)" size="small">
                {{ (scope.row.risk_level || "unknown").toUpperCase() }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="事件时间" min-width="170">
            <template #default="scope">
              {{ formatDate(scope.row.event_time || scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="280">
            <template #default="scope">
              <div class="risk-events__summary">{{ scope.row.summary }}</div>
              <div v-if="scope.row.evidence_text" class="risk-events__evidence">"{{ scope.row.evidence_text }}"</div>
            </template>
          </el-table-column>
          <el-table-column label="审核状态" width="100">
            <template #default="scope">
              <el-tag :type="getReviewTagType((scope.row.review_status || 'pending').toLowerCase())" size="small">
                {{ getReviewStatusText(scope.row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="scope">
              <template v-if="(scope.row.review_status || 'pending').toLowerCase() === 'pending'">
                <el-button type="success" plain size="small" @click="handleReview(scope.row, 'approved')">确认</el-button>
                <el-button type="danger" plain size="small" @click="handleReview(scope.row, 'rejected')">忽略</el-button>
              </template>
              <span v-else class="risk-events__no-action">-</span>
            </template>
          </el-table-column>
          <template #empty>暂无风险事件。</template>
        </el-table>
      </div>
    </section>

    <!-- Generated Report -->
    <section v-if="generatedReport" class="risk-card risk-report-result">
      <div class="risk-report-result__header">
        <h2>{{ generatedReport.title }}</h2>
        <div class="risk-report-result__meta">
          <span>生成时间: {{ formatDate(generatedReport.created_at || generatedReport.generated_at) }}</span>
          <span>事件数: {{ generatedReport.source_metadata?.event_count || 0 }}</span>
        </div>
      </div>
      <div class="risk-report-result__summary">
        <h3>高管摘要</h3>
        <p>{{ generatedReport.summary }}</p>
      </div>
      <div class="risk-report-result__content">
        <h3>报告详情</h3>
        <div class="risk-report-result__body">{{ generatedReport.content }}</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ============================================
   Risk Shell - Dark Navy Dashboard
   ============================================ */

.risk-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

/* ---- Hero ---- */

.risk-hero {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  border: 1px solid rgba(233, 76, 89, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 19, 38, 0.94), rgba(7, 14, 28, 0.94)),
    radial-gradient(circle at top right, rgba(233, 76, 89, 0.1), transparent 38%);
  box-shadow: 0 20px 48px -32px rgba(4, 10, 22, 0.88);
}

.risk-hero__icon {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.risk-hero__glow {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1.5px solid rgba(233, 76, 89, 0.25);
  background: rgba(115, 23, 58, 0.55);
  box-shadow: 0 0 28px rgba(233, 76, 89, 0.45);
}

.risk-hero__shield {
  position: absolute;
  inset: 8px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff5c62, #c9345c);
  box-shadow: inset 0 2px 6px rgba(255,255,255,0.24), 0 0 18px rgba(233, 76, 89, 0.4);
  color: #fff;
}

.risk-hero__titles { flex: 1; min-width: 0; }
.risk-hero__titles h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #f4f7ff;
}
.risk-hero__titles p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8597bb;
}

/* ---- Layout ---- */

.risk-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.75fr);
  gap: 14px;
  min-height: 0;
}

.risk-left,
.risk-right {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

/* ---- Cards ---- */

.risk-card {
  border: 1px solid rgba(66, 108, 255, 0.14);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(10, 19, 38, 0.9), rgba(7, 14, 28, 0.9)),
    radial-gradient(circle at top right, rgba(71, 94, 255, 0.06), transparent 36%);
  box-shadow: 0 20px 48px -36px rgba(4, 10, 22, 0.84);
  padding: 16px 18px;
  overflow: hidden;
}

.risk-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #edf4ff;
  letter-spacing: 0.01em;
}

.risk-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.risk-card__head .risk-card__title { margin-bottom: 0; }

.risk-card__update {
  font-size: 11px;
  color: #75839b;
}

.risk-card__count {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid rgba(93, 130, 255, 0.2);
  background: rgba(49, 68, 130, 0.22);
  color: #a9beff;
  font-size: 12px;
  font-weight: 700;
}

.risk-card__see-all {
  border: 0;
  background: transparent;
  color: #6e7d95;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

/* ---- Document Source ---- */

.risk-source__file {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(8, 17, 34, 0.82);
  border: 1px solid rgba(111, 144, 205, 0.16);
}

.risk-source__info {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.risk-source__pdf-badge {
  width: 31px;
  height: 35px;
  border-radius: 5px;
  background: linear-gradient(180deg, #e35a55, #b9292e);
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 10px;
  font-weight: 900;
  flex-shrink: 0;
  position: relative;
}

.risk-source__pdf-badge::before {
  content: "";
  position: absolute;
  right: 0;
  top: 0;
  border-left: 8px solid transparent;
  border-bottom: 8px solid rgba(255,255,255,.25);
}

.risk-source__info strong {
  font-size: 14px;
  color: #edf4ff;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-source__info p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8592aa;
}

.risk-source__upload {
  height: 34px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid rgba(84, 127, 255, 0.32);
  background: #123a9c;
  color: #b7caff;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
}

/* ---- Steps ---- */

.risk-steps {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(111, 144, 205, 0.15);
}

.risk-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 700;
  color: #7987a0;
  background: rgba(9, 18, 35, 0.85);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
}

.risk-step--active {
  color: #fff;
  background: linear-gradient(90deg, rgba(233, 76, 89, 0.32), rgba(13, 27, 55, 0.72));
}

.risk-step__num {
  width: 27px;
  height: 27px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(80, 99, 136, 0.32);
  border: 1px solid rgba(125, 151, 203, 0.17);
  color: #92a0b8;
  font-weight: 800;
  font-size: 13px;
  flex-shrink: 0;
}

.risk-step--active .risk-step__num {
  color: #fff;
  background: #e94c59;
  border-color: rgba(233, 76, 89, 0.5);
  box-shadow: 0 0 16px rgba(233, 76, 89, 0.4);
}

/* ---- Work Area ---- */

.risk-work {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 14px;
}

/* Document Panel */

.risk-doc {
  border-radius: 10px;
  border: 1px solid rgba(111, 144, 205, 0.14);
  background: rgba(9, 18, 35, 0.85);
  overflow: hidden;
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

.risk-doc__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 14px;
  border-bottom: 1px solid rgba(111, 144, 205, 0.12);
  background: rgba(9, 18, 35, 0.65);
  color: #8492ac;
  font-size: 12px;
}

.risk-doc__pager {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.risk-pager-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: rgba(21, 35, 61, 0.92);
  border: 1px solid rgba(117, 149, 205, 0.12);
  display: grid;
  place-items: center;
  color: #8290a9;
  cursor: pointer;
  font-size: 14px;
}

.risk-pager-num {
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(31, 43, 72, 0.8);
  color: #a9b6ce;
  font-size: 12px;
  font-weight: 700;
}

.risk-doc__body {
  flex: 1;
  padding: 16px 18px;
  background:
    linear-gradient(90deg, rgba(255,255,255,.03) 0 8px, transparent 8px calc(100% - 8px), rgba(255,255,255,.03) calc(100% - 8px)),
    #081529;
  overflow-y: auto;
}

.risk-doc__page {
  max-width: 100%;
  background: #f6f7fb;
  color: #202633;
  border-radius: 3px;
  box-shadow: 0 14px 24px rgba(0,0,0,.38);
  padding: 28px 36px;
  font-size: 13px;
  line-height: 1.7;
}

.risk-doc__page h3 { font-size: 17px; margin: 0 0 4px; color: #111; }
.risk-doc__page h4 { font-size: 14px; margin: 12px 0 4px; color: #222; }
.risk-doc__page p { margin: 0 0 8px; }

.risk-doc__hl {
  border-radius: 3px;
  padding: 4px 6px;
  font-weight: 600;
  margin-bottom: 8px;
  display: block;
}

.risk-doc__hl--0 { background: rgba(234, 72, 92, 0.28); }
.risk-doc__hl--1 { background: rgba(240, 165, 26, 0.36); }
.risk-doc__hl--2 { background: rgba(47, 111, 255, 0.26); }
.risk-doc__hl--3 { background: rgba(33, 173, 122, 0.28); }
.risk-doc__hl--4 { background: rgba(129, 87, 246, 0.24); }

.risk-doc__empty {
  color: #8592aa;
  text-align: center;
  padding: 40px 20px;
}

/* Extraction Panel */

.risk-extract {
  border-radius: 10px;
  border: 1px solid rgba(111, 144, 205, 0.14);
  background: rgba(9, 18, 35, 0.85);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.risk-extract__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid rgba(111, 144, 205, 0.13);
  background: rgba(9, 18, 35, 0.55);
}

.risk-extract__tabs {
  display: flex;
  gap: 18px;
}

.risk-extract__tab {
  padding: 12px 0;
  font-size: 13px;
  font-weight: 800;
  color: #8794ad;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s;
}

.risk-extract__tab--active {
  color: #eaf2ff;
  border-bottom-color: #e94c59;
}

.risk-extract__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  color: #8492aa;
  font-size: 12px;
}

.risk-extract__toggle {
  width: 34px;
  height: 18px;
  background: #e94c59;
  border-radius: 9px;
  position: relative;
  cursor: pointer;
}

.risk-extract__toggle::after {
  content: "";
  position: absolute;
  right: 2px;
  top: 2px;
  width: 14px;
  height: 14px;
  background: #fff;
  border-radius: 50%;
}

.risk-extract__export {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border: 1px solid rgba(111, 144, 205, 0.16);
  background: rgba(16, 31, 58, 0.9);
  border-radius: 6px;
  color: #a9b6cf;
  font-size: 12px;
  cursor: pointer;
}

/* Risk Items */

.risk-extract__list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 10px 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.risk-extract__item {
  display: grid;
  grid-template-columns: 32px 1fr auto 16px;
  align-items: center;
  gap: 8px;
  padding: 10px 10px;
  border-radius: 9px;
  border: 1px solid rgba(111, 144, 205, 0.08);
  background: rgba(14, 28, 53, 0.75);
}

.risk-extract__item--active {
  border-color: rgba(233, 76, 89, 0.4);
  background: rgba(21, 39, 74, 0.82);
}

.risk-extract__icon {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  display: grid;
  place-items: center;
}

.ri-red { background: rgba(234,72,92,.12); color: #e94c59; border: 1px solid rgba(234,72,92,.28); }
.ri-orange { background: rgba(240,165,26,.12); color: #f0a51a; border: 1px solid rgba(240,165,26,.26); }
.ri-blue { background: rgba(47,111,255,.12); color: #2f7bff; border: 1px solid rgba(47,111,255,.26); }
.ri-green { background: rgba(33,173,122,.12); color: #21ad7a; border: 1px solid rgba(33,173,122,.26); }
.ri-purple { background: rgba(129,87,246,.12); color: #8157f6; border: 1px solid rgba(129,87,246,.26); }
.ri-brown { background: rgba(190,115,76,.12); color: #bd7951; border: 1px solid rgba(190,115,76,.26); }

.risk-extract__body { min-width: 0; }
.risk-extract__name {
  font-size: 13px;
  color: #ebf2ff;
  font-weight: 800;
  margin-bottom: 3px;
}
.risk-extract__desc {
  font-size: 11px;
  color: #8190aa;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-extract__count {
  font-size: 11px;
  color: #95a4be;
  text-align: right;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.risk-extract__level {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 900;
}

.lv-high { color: #ff6f78; background: rgba(234,72,92,.13); }
.lv-mid { color: #f3b236; background: rgba(240,165,26,.13); }
.lv-low { color: #4ea0ff; background: rgba(47,111,255,.13); }

.risk-extract__chev { color: #8fa1bf; font-size: 14px; }
.risk-extract__empty { padding: 20px; text-align: center; color: #6f7e9c; font-size: 13px; }

/* ---- Timeline ---- */

.risk-timeline__track {
  display: grid;
  grid-template-columns: 36px repeat(auto-fit, minmax(0, 1fr)) 36px;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding: 12px 10px;
  border-radius: 10px;
  background: rgba(9, 18, 35, 0.6);
  border: 1px solid rgba(111, 144, 205, 0.07);
  overflow-x: auto;
}

.risk-timeline__arrow {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  color: #8c9db9;
  background: rgba(19, 35, 62, 0.9);
  border: 1px solid rgba(111, 144, 205, 0.12);
  cursor: pointer;
  font-size: 18px;
  flex-shrink: 0;
}

.risk-timeline__node {
  border-left: 2px solid #356be8;
  padding: 10px 14px;
  min-width: 140px;
}

.risk-timeline__node::before {
  content: "";
  display: block;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #102040;
  border: 2px solid #76a2ff;
  margin-left: -21.5px;
  margin-bottom: 8px;
  box-shadow: 0 0 14px rgba(80,130,255,.7);
}

.risk-timeline__node--active::before {
  border-color: #e94c59;
  box-shadow: 0 0 14px rgba(233,76,89,.7);
}

.risk-timeline__node strong {
  display: block;
  color: #dbe6ff;
  font-size: 13px;
  margin-bottom: 4px;
}

.risk-timeline__node span {
  display: block;
  color: #8290a8;
  font-size: 11px;
  line-height: 1.6;
}

.risk-timeline__node--active strong { color: #ff8a94; }
.risk-timeline__empty { padding: 20px; color: #6f7e9c; text-align: center; font-size: 13px; grid-column: 1/-1; }

/* ---- Overview ---- */

.risk-overview__body {
  display: grid;
  grid-template-columns: 120px 1fr;
  align-items: center;
  gap: 10px;
  min-height: 100px;
}

.risk-overview__total { text-align: center; }

.risk-overview__num {
  font-size: 42px;
  line-height: 1;
  color: #83a7ff;
  font-weight: 900;
  letter-spacing: 1px;
}

.risk-overview__total p {
  margin: 6px 0 0;
  color: #8190aa;
  font-size: 13px;
  font-weight: 700;
}

.risk-overview__donut-area {
  display: flex;
  align-items: center;
  gap: 18px;
}

.risk-overview__donut {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
}

.risk-overview__donut::after {
  content: "";
  position: absolute;
  inset: 20px;
  border-radius: 50%;
  background: #0d1a31;
  box-shadow: inset 0 0 8px rgba(0,0,0,.4);
}

.risk-overview__legend {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #a2afc6;
  font-size: 12px;
  font-weight: 700;
}

.risk-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 7px;
}

.risk-overview__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-top: 14px;
}

.risk-metric {
  border-radius: 9px;
  background: rgba(17, 33, 61, 0.82);
  display: grid;
  place-items: center;
  padding: 12px 8px;
}

.risk-metric strong {
  font-size: 24px;
  color: #7fa5ff;
  font-weight: 900;
}

.risk-metric span {
  margin-top: 4px;
  font-size: 12px;
  color: #8492ac;
  font-weight: 700;
}

/* ---- Bar Chart ---- */

.risk-bar__chart {
  margin-top: 8px;
  min-height: 200px;
}

.risk-bar__empty {
  display: grid;
  place-items: center;
  min-height: 160px;
  color: #6f7e9c;
  font-size: 13px;
}

.risk-notice {
  padding: 10px 14px;
  border-radius: 9px;
  font-size: 13px;
  margin-bottom: 12px;
}

.risk-notice--error {
  border: 1px solid rgba(224, 92, 120, 0.22);
  background: rgba(51, 18, 34, 0.78);
  color: #ffb4c1;
}

/* ---- TOP5 ---- */

.risk-top__list {
  display: flex;
  flex-direction: column;
}

.risk-top__item {
  display: grid;
  grid-template-columns: 22px 1fr auto;
  align-items: start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(111, 144, 205, 0.08);
}

.risk-top__item:last-child { border-bottom: 0; }

.risk-top__rank {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(234, 72, 92, 0.14);
  color: #ff6470;
  font-size: 11px;
  font-weight: 900;
  margin-top: 1px;
}

.risk-top__text {
  font-size: 12px;
  color: #a6b4cb;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.risk-top__tags {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}

.risk-top__tag {
  padding: 3px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}

.tag-red { color: #ff6974; background: rgba(234,72,92,.13); }
.tag-orange { color: #f3ae2a; background: rgba(240,165,26,.13); }
.tag-blue { color: #4fa1ff; background: rgba(47,111,255,.13); }
.tag-cyan { color: #28b7e8; background: rgba(40,183,232,.13); }

.risk-top__page {
  font-size: 11px;
  color: #7d8ba3;
  white-space: nowrap;
}

.risk-top__empty {
  padding: 20px;
  text-align: center;
  color: #6f7e9c;
  font-size: 13px;
}

/* ---- Export ---- */

.risk-export__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 12px;
}

.risk-export__btn {
  display: grid;
  grid-template-columns: 24px 1fr;
  align-items: center;
  gap: 10px;
  padding: 14px 12px;
  border-radius: 10px;
  border: 1px solid rgba(111, 144, 205, 0.12);
  background: rgba(12, 24, 45, 0.82);
  color: #dbe7ff;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, background 0.2s;
}

.risk-export__btn:hover:not(:disabled) {
  border-color: rgba(102, 138, 255, 0.24);
  background: rgba(15, 28, 52, 0.9);
}

.risk-export__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.risk-export__btn span {
  display: block;
  margin-top: 4px;
  color: #75839a;
  font-size: 11px;
  font-weight: 600;
}

/* ---- Events Table ---- */

.risk-events {
  margin-top: 0;
}

.risk-filter-row {
  margin: 14px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.risk-events__table-wrap {
  overflow-x: auto;
}

.risk-events__summary {
  font-weight: 600;
  color: #d8e5ff;
  font-size: 13px;
}

.risk-events__evidence {
  font-size: 12px;
  color: #8592aa;
  margin-top: 4px;
  line-height: 1.5;
}

.risk-events__no-action {
  color: #6f7e9c;
  font-size: 13px;
}

/* ---- Report Result ---- */

.risk-report-result {
  padding: 24px;
}

.risk-report-result__header {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.1);
}

.risk-report-result__header h2 {
  margin: 0 0 8px;
  color: #f4f7ff;
  font-size: 20px;
}

.risk-report-result__meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #75839b;
}

.risk-report-result__summary,
.risk-report-result__content {
  margin-bottom: 18px;
}

.risk-report-result__summary h3,
.risk-report-result__content h3 {
  margin: 0 0 10px;
  color: #c5d4f7;
  font-size: 16px;
}

.risk-report-result__summary p,
.risk-report-result__body {
  color: #b0c0e0;
  line-height: 1.75;
  white-space: pre-wrap;
  font-size: 13px;
}

/* ---- Responsive ---- */

@media (max-width: 1200px) {
  .risk-layout {
    grid-template-columns: 1fr;
  }

  .risk-work {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .risk-hero { flex-wrap: wrap; padding: 16px; }
  .risk-hero__icon { width: 48px; height: 48px; }
  .risk-hero__titles h1 { font-size: 20px; }

  .risk-export__grid {
    grid-template-columns: 1fr;
  }

  .risk-overview__body {
    grid-template-columns: 1fr;
  }

  .risk-overview__donut-area {
    justify-content: center;
  }
}
</style>
