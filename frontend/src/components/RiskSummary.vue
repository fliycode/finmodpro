<script setup>
import { computed, onMounted, ref } from "vue";
import { riskApi } from "../api/risk.js";
import { useFlash } from "../lib/flash.js";
import {
  buildRiskLevelChartOption,
  buildRiskTypeChartOption,
  buildRiskTrendChartOption,
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

const riskLevelOption = computed(() => buildRiskLevelChartOption(analytics.value));
const riskTypeOption = computed(() => buildRiskTypeChartOption(analytics.value));
const riskTrendOption = computed(() => buildRiskTrendChartOption(analytics.value));

const riskLevelDist = computed(() => analytics.value.risk_level_distribution || []);
const riskTypeDist = computed(() => analytics.value.risk_type_distribution || []);
const topCompanies = computed(() => analytics.value.top_companies || []);

const riskLevelCounts = computed(() => {
  const map = { high: 0, medium: 0, low: 0, critical: 0 };
  riskLevelDist.value.forEach((item) => {
    map[item.key] = (map[item.key] || 0) + item.value;
  });
  return map;
});

const totalEvents = computed(() => analytics.value.summary.total_events);
const highCount = computed(() => riskLevelCounts.value.high + riskLevelCounts.value.critical);
const medCount = computed(() => riskLevelCounts.value.medium);
const lowCount = computed(() => riskLevelCounts.value.low);

const highPct = computed(() => totalEvents.value > 0 ? Math.round(highCount.value / totalEvents.value * 100) : 0);
const medPct = computed(() => totalEvents.value > 0 ? Math.round(medCount.value / totalEvents.value * 100) : 0);
const lowPct = computed(() => totalEvents.value > 0 ? Math.round(lowCount.value / totalEvents.value * 100) : 0);

const donutStyle = computed(() => {
  if (totalEvents.value === 0) return {};
  const h = highPct.value;
  const m = medPct.value;
  return {
    background: `conic-gradient(#e94c59 0 ${h}%, #f0a51a ${h}% ${h + m}%, #2f7bff ${h + m}% 100%)`,
  };
});

const highRiskEvents = computed(() =>
  events.value
    .filter((e) => e.risk_level === "high" || e.risk_level === "critical")
    .slice(0, 5)
);

const trendNodes = computed(() => {
  const trend = analytics.value.trend || [];
  return trend.slice(-4).map((item, i, arr) => ({
    date: item.key || item.date || '',
    label: '',
    count: item.value || item.count || 0,
    active: i === arr.length - 1,
  }));
});

const activeStep = ref(1);
const activeExtractTab = ref('results');

/* ---- API calls ---- */

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

onMounted(() => refreshWorkspace());

const handleReview = async (event, status) => {
  try {
    await riskApi.reviewEvent(event.id || event.event_id, status);
    flash.success(`风险事件已${status === "approved" ? "确认" : "忽略"}`);
    await refreshWorkspace();
  } catch (error) {
    flash.error(error.message || "审核失败");
  }
};

const applyFilters = () => refreshWorkspace();
const resetFilters = () => { filters.value = buildDefaultFilters(); refreshWorkspace(); };

const getReviewStatusText = (s) => ({ pending: "待审核", approved: "已确认", rejected: "已忽略" }[s?.toLowerCase()] || s || "待审核");
const getRiskTagType = (l) => ({ high: "danger", critical: "danger", medium: "warning", low: "success" }[l] || "info");
const getReviewTagType = (s) => ({ approved: "success", rejected: "danger", pending: "warning" }[s] || "info");

const formatDate = (d) => { try { return d ? new Date(d).toLocaleString() : "N/A" } catch { return d } };

const getRiskLevelText = (l) => ({ critical: "严重", high: "高", medium: "中", low: "低" }[l] || l);
const getRiskLevelClass = (l) => ({ high: "lv-high", critical: "lv-high", medium: "lv-mid", low: "lv-low" }[l] || "lv-low");

const iconClasses = ["ri-red", "ri-orange", "ri-blue", "ri-green", "ri-purple", "ri-blue", "ri-brown", "ri-blue"];
const tagClasses = ["tag-red", "tag-orange", "tag-blue", "tag-cyan"];
const hlClasses = ["hl-red", "hl-orange", "hl-blue", "hl-green", "hl-purple"];

const getRiskIconCls = (i) => iconClasses[i % iconClasses.length];
const getRiskTagCls = (i) => tagClasses[i % tagClasses.length];
const getHlCls = (i) => hlClasses[i % hlClasses.length];

const sourceDoc = computed(() => {
  const e = events.value[0];
  return {
    title: `${e?.company_name || '未知公司'}年度报告.pdf`,
    company: e?.company_name || '未知公司',
    size: "23.4 MB",
    date: "2024-03-20",
  };
});

const eventsDrawerOpen = ref(false);

/* ---- Report ---- */

const reportType = ref("company");
const isReportLoading = ref(false);
const isReportExporting = ref(false);
const reportErrorMsg = ref("");
const generatedReport = ref(null);
const reportForm = ref({ company_name: "", period_start: "", period_end: "" });

const generateReport = async () => {
  isReportLoading.value = true;
  reportErrorMsg.value = "";
  generatedReport.value = null;
  try {
    let data;
    if (reportType.value === "company") {
      if (!reportForm.value.company_name) throw new Error("请输入公司名称");
      data = await riskApi.generateCompanyReport({ company_name: reportForm.value.company_name, period_start: reportForm.value.period_start || undefined, period_end: reportForm.value.period_end || undefined });
    } else {
      if (!reportForm.value.period_start || !reportForm.value.period_end) throw new Error("请输入开始和结束日期");
      data = await riskApi.generateTimeRangeReport({ period_start: reportForm.value.period_start, period_end: reportForm.value.period_end });
    }
    generatedReport.value = data.data?.report || data.report || data;
    flash.success("风险报告生成成功");
    await fetchAnalytics();
  } catch (error) {
    reportErrorMsg.value = error.message || "生成报告失败";
  } finally {
    isReportLoading.value = false;
  }
};

const downloadGeneratedReport = async (format = "markdown") => {
  if (!generatedReport.value?.id) { flash.error("请先生成报告后再导出"); return; }
  isReportExporting.value = true;
  try {
    const p = await riskApi.exportReport(generatedReport.value.id, { format });
    const blob = new Blob([p.content], { type: p.contentType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = p.filename; a.click();
    window.URL.revokeObjectURL(url);
    flash.success(`已导出为 ${format === "json" ? "JSON" : "Markdown"}`);
  } catch (error) {
    flash.error(error.message || "导出失败");
  } finally {
    isReportExporting.value = false;
  }
};
</script>

<template>
  <div class="risk-stage">
    <!-- Top Bar -->
    <div class="risk-topbar">
      <div class="risk-topbar__title">
        <h2>风险信息提取</h2>
        <p>智能识别文档中的风险要素，结构化呈现关键信息</p>
      </div>
      <div class="risk-topbar__center">
        <span class="risk-topbar__badge">
          <AppIcon name="shield" :size="14" />
          已识别 {{ riskTypeDist.length }} 类风险 · {{ totalEvents }} 条信息
        </span>
      </div>
      <div class="risk-topbar__actions">
        <button type="button" class="risk-action-btn" @click="eventsDrawerOpen = true">
          <AppIcon name="search" :size="14" />
          查看全部事件
        </button>
        <button type="button" class="risk-action-btn risk-action-btn--primary" @click="refreshWorkspace" :disabled="isAnalyticsLoading">
          <AppIcon name="refresh" :size="14" />
          刷新
        </button>
      </div>
    </div>

    <!-- Main Grid -->
    <div class="risk-grid">
      <!-- LEFT COLUMN -->
      <div class="risk-left">
        <!-- Row 1: Source + Steps -->
        <div class="risk-row-top">
          <section class="risk-panel risk-source">
            <div class="risk-panel__head">
              <h3><AppIcon name="file" :size="14" /> 文档来源</h3>
            </div>
            <div class="risk-source__file">
              <div class="risk-source__info">
                <span class="risk-source__pdf">PDF</span>
                <div>
                  <strong>{{ sourceDoc.title }}</strong>
                  <p>{{ sourceDoc.size }} · {{ sourceDoc.date }}</p>
                </div>
              </div>
              <button class="risk-source__upload">重新上传</button>
            </div>
          </section>

          <div class="risk-steps">
            <div
              v-for="(s, i) in [{ n: 1, l: '风险识别' }, { n: 2, l: '信息提取' }, { n: 3, l: '风险总结' }]"
              :key="s.n"
              class="risk-step"
              :class="{ 'is-active': activeStep >= s.n }"
              @click="activeStep = s.n"
            >
              <span class="risk-step__n">{{ s.n }}</span>
              <span>{{ s.l }}</span>
            </div>
          </div>
        </div>

        <!-- Row 2: Doc Viewer + Extract List (fills remaining space) -->
        <div class="risk-work">
          <!-- Document Panel -->
          <div class="risk-doc">
            <div class="risk-doc__bar">
              <span>已识别 {{ riskTypeDist.length }} 类风险，共 {{ totalEvents }} 条风险信息</span>
              <span class="risk-doc__pager">
                <button>&lt;</button>
                <span class="risk-doc__page-num">{{ events.length ? `1 / ${Math.max(1, Math.ceil(events.length / 5))}` : '- / -' }}</span>
                <button>&gt;</button>
              </span>
            </div>
            <div class="risk-doc__page">
              <h3>风险因素分析</h3>
              <p>基于已提取的风险事件，以下列出主要风险类别及证据：</p>
              <template v-for="(group, gi) in riskTypeDist.slice(0, 5)" :key="group.key">
                <h4>{{ gi + 1 }}. {{ group.key }}</h4>
                <p class="risk-doc__hl" :class="getHlCls(gi)">
                  {{ events.filter(e => e.risk_type === group.key).slice(0, 1).map(e => e.evidence_text || e.summary).join('') || '暂无证据文本。' }}
                </p>
              </template>
              <p v-if="riskTypeDist.length === 0" class="risk-doc__empty">
                暂无风险数据。上传文档并执行提取后，风险信息将在此展示。
              </p>
            </div>
          </div>

          <!-- Extract Panel -->
          <div class="risk-extract">
            <div class="risk-extract__head">
              <div class="risk-extract__tabs">
                <button
                  :class="['risk-extract__tab', { 'is-active': activeExtractTab === 'results' }]"
                  @click="activeExtractTab = 'results'"
                >提取结果</button>
                <button
                  :class="['risk-extract__tab', { 'is-active': activeExtractTab === 'source' }]"
                  @click="activeExtractTab = 'source'"
                >原文片段</button>
              </div>
              <div class="risk-extract__tools">
                <span class="risk-extract__toggle-label">高亮</span>
                <span class="risk-extract__toggle" />
                <button class="risk-extract__download" @click="downloadGeneratedReport('json')">
                  <AppIcon name="download" :size="12" /> 导出
                </button>
              </div>
            </div>
            <div class="risk-extract__list">
              <div
                v-for="(item, i) in riskTypeDist"
                :key="item.key"
                class="risk-extract__item"
                :class="{ 'is-active': i === 0 }"
              >
                <div class="risk-extract__icon" :class="getRiskIconCls(i)">
                  <AppIcon name="alert-triangle" :size="13" />
                </div>
                <div class="risk-extract__body">
                  <div class="risk-extract__name">{{ item.key }}</div>
                  <div class="risk-extract__desc">
                    {{ events.filter(e => e.risk_type === item.key).slice(0, 1).map(e => e.summary).join('') || '暂无描述' }}
                  </div>
                </div>
                <div class="risk-extract__meta">
                  <span>{{ item.value }} 条</span>
                  <span class="risk-extract__level" :class="getRiskLevelClass(item.key)">{{ getRiskLevelText(item.key) }}</span>
                </div>
                <span class="risk-extract__chev">&rsaquo;</span>
              </div>
              <div v-if="riskTypeDist.length === 0" class="risk-extract__empty">
                等待风险提取完成...
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3: Timeline -->
        <section class="risk-panel risk-timeline">
          <div class="risk-panel__head">
            <h3><AppIcon name="history" :size="14" /> 风险信息时间轴</h3>
          </div>
          <div class="risk-timeline__track">
            <button class="risk-timeline__arr">&lsaquo;</button>
            <template v-for="(node, i) in trendNodes" :key="i">
              <div class="risk-timeline__node" :class="{ 'is-active': node.active }">
                <strong>{{ node.date }}</strong>
                <span>{{ node.label || '报告期' }}</span>
                <span>识别 {{ node.count }} 条风险</span>
              </div>
            </template>
            <div v-if="trendNodes.length === 0" class="risk-timeline__empty">暂无时间轴数据</div>
            <button class="risk-timeline__arr">&rsaquo;</button>
          </div>
        </section>
      </div>

      <!-- RIGHT COLUMN -->
      <div class="risk-right">
        <!-- Overview Card -->
        <section class="risk-panel risk-overview">
          <div class="risk-panel__head">
            <h3><AppIcon name="pie-chart" :size="14" /> 风险概览</h3>
            <span class="risk-panel__update">更新于 {{ formatDate(new Date().toISOString()) }}</span>
          </div>

          <div v-if="analyticsErrorMsg" class="risk-err">{{ analyticsErrorMsg }}</div>

          <div v-else class="risk-overview__inner" v-loading="isAnalyticsLoading">
            <div class="risk-overview__total">
              <span class="risk-overview__num">{{ totalEvents }}</span>
              <span class="risk-overview__label">风险总数</span>
            </div>
            <div class="risk-overview__chart">
              <div class="risk-overview__donut" :style="donutStyle" />
              <div class="risk-overview__legend">
                <div><i class="risk-dot" style="background:#e94c59" />高风险 {{ highCount }} ({{ highPct }}%)</div>
                <div><i class="risk-dot" style="background:#f0a51a" />中风险 {{ medCount }} ({{ medPct }}%)</div>
                <div><i class="risk-dot" style="background:#2f7bff" />低风险 {{ lowCount }} ({{ lowPct }}%)</div>
              </div>
            </div>
          </div>

          <div class="risk-overview__kpis">
            <div class="risk-kpi"><strong>{{ riskTypeDist.length }}</strong><span>风险类别</span></div>
            <div class="risk-kpi"><strong>{{ totalEvents }}</strong><span>风险信息</span></div>
            <div class="risk-kpi"><strong>{{ analytics.summary.pending_reviews }}</strong><span>待审核</span></div>
          </div>
        </section>

        <!-- Bar Chart -->
        <section class="risk-panel risk-bar">
          <div class="risk-panel__head">
            <h3><AppIcon name="bar-chart" :size="14" /> 风险等级分布</h3>
          </div>
          <div class="risk-bar__inner">
            <AdminChart v-if="riskLevelDist.length" :option="riskLevelOption" height="100%" />
            <div v-else class="risk-bar__empty">暂无数据</div>
          </div>
        </section>

        <!-- TOP5 -->
        <section class="risk-panel risk-top5">
          <div class="risk-panel__head">
            <h3><AppIcon name="alert-triangle" :size="14" /> 高风险信息 TOP5</h3>
            <button class="risk-panel__all">查看全部</button>
          </div>
          <div class="risk-top5__list">
            <div v-for="(ev, i) in highRiskEvents" :key="ev.id || i" class="risk-top5__row">
              <span class="risk-top5__rank">{{ i + 1 }}</span>
              <span class="risk-top5__text">{{ ev.summary || ev.evidence_text || '无描述' }}</span>
              <span class="risk-top5__tag" :class="getRiskTagCls(i)">{{ ev.risk_type }}</span>
            </div>
            <div v-if="highRiskEvents.length === 0" class="risk-top5__empty">暂无高风险事件</div>
          </div>
        </section>

        <!-- Export -->
        <section class="risk-panel risk-export">
          <div class="risk-panel__head">
            <h3><AppIcon name="download" :size="14" /> 导出与分享</h3>
          </div>
          <div class="risk-export__grid">
            <button class="risk-export__btn" @click="downloadGeneratedReport('markdown')" :disabled="!generatedReport">
              <AppIcon name="download" :size="15" />
              <div>数据<span>Excel / CSV</span></div>
            </button>
            <button class="risk-export__btn" @click="generateReport" :disabled="isReportLoading">
              <AppIcon name="file-text" :size="15" />
              <div>报告<span>PDF 报告</span></div>
            </button>
            <button class="risk-export__btn">
              <AppIcon name="external-link" :size="15" />
              <div>分享<span>分享链接</span></div>
            </button>
          </div>
        </section>
      </div>
    </div>

    <!-- Events Drawer -->
    <el-drawer v-model="eventsDrawerOpen" direction="rtl" size="700px" :with-header="false">
      <div class="risk-events-drawer">
        <h3>风险事件列表</h3>
        <el-form :inline="true" class="risk-filter-row">
          <el-form-item><el-input v-model="filters.company_name" placeholder="公司名称" size="small" clearable /></el-form-item>
          <el-form-item><el-input v-model="filters.risk_type" placeholder="风险类型" size="small" clearable /></el-form-item>
          <el-form-item><el-select v-model="filters.risk_level" placeholder="等级" size="small" clearable><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /><el-option label="严重" value="critical" /></el-select></el-form-item>
          <el-form-item><el-select v-model="filters.review_status" placeholder="状态" size="small" clearable><el-option label="待审核" value="pending" /><el-option label="已确认" value="approved" /><el-option label="已忽略" value="rejected" /></el-select></el-form-item>
          <el-form-item><el-button type="primary" size="small" @click="applyFilters" :loading="isEventsLoading">查询</el-button><el-button size="small" @click="resetFilters">重置</el-button></el-form-item>
        </el-form>
        <el-table :data="events" stripe size="small" v-loading="isEventsLoading" max-height="calc(100vh - 200px)">
          <el-table-column prop="company_name" label="公司" min-width="140" />
          <el-table-column prop="risk_type" label="类型" width="100"><template #default="s"><el-tag size="small" effect="plain">{{ s.row.risk_type }}</el-tag></template></el-table-column>
          <el-table-column label="等级" width="80"><template #default="s"><el-tag :type="getRiskTagType(s.row.risk_level)" size="small">{{ (s.row.risk_level || '').toUpperCase() }}</el-tag></template></el-table-column>
          <el-table-column label="时间" min-width="150"><template #default="s">{{ formatDate(s.row.event_time || s.row.created_at) }}</template></el-table-column>
          <el-table-column label="摘要" min-width="240"><template #default="s"><div class="risk-events__summary">{{ s.row.summary }}</div></template></el-table-column>
          <el-table-column label="审核" width="90"><template #default="s"><el-tag :type="getReviewTagType((s.row.review_status || 'pending').toLowerCase())" size="small">{{ getReviewStatusText(s.row.review_status) }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="140"><template #default="s"><template v-if="(s.row.review_status || 'pending').toLowerCase() === 'pending'"><el-button type="success" plain size="small" @click="handleReview(s.row, 'approved')">确认</el-button><el-button type="danger" plain size="small" @click="handleReview(s.row, 'rejected')">忽略</el-button></template><span v-else class="no-action">-</span></template></el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
/* ============================================
   RISK STAGE — viewport-fitting dense dashboard
   ============================================ */

.risk-stage {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 88px); /* fills viewport minus topbar */
  min-height: 700px;
  gap: 12px;
  overflow: hidden;
}

/* ---- Top Bar ---- */

.risk-topbar {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
  padding: 14px 18px;
  border: 1px solid rgba(233, 76, 89, 0.14);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(10, 19, 38, 0.94), rgba(7, 14, 28, 0.94)),
    radial-gradient(circle at top right, rgba(233, 76, 89, 0.08), transparent 36%);
}

.risk-topbar__title { flex: 1; min-width: 0; }
.risk-topbar__title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
  color: #f4f7ff;
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.risk-topbar__title p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #8597bb;
}

