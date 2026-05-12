<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import { kbApi } from '../api/knowledgebase.js';
import { riskApi } from '../api/risk.js';
import { useFlash } from '../lib/flash.js';
import { normalizeRiskAnalytics } from '../lib/risk-workspace.js';
import AppIcon from './ui/AppIcon.vue';

const flash = useFlash();
const fmt = new Intl.NumberFormat('zh-CN');

const buildDefaultFilters = () => ({
  company_name: '',
  risk_type: '',
  risk_level: '',
  review_status: '',
  period_start: '',
  period_end: '',
});

const filters = ref(buildDefaultFilters());
const events = ref([]);
const analyticsPayload = ref(null);

const isEventsLoading = ref(false);
const isAnalyticsLoading = ref(false);
const isUploading = ref(false);
const isReportLoading = ref(false);
const isReportExporting = ref(false);
const reviewingId = ref(null);

const eventsErrorMsg = ref('');
const analyticsErrorMsg = ref('');
const reportErrorMsg = ref('');

const fileInput = ref(null);
const eventsDrawerOpen = ref(false);
const reportType = ref('company');
const reportForm = ref({ company_name: '', period_start: '', period_end: '' });
const generatedReport = ref(null);

let workspaceAbort = null;

const analytics = computed(() => normalizeRiskAnalytics(analyticsPayload.value));
const riskTypeDist = computed(() => analytics.value.risk_type_distribution || []);
const totalEvents = computed(() => analytics.value.summary.total_events || 0);
const pendingReviews = computed(() => analytics.value.summary.pending_reviews || 0);

const eventsByType = computed(() => {
  const groups = {};
  events.value.forEach((event) => {
    if (!groups[event.risk_type]) {
      groups[event.risk_type] = [];
    }
    groups[event.risk_type].push(event);
  });
  return groups;
});

const dominantLevelMap = computed(() => {
  const priority = { critical: 4, high: 3, medium: 2, low: 1 };
  const groups = {};

  Object.entries(eventsByType.value).forEach(([type, typeEvents]) => {
    groups[type] = typeEvents.reduce((best, event) => (
      (priority[event.risk_level] || 0) > (priority[best] || 0) ? event.risk_level : best
    ), 'low');
  });

  return groups;
});

const groupedRiskResults = computed(() => riskTypeDist.value.map((item) => {
  const relatedEvents = eventsByType.value[item.key] || [];
  return {
    key: item.key,
    count: item.value,
    dominantLevel: dominantLevelMap.value[item.key] || 'low',
    summary: relatedEvents[0]?.summary || '暂无摘要',
    evidence: relatedEvents[0]?.evidence_text || '暂无证据文本。',
  };
}));

const recentEvents = computed(() => events.value.slice(0, 8));

const sourceDoc = computed(() => {
  const firstEvent = events.value[0];
  const fileSize = firstEvent?.document_file_size || 0;

  return {
    title: firstEvent?.document_title || firstEvent?.document_filename || '暂无文档',
    company: firstEvent?.company_name || '未识别公司',
    size: fileSize > 0 ? `${(fileSize / 1024 / 1024).toFixed(1)} MB` : '--',
    date: firstEvent?.document_source_date || '--',
  };
});

const extractionQuality = computed(() => {
  const firstEvent = events.value.find((event) => event.extraction_metadata);
  if (!firstEvent) {
    return null;
  }

  return {
    rounds: firstEvent.extraction_metadata.rounds_completed,
    verified: firstEvent.extraction_metadata.verification_passed,
    filteredChunks: firstEvent.extraction_metadata.filtered_chunks,
    totalChunks: firstEvent.extraction_metadata.total_chunks,
  };
});

const summaryCards = computed(() => ([
  {
    key: 'events',
    label: '风险事件',
    value: fmt.format(totalEvents.value),
    note: '已提取结果',
  },
  {
    key: 'types',
    label: '风险类型',
    value: fmt.format(riskTypeDist.value.length),
    note: '按类型归并',
  },
  {
    key: 'pending',
    label: '待审核',
    value: fmt.format(pendingReviews.value),
    note: '需要人工确认',
  },
]));

const isAbortError = (error) => error?.name === 'AbortError';