.risk-topbar__center {
  flex-shrink: 0;
}

.risk-topbar__badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(233, 76, 89, 0.18);
  background: rgba(233, 76, 89, 0.08);
  color: #ff949b;
  font-size: 12px;
  font-weight: 700;
}

.risk-topbar__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.risk-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(102, 132, 255, 0.16);
  border-radius: 8px;
  background: rgba(15, 24, 44, 0.78);
  color: #95aacd;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.2s, color 0.2s;
}
.risk-action-btn:hover { border-color: rgba(102, 138, 255, 0.28); color: #eef4ff; }
.risk-action-btn--primary {
  border-color: rgba(233, 76, 89, 0.28);
  background: linear-gradient(135deg, rgba(233, 76, 89, 0.2), rgba(180, 40, 60, 0.15));
  color: #ff949b;
}

/* ---- Main Grid ---- */

.risk-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(340px, 0.72fr);
  gap: 12px;
  overflow: hidden;
}

/* ---- Left Column ---- */

.risk-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow: hidden;
}

.risk-row-top {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  flex-shrink: 0;
}

/* ---- Panels ---- */

.risk-panel {
  border: 1px solid rgba(66, 108, 255, 0.12);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(10, 19, 38, 0.88), rgba(7, 14, 28, 0.88)),
    radial-gradient(circle at top right, rgba(71, 94, 255, 0.05), transparent 34%);
  box-shadow: 0 16px 40px -32px rgba(4, 10, 22, 0.8);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.risk-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.08);
  flex-shrink: 0;
}

.risk-panel__head h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 800;
  color: #edf4ff;
}

.risk-panel__update {
  font-size: 10px;
  color: #75839b;
}

.risk-panel__all {
  border: 0;
  background: transparent;
  font-size: 11px;
  font-weight: 700;
  color: #6e7d95;
  cursor: pointer;
}

/* ---- Source Card ---- */

.risk-source { flex: 1; }

.risk-source__file {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  flex: 1;
}

.risk-source__info {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.risk-source__pdf {
  width: 28px;
  height: 32px;
  border-radius: 4px;
  background: linear-gradient(180deg, #e35a55, #b9292e);
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 9px;
  font-weight: 900;
  flex-shrink: 0;
}

.risk-source__info strong {
  font-size: 13px;
  color: #edf4ff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.risk-source__info p {
  margin: 2px 0 0;
  font-size: 11px;
  color: #8592aa;
}

.risk-source__upload {
  height: 30px;
  padding: 0 14px;
  border-radius: 7px;
  border: 1px solid rgba(84, 127, 255, 0.28);
  background: #123a9c;
  color: #b7caff;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
}

/* ---- Steps ---- */

.risk-steps {
  display: flex;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(111, 144, 205, 0.13);
  flex-shrink: 0;
}

.risk-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 18px;
  height: 44px;
  font-size: 13px;
  font-weight: 700;
  color: #7987a0;
  background: rgba(9, 18, 35, 0.8);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
  white-space: nowrap;
}

.risk-step.is-active {
  color: #fff;
  background: linear-gradient(90deg, rgba(233, 76, 89, 0.28), rgba(13, 27, 55, 0.7));
}

.risk-step__n {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(80, 99, 136, 0.28);
  border: 1px solid rgba(125, 151, 203, 0.15);
  color: #92a0b8;
  font-weight: 800;
  font-size: 12px;
  flex-shrink: 0;
}

.risk-step.is-active .risk-step__n {
  color: #fff;
  background: #e94c59;
  border-color: rgba(233, 76, 89, 0.4);
  box-shadow: 0 0 12px rgba(233, 76, 89, 0.35);
}

/* ---- Work Area (Doc + Extract) ---- */

.risk-work {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 10px;
  overflow: hidden;
}

/* Document Panel */

.risk-doc {
  border: 1px solid rgba(111, 144, 205, 0.12);
  border-radius: 10px;
  background: rgba(9, 18, 35, 0.82);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.risk-doc__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(111, 144, 205, 0.1);
  background: rgba(9, 18, 35, 0.55);
  color: #8492ac;
  font-size: 11px;
  flex-shrink: 0;
}

.risk-doc__pager {
  display: flex;
  align-items: center;
  gap: 6px;
}

.risk-doc__pager button {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  background: rgba(21, 35, 61, 0.9);
  border: 1px solid rgba(117, 149, 205, 0.1);
  color: #8290a9;
  cursor: pointer;
  font-size: 13px;
  display: grid;
  place-items: center;
}

.risk-doc__page-num {
  padding: 2px 8px;
  border-radius: 5px;
  background: rgba(31, 43, 72, 0.75);
  color: #a9b6ce;
  font-size: 11px;
  font-weight: 700;
}

.risk-doc__page {
  flex: 1;
  overflow-y: auto;
  padding: 16px 22px;
  background: linear-gradient(90deg, rgba(255,255,255,.02) 0 6px, transparent 6px calc(100% - 6px), rgba(255,255,255,.02) calc(100% - 6px)), #081529;
  font-size: 12px;
  line-height: 1.65;
  color: #202633;
}

.risk-doc__page h3 { font-size: 15px; margin: 0 0 4px; color: #f6f7fb; }
.risk-doc__page h4 { font-size: 13px; margin: 10px 0 3px; color: #d0d8f0; }
.risk-doc__page > p { margin: 0 0 8px; color: #a0adc4; }

.risk-doc__hl {
  border-radius: 2px;
  padding: 3px 5px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #202633;
}

.hl-red { background: rgba(234, 72, 92, 0.26); }
.hl-orange { background: rgba(240, 165, 26, 0.32); }
.hl-blue { background: rgba(47, 111, 255, 0.22); }
.hl-green { background: rgba(33, 173, 122, 0.24); }
.hl-purple { background: rgba(129, 87, 246, 0.2); }

.risk-doc__empty {
  color: #8592aa;
  text-align: center;
  padding: 40px 20px;
}

/* Extract Panel */

.risk-extract {
  border: 1px solid rgba(111, 144, 205, 0.12);
  border-radius: 10px;
  background: rgba(9, 18, 35, 0.82);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.risk-extract__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid rgba(111, 144, 205, 0.1);
  background: rgba(9, 18, 35, 0.5);
  flex-shrink: 0;
}

.risk-extract__tabs {
  display: flex;
  gap: 14px;
}

.risk-extract__tab {
  padding: 9px 0;
  border: 0;
  background: transparent;
  font-size: 12px;
  font-weight: 800;
  color: #8794ad;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s;
}

.risk-extract__tab.is-active {
  color: #eaf2ff;
  border-bottom-color: #e94c59;
}

.risk-extract__tools {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 6px;
  color: #8492aa;
  font-size: 11px;
}

.risk-extract__toggle-label { font-size: 11px; }

.risk-extract__toggle {
  width: 30px;
  height: 16px;
  background: #e94c59;
  border-radius: 8px;
  position: relative;
  cursor: pointer;
}

.risk-extract__toggle::after {
  content: "";
  position: absolute;
  right: 2px;
  top: 2px;
  width: 12px;
  height: 12px;
  background: #fff;
  border-radius: 50%;
}

.risk-extract__download {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 9px;
  border: 1px solid rgba(111, 144, 205, 0.14);
  background: rgba(16, 31, 58, 0.85);
  border-radius: 5px;
  color: #a9b6cf;
  font-size: 11px;
  cursor: pointer;
}

.risk-extract__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.risk-extract__item {
  display: grid;
  grid-template-columns: 28px 1fr auto 14px;
  align-items: center;
  gap: 7px;
  padding: 8px 9px;
  border-radius: 8px;
  border: 1px solid rgba(111, 144, 205, 0.07);
  background: rgba(14, 28, 53, 0.7);
}

.risk-extract__item.is-active {
  border-color: rgba(233, 76, 89, 0.35);
  background: rgba(21, 39, 74, 0.8);
}

.risk-extract__icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: grid;
  place-items: center;
}

.ri-red { background: rgba(234,72,92,.1); color: #e94c59; border: 1px solid rgba(234,72,92,.24); }
.ri-orange { background: rgba(240,165,26,.1); color: #f0a51a; border: 1px solid rgba(240,165,26,.22); }
.ri-blue { background: rgba(47,111,255,.1); color: #2f7bff; border: 1px solid rgba(47,111,255,.22); }
.ri-green { background: rgba(33,173,122,.1); color: #21ad7a; border: 1px solid rgba(33,173,122,.22); }
.ri-purple { background: rgba(129,87,246,.1); color: #8157f6; border: 1px solid rgba(129,87,246,.22); }
.ri-brown { background: rgba(190,115,76,.1); color: #bd7951; border: 1px solid rgba(190,115,76,.22); }

.risk-extract__body { min-width: 0; }
.risk-extract__name { font-size: 12px; color: #ebf2ff; font-weight: 800; margin-bottom: 2px; }
.risk-extract__desc {
  font-size: 10.5px;
  color: #8190aa;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.risk-extract__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  font-size: 10px;
  color: #95a4be;
}

.risk-extract__level {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 900;
}

.lv-high { color: #ff6f78; background: rgba(234,72,92,.12); }
.lv-mid { color: #f3b236; background: rgba(240,165,26,.12); }
.lv-low { color: #4ea0ff; background: rgba(47,111,255,.12); }

.risk-extract__chev { color: #8fa1bf; font-size: 16px; }
.risk-extract__empty { padding: 20px; text-align: center; color: #6f7e9c; font-size: 12px; }

/* ---- Timeline ---- */

.risk-timeline { flex-shrink: 0; }

.risk-timeline__track {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  flex: 1;
}

.risk-timeline__arr {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  color: #8c9db9;
  background: rgba(19, 35, 62, 0.85);
  border: 1px solid rgba(111, 144, 205, 0.1);
  cursor: pointer;
  font-size: 20px;
  flex-shrink: 0;
}

.risk-timeline__node {
  flex: 1;
  min-width: 120px;
  border-left: 2px solid #356be8;
  padding: 6px 12px;
  position: relative;
}

.risk-timeline__node::before {
  content: "";
  position: absolute;
  left: -8px;
  top: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #102040;
  border: 2px solid #76a2ff;
  box-shadow: 0 0 10px rgba(80,130,255,.5);
}

.risk-timeline__node.is-active::before {
  border-color: #e94c59;
  box-shadow: 0 0 10px rgba(233,76,89,.5);
}

.risk-timeline__node strong {
  display: block;
  color: #dbe6ff;
  font-size: 12px;
  margin-bottom: 3px;
}

.risk-timeline__node span {
  display: block;
  color: #8290a8;
  font-size: 10.5px;
  line-height: 1.5;
}

.risk-timeline__node.is-active strong { color: #ff8a94; }
.risk-timeline__empty { padding: 20px; color: #6f7e9c; text-align: center; flex: 1; font-size: 12px; }

/* ---- RIGHT COLUMN ---- */

.risk-right {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow: hidden;
}

/* Overview */

.risk-overview { flex-shrink: 0; }

.risk-overview__inner {
  display: grid;
  grid-template-columns: 90px 1fr;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
}

.risk-overview__total {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.risk-overview__num {
  font-size: 38px;
  font-weight: 900;
  color: #83a7ff;
  line-height: 1;
}

.risk-overview__label {
  font-size: 11px;
  color: #8190aa;
  font-weight: 700;
  margin-top: 3px;
}

.risk-overview__chart {
  display: flex;
  align-items: center;
  gap: 14px;
}

.risk-overview__donut {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

.risk-overview__donut::after {
  content: "";
  position: absolute;
  inset: 16px;
  border-radius: 50%;
  background: #0d1a31;
  box-shadow: inset 0 0 6px rgba(0,0,0,.35);
}

.risk-overview__legend {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 11px;
  font-weight: 700;
  color: #a2afc6;
}

.risk-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 5px;
}

.risk-overview__kpis {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  padding: 0 14px 12px;
}

.risk-kpi {
  border-radius: 8px;
  background: rgba(17, 33, 61, 0.78);
  display: grid;
  place-items: center;
  padding: 10px 6px;
}

.risk-kpi strong {
  font-size: 22px;
  color: #7fa5ff;
  font-weight: 900;
  line-height: 1;
}

.risk-kpi span {
  margin-top: 3px;
  font-size: 10.5px;
  color: #8492ac;
  font-weight: 700;
}

.risk-err {
  margin: 10px 14px;
  padding: 9px 12px;
  border-radius: 7px;
  border: 1px solid rgba(224, 92, 120, 0.2);
  background: rgba(51, 18, 34, 0.72);
  color: #ffb4c1;
  font-size: 12px;
}

/* Bar */

.risk-bar { flex: 1; min-height: 0; }
.risk-bar__inner {
  flex: 1;
  min-height: 0;
  padding: 6px 8px;
}
.risk-bar__empty {
  display: grid;
  place-items: center;
  height: 100%;
  color: #6f7e9c;
  font-size: 12px;
}

/* TOP5 */

.risk-top5 { flex: 1; min-height: 0; }

.risk-top5__list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 8px;
}

.risk-top5__row {
  display: grid;
  grid-template-columns: 18px 1fr auto;
  align-items: start;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(111, 144, 205, 0.06);
  font-size: 11.5px;
  color: #a6b4cb;
  line-height: 1.4;
}

.risk-top5__row:last-child { border-bottom: 0; }

.risk-top5__rank {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(234, 72, 92, 0.12);
  color: #ff6470;
  font-size: 10px;
  font-weight: 900;
  margin-top: 1px;
}

.risk-top5__text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.risk-top5__tag {
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}

.tag-red { color: #ff6974; background: rgba(234,72,92,.12); }
.tag-orange { color: #f3ae2a; background: rgba(240,165,26,.12); }
.tag-blue { color: #4fa1ff; background: rgba(47,111,255,.12); }
.tag-cyan { color: #28b7e8; background: rgba(40,183,232,.12); }

.risk-top5__empty {
  padding: 20px;
  text-align: center;
  color: #6f7e9c;
  font-size: 12px;
}

/* Export */

.risk-export { flex-shrink: 0; }

.risk-export__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 10px 12px;
}

.risk-export__btn {
  display: grid;
  grid-template-columns: 22px 1fr;
  align-items: center;
  gap: 8px;
  padding: 11px 10px;
  border-radius: 8px;
  border: 1px solid rgba(111, 144, 205, 0.1);
  background: rgba(12, 24, 45, 0.78);
  color: #dbe7ff;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s;
}

.risk-export__btn:hover:not(:disabled) { border-color: rgba(102, 138, 255, 0.22); }
.risk-export__btn:disabled { opacity: 0.45; cursor: not-allowed; }

.risk-export__btn span {
  display: block;
  margin-top: 2px;
  color: #75839a;
  font-size: 10px;
  font-weight: 600;
}

/* ---- Events Drawer ---- */

.risk-events-drawer {
  padding: 18px;
}

.risk-events-drawer h3 {
  margin: 0 0 16px;
  font-size: 18px;
  color: #edf4ff;
}

.risk-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 14px;
}

.risk-events__summary {
  font-weight: 600;
  color: #d8e5ff;
  font-size: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ---- Responsive ---- */

@media (max-width: 1200px) {
  .risk-grid {
    grid-template-columns: 1fr;
  }
  .risk-right {
    display: none;
  }
}

@media (max-width: 800px) {
  .risk-stage { height: auto; overflow-y: auto; }
  .risk-topbar { flex-wrap: wrap; }
  .risk-work { grid-template-columns: 1fr; min-height: 500px; }
  .risk-row-top { grid-template-columns: 1fr; }
}
</style>