const fetchEvents = async (signal) => {
  isEventsLoading.value = true;
  eventsErrorMsg.value = '';
  try {
    const data = await riskApi.getEvents(filters.value, { signal });
    events.value = data.data?.risk_events || data.risk_events || [];
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }
    eventsErrorMsg.value = error.message || '加载风险事件失败';
  } finally {
    isEventsLoading.value = false;
  }
};

const fetchAnalytics = async (signal) => {
  isAnalyticsLoading.value = true;
  analyticsErrorMsg.value = '';
  try {
    analyticsPayload.value = await riskApi.getAnalytics(filters.value, { signal });
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }
    analyticsErrorMsg.value = error.message || '加载风险分析失败';
  } finally {
    isAnalyticsLoading.value = false;
  }
};

const refreshWorkspace = async () => {
  if (workspaceAbort) {
    workspaceAbort.abort();
  }

  const controller = new AbortController();
  workspaceAbort = controller;

  try {
    await Promise.all([
      fetchEvents(controller.signal),
      fetchAnalytics(controller.signal),
    ]);
  } finally {
    if (workspaceAbort === controller) {
      workspaceAbort = null;
    }
  }
};

const handleReview = async (event, status) => {
  const eventId = event.id || event.event_id;
  if (reviewingId.value === eventId) {
    return;
  }

  reviewingId.value = eventId;
  try {
    await riskApi.reviewEvent(eventId, status);
    flash.success(`风险事件已${status === 'approved' ? '确认' : '忽略'}`);
    await refreshWorkspace();
  } catch (error) {
    flash.error(error.message || '审核失败');
  } finally {
    reviewingId.value = null;
  }
};

const applyFilters = () => refreshWorkspace();
const resetFilters = () => {
  filters.value = buildDefaultFilters();
  refreshWorkspace();
};

const triggerUpload = () => fileInput.value?.click();

const pollDocumentIndexed = async (documentId, { timeout = 60000, interval = 2000 } = {}) => {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const document = await kbApi.getDocumentDetail(documentId);
    const status = (document.status || '').toLowerCase();

    if (status === 'indexed') {
      return document;
    }
    if (status === 'failed') {
      throw new Error('文档处理失败');
    }

    await new Promise((resolve) => setTimeout(resolve, interval));
  }

  throw new Error('文档处理超时，请稍后重试');
};

const runRiskPipeline = async (documentId) => {
  flash.success('上传完成，文档处理中...');
  await kbApi.ingestDocument(documentId);
  await pollDocumentIndexed(documentId);
  flash.success('文档就绪，正在提取风险事件...');
  await riskApi.extractDocumentWithPolling(documentId);
  flash.success('风险提取完成');
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  isUploading.value = true;
  try {
    flash.success('文档上传中...');
    const result = await kbApi.uploadDocument(file);
    const documentId = result.document?.id;

    if (documentId) {
      await runRiskPipeline(documentId);
    }

    await refreshWorkspace();
  } catch (error) {
    if (error.code === 'DUPLICATE' && error.existingDocument) {
      try {
        await ElMessageBox.confirm(
          `文件已存在（《${error.existingDocument.title}》），是否作为新版本上传？`,
          '文件重复',
          { confirmButtonText: '上传新版本', cancelButtonText: '取消', type: 'info' },
        );
      } catch {
        return;
      }

      try {
        flash.success('正在上传新版本...');
        const versionResult = await kbApi.uploadNewVersion(error.existingDocument.id, file, {
          title: file.name,
          sourceLabel: file.name,
        });
        const newDocumentId = versionResult.document?.id;
        if (newDocumentId) {
          await runRiskPipeline(newDocumentId);
        }
        await refreshWorkspace();
      } catch (versionError) {
        flash.error(versionError.message || '上传新版本失败');
      }
      return;
    }

    flash.error(error.message || '上传或提取失败');
  } finally {
    isUploading.value = false;
    if (event.target) {
      event.target.value = '';
    }
  }
};

const generateReport = async () => {
  reportErrorMsg.value = '';

  if (reportType.value === 'company' && !reportForm.value.company_name) {
    reportErrorMsg.value = '请输入公司名称';
    return;
  }

  if (reportType.value === 'time_range' && (!reportForm.value.period_start || !reportForm.value.period_end)) {
    reportErrorMsg.value = '请输入开始和结束日期';
    return;
  }

  isReportLoading.value = true;
  generatedReport.value = null;

  try {
    let data;
    if (reportType.value === 'company') {
      data = await riskApi.generateCompanyReport({
        company_name: reportForm.value.company_name,
        period_start: reportForm.value.period_start || undefined,
        period_end: reportForm.value.period_end || undefined,
      });
    } else {
      data = await riskApi.generateTimeRangeReport({
        period_start: reportForm.value.period_start,
        period_end: reportForm.value.period_end,
      });
    }

    generatedReport.value = data.data?.report || data.report || data;
    flash.success('风险报告生成成功');
    await fetchAnalytics();
  } catch (error) {
    reportErrorMsg.value = error.message || '生成报告失败';
  } finally {
    isReportLoading.value = false;
  }
};

const downloadGeneratedReport = async (format = 'markdown') => {
  if (!generatedReport.value?.id) {
    flash.error('请先生成报告后再导出');
    return;
  }

  isReportExporting.value = true;
  try {
    const payload = await riskApi.exportReport(generatedReport.value.id, { format });
    const blob = new Blob([payload.content], { type: payload.contentType });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = payload.filename;
    anchor.click();
    window.URL.revokeObjectURL(url);
    flash.success('报告已导出');
  } catch (error) {
    flash.error(error.message || '导出失败');
  } finally {
    isReportExporting.value = false;
  }
};

const exportEventsAsJson = () => {
  if (!events.value.length) {
    flash.warning('暂无风险事件可导出');
    return;
  }

  const blob = new Blob([JSON.stringify(events.value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'risk-events.json';
  anchor.click();
  URL.revokeObjectURL(url);
  flash.success('已导出风险事件 JSON');
};

const formatDate = (value) => {
  try {
    return value ? new Date(value).toLocaleString() : '--';
  } catch {
    return value;
  }
};

const getRiskTagType = (level) => ({ high: 'danger', critical: 'danger', medium: 'warning', low: 'success' }[level] || 'info');
const getReviewTagType = (status) => ({ approved: 'success', rejected: 'danger', pending: 'warning' }[status] || 'info');
const getReviewStatusText = (status) => ({ pending: '待审核', approved: '已确认', rejected: '已忽略' }[status?.toLowerCase()] || status || '待审核');
const getRiskLevelText = (level) => ({ critical: '严重', high: '高', medium: '中', low: '低' }[level] || level);

const formatConfidence = (score) => `${Math.round((parseFloat(score) || 0) * 100)}%`;
const getConfidenceClass = (score) => {
  const value = parseFloat(score) || 0;
  if (value >= 0.8) return 'confidence-high';
  if (value >= 0.5) return 'confidence-mid';
  return 'confidence-low';
};

const getSourceTooltip = (event) => {
  const meta = event.extraction_metadata;
  if (!meta) {
    return `Chunk #${event.chunk_id}`;
  }

  return [
    `Chunk #${event.chunk_id}`,
    `提取轮次: ${meta.rounds_completed}`,
    `验证: ${meta.verification_passed ? '通过' : '未通过'}`,
    `筛选切块: ${meta.filtered_chunks || '?'}/${meta.total_chunks || '?'}`,
  ].join('\n');
};

onMounted(() => {
  refreshWorkspace();
});

onBeforeUnmount(() => {
  if (workspaceAbort) {
    workspaceAbort.abort();
  }
});
</script>

<template>
  <div class="page-stack risk-page">
    <el-alert
      v-if="eventsErrorMsg || analyticsErrorMsg"
      :title="eventsErrorMsg || analyticsErrorMsg"
      type="error"
      show-icon
      :closable="false"
    />

    <section class="risk-page__hero">
      <div class="risk-page__hero-copy">
        <span class="risk-page__eyebrow">Risk Extraction</span>
        <h2>上传文档，提取风险，确认结果</h2>
        <p>这个页面只保留三件事：跑提取、看结果、做审核。报告导出放到次级区，不再和主流程抢注意力。</p>
      </div>

      <div class="risk-page__hero-actions">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.docx,.txt"
          class="risk-page__file-input"
          @change="handleFileChange"
          aria-hidden="true"
          tabindex="-1"
        />
        <el-button type="primary" :loading="isUploading" @click="triggerUpload">
          <AppIcon name="upload" />
          {{ isUploading ? '上传中...' : '上传文档' }}
        </el-button>
        <el-button :loading="isEventsLoading || isAnalyticsLoading" @click="refreshWorkspace">
          <AppIcon name="refresh" />
          刷新
        </el-button>
        <el-button @click="eventsDrawerOpen = true">
          查看全部事件
        </el-button>
      </div>
    </section>

    <section class="risk-page__summary">
      <article v-for="item in summaryCards" :key="item.key" class="risk-page__summary-card">
        <small>{{ item.label }}</small>
        <strong>{{ item.value }}</strong>
        <span>{{ item.note }}</span>
      </article>
    </section>

    <div class="risk-page__main">
      <section class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>提取结果</h3>
            <p>按风险类型归并结果，先看类型和证据，不再拆成多个复杂面板。</p>
          </div>
        </header>

        <div v-if="isEventsLoading" class="risk-page__empty">正在加载提取结果...</div>
        <div v-else-if="!groupedRiskResults.length" class="risk-page__empty">
          上传文档后，提取结果会出现在这里。
        </div>
        <div v-else class="risk-page__result-list">
          <article
            v-for="item in groupedRiskResults"
            :key="item.key"
            class="risk-page__result-item"
          >
            <div class="risk-page__result-head">
              <div>
                <strong>{{ item.key }}</strong>
                <p>{{ item.summary }}</p>
              </div>
              <div class="risk-page__result-meta">
                <el-tag :type="getRiskTagType(item.dominantLevel)" size="small">
                  {{ getRiskLevelText(item.dominantLevel) }}
                </el-tag>
                <span>{{ item.count }} 条</span>
              </div>
            </div>
            <p class="risk-page__evidence">{{ item.evidence }}</p>
          </article>
        </div>
      </section>

      <section class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>审核队列</h3>
            <p>只展示最近待处理事件，完整筛选和全量记录放到右侧抽屉。</p>
          </div>
          <el-button text @click="eventsDrawerOpen = true">查看全部</el-button>
        </header>

        <el-table
          :data="recentEvents"
          size="small"
          v-loading="isEventsLoading"
          empty-text="暂无风险事件"
        >
          <el-table-column prop="company_name" label="公司" min-width="120" show-overflow-tooltip />
          <el-table-column prop="risk_type" label="类型" min-width="110" show-overflow-tooltip />
          <el-table-column label="等级" width="82">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">
                {{ getRiskLevelText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.summary || row.evidence_text || '--' }}
            </template>
          </el-table-column>
          <el-table-column label="审核" width="88">
            <template #default="{ row }">
              <el-tag :type="getReviewTagType((row.review_status || 'pending').toLowerCase())" size="small">
                {{ getReviewStatusText(row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="148" align="right">
            <template #default="{ row }">
              <div v-if="(row.review_status || 'pending').toLowerCase() === 'pending'" class="risk-page__actions">
                <el-button
                  type="success"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'approved')"
                >
                  确认
                </el-button>
                <el-button
                  type="danger"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'rejected')"
                >
                  忽略
                </el-button>
              </div>
              <span v-else class="risk-page__muted-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>

    <div class="risk-page__secondary">
      <section class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>来源与证据</h3>
            <p>把文档元信息和原文证据收在一起，减少来回切换。</p>
          </div>
        </header>

        <div class="risk-page__source-grid">
          <div class="risk-page__source-field">
            <span>文档</span>
            <strong>{{ sourceDoc.title }}</strong>
          </div>
          <div class="risk-page__source-field">
            <span>公司</span>
            <strong>{{ sourceDoc.company }}</strong>
          </div>
          <div class="risk-page__source-field">
            <span>大小</span>
            <strong>{{ sourceDoc.size }}</strong>
          </div>
          <div class="risk-page__source-field">
            <span>日期</span>
            <strong>{{ sourceDoc.date }}</strong>
          </div>
        </div>

        <div v-if="extractionQuality" class="risk-page__quality">
          <span>{{ extractionQuality.rounds }} 轮提取</span>
          <span>{{ extractionQuality.verified ? '验证通过' : '待人工确认' }}</span>
          <span v-if="extractionQuality.totalChunks">筛选 {{ extractionQuality.filteredChunks }}/{{ extractionQuality.totalChunks }} 切块</span>
        </div>

        <div v-if="events.length" class="risk-page__evidence-list">
          <article
            v-for="event in events.slice(0, 5)"
            :key="event.id || event.event_id"
            class="risk-page__evidence-item"
          >
            <div class="risk-page__evidence-head">
              <strong>{{ event.risk_type }}</strong>
              <span>{{ event.company_name }}</span>
            </div>
            <p>{{ event.evidence_text || event.summary || '暂无证据文本。' }}</p>
          </article>
        </div>
        <div v-else class="risk-page__empty">暂无证据片段。</div>
      </section>

      <section class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>报告与导出</h3>
            <p>保留导出能力，但降到次要层级，不干扰提取和审核主任务。</p>
          </div>
        </header>

        <div v-if="reportErrorMsg" class="risk-page__report-error">{{ reportErrorMsg }}</div>

        <div class="risk-page__report-type">
          <el-radio-group v-model="reportType" size="small">
            <el-radio-button label="company">公司报告</el-radio-button>
            <el-radio-button label="time_range">时间范围</el-radio-button>
          </el-radio-group>
        </div>

        <div v-if="reportType === 'company'" class="risk-page__report-fields">
          <el-input v-model="reportForm.company_name" placeholder="公司名称" clearable />
        </div>
        <div v-else class="risk-page__report-fields risk-page__report-fields--dates">
          <el-date-picker
            v-model="reportForm.period_start"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
          <el-date-picker
            v-model="reportForm.period_end"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </div>

        <div class="risk-page__report-actions">
          <el-button type="primary" :loading="isReportLoading" @click="generateReport">
            生成报告
          </el-button>
          <el-button :disabled="!generatedReport || isReportExporting" :loading="isReportExporting" @click="downloadGeneratedReport('markdown')">
            导出 Markdown
          </el-button>
          <el-button @click="exportEventsAsJson">
            导出事件 JSON
          </el-button>
        </div>
      </section>
    </div>

    <el-drawer
      v-model="eventsDrawerOpen"
      direction="rtl"
      size="720px"
      :with-header="false"
      destroy-on-close
      aria-label="风险事件列表"
    >
      <div class="risk-events-drawer">
        <div class="risk-events-drawer__head">
          <div>
            <h3>风险事件列表</h3>
            <div v-if="extractionQuality" class="risk-events-drawer__quality">
              <span>{{ extractionQuality.rounds }} 轮提取</span>
              <span v-if="extractionQuality.verified">验证通过</span>
            </div>
          </div>
          <el-button text @click="eventsDrawerOpen = false">关闭</el-button>
        </div>

        <el-form :inline="true" class="risk-filter-row">
          <el-form-item>
            <el-input v-model="filters.company_name" placeholder="公司名称" size="small" clearable />
          </el-form-item>
          <el-form-item>
            <el-input v-model="filters.risk_type" placeholder="风险类型" size="small" clearable />
          </el-form-item>
          <el-form-item>
            <el-select v-model="filters.risk_level" placeholder="等级" size="small" clearable>
              <el-option label="严重" value="critical" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="filters.review_status" placeholder="状态" size="small" clearable>
              <el-option label="待审核" value="pending" />
              <el-option label="已确认" value="approved" />
              <el-option label="已忽略" value="rejected" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" :loading="isEventsLoading" @click="applyFilters">查询</el-button>
            <el-button size="small" @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>

        <el-table
          :data="events"
          stripe
          size="small"
          v-loading="isEventsLoading"
          max-height="calc(100vh - 220px)"
          empty-text="暂无风险事件"
        >
          <el-table-column prop="company_name" label="公司" min-width="140" show-overflow-tooltip />
          <el-table-column label="类型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.risk_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="等级" width="82">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">
                {{ getRiskLevelText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="150">
            <template #default="{ row }">
              {{ formatDate(row.event_time || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.summary || '--' }}
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="88">
            <template #default="{ row }">
              <span :class="getConfidenceClass(row.confidence_score)">
                {{ formatConfidence(row.confidence_score) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="96">
            <template #default="{ row }">
              <el-tooltip v-if="row.chunk_id" :content="getSourceTooltip(row)" placement="top">
                <span class="risk-source-chip">Chunk #{{ row.chunk_id }}</span>
              </el-tooltip>
              <span v-else class="risk-source-chip risk-source-chip--muted">--</span>
            </template>
          </el-table-column>
          <el-table-column label="审核" width="88">
            <template #default="{ row }">
              <el-tag :type="getReviewTagType((row.review_status || 'pending').toLowerCase())" size="small">
                {{ getReviewStatusText(row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="144">
            <template #default="{ row }">
              <template v-if="(row.review_status || 'pending').toLowerCase() === 'pending'">
                <el-button
                  type="success"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'approved')"
                >
                  确认
                </el-button>
                <el-button
                  type="danger"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'rejected')"
                >
                  忽略
                </el-button>
              </template>
              <span v-else class="risk-page__muted-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.risk-page {
  min-width: 0;
}

.risk-page__hero,
.risk-page__panel {
  padding: 20px 22px;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
}

.risk-page__hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.risk-page__hero-copy {
  max-width: 760px;
}

.risk-page__eyebrow {
  display: inline-flex;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.risk-page__hero-copy h2,
.risk-page__panel-head h3 {
  margin: 0;
  color: var(--text-primary);
}

.risk-page__hero-copy p,
.risk-page__panel-head p,
.risk-page__result-head p,
.risk-page__evidence,
.risk-page__evidence-item p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__hero-actions,
.risk-page__summary,
.risk-page__main,
.risk-page__secondary,
.risk-page__report-actions,
.risk-page__actions,
.risk-page__quality {
  display: flex;
  gap: 10px;
}

.risk-page__hero-actions,
.risk-page__quality,
.risk-page__actions {
  flex-wrap: wrap;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.risk-page__summary-card {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-1);
}

.risk-page__summary-card small,
.risk-page__source-field span,
.risk-page__muted-text,
.risk-page__quality,
.risk-events-drawer__quality {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__summary-card strong {
  color: var(--text-primary);
  font-size: 1.625rem;
  line-height: 1;
}

.risk-page__main,
.risk-page__secondary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.risk-page__panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.risk-page__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.risk-page__result-list,
.risk-page__evidence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-page__result-item,
.risk-page__evidence-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__result-head,
.risk-page__evidence-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-page__result-head strong,
.risk-page__evidence-head strong,
.risk-page__source-field strong {
  color: var(--text-primary);
}

.risk-page__result-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}

.risk-page__evidence {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-3);
}

.risk-page__source-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.risk-page__source-field {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.risk-page__evidence-head span {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__report-error {
  padding: 12px 14px;
  border: 1px solid rgba(196, 73, 61, 0.16);
  border-radius: 14px;
  background: rgba(196, 73, 61, 0.08);
  color: var(--risk);
  font-size: 0.875rem;
}

.risk-page__report-fields {
  display: grid;
  gap: 10px;
}

.risk-page__report-fields--dates {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.risk-page__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  color: var(--text-secondary);
  text-align: center;
}

.risk-events-drawer {
  padding: 20px;
}

.risk-events-drawer__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.risk-events-drawer__head h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.125rem;
}

.risk-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 14px;
}

.confidence-high {
  color: var(--success);
  font-weight: 600;
}

.confidence-mid {
  color: var(--warning);
  font-weight: 600;
}

.confidence-low {
  color: var(--risk);
  font-weight: 600;
}

.risk-source-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.1);
  color: var(--brand);
  font-size: 0.75rem;
}

.risk-source-chip--muted {
  background: rgba(125, 135, 152, 0.1);
  color: var(--text-muted);
}

.risk-page :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
}

.risk-page :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.risk-page :deep(.el-table th.el-table__cell) {
  height: 40px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
}

.risk-page :deep(.el-input__wrapper),
.risk-page :deep(.el-select__wrapper),
.risk-page :deep(.el-textarea__inner) {
  min-height: 36px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  border-radius: 12px;
}

.risk-page :deep(.el-radio-button__inner) {
  border-radius: 12px;
}

@media (max-width: 1200px) {
  .risk-page__summary,
  .risk-page__main,
  .risk-page__secondary,
  .risk-page__source-grid,
  .risk-page__report-fields--dates {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .risk-page__hero,
  .risk-page__panel-head {
    flex-direction: column;
  }
}
</style>
