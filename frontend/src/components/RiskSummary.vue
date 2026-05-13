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
const activeDocument = ref(null);
const createPipelineRunState = () => ({
  status: 'idle',
  fileName: '',
  documentId: null,
  detail: '等待新文档',
  uploadProgress: 0,
  ingestLabel: '待开始',
  ingestProgress: 0,
  extractLabel: '待开始',
  extractStatus: 'IDLE',
  extractProgress: 0,
  createdCount: 0,
  reviewReady: false,
  failureCode: '',
});
const pipelineRun = ref(createPipelineRunState());
const sourceMode = ref('upload');
const knowledgebaseSearch = ref('');
const knowledgebaseDocs = ref([]);
const selectedKnowledgebaseId = ref('');
const isKnowledgebaseLoading = ref(false);
const showUtilities = ref(false);

let workspaceAbort = null;

const analytics = computed(() => normalizeRiskAnalytics(analyticsPayload.value));
const riskTypeDist = computed(() => analytics.value.risk_type_distribution || []);
const totalEvents = computed(() => analytics.value.summary.total_events || 0);
const pendingReviews = computed(() => analytics.value.summary.pending_reviews || 0);
const selectedKnowledgeDocument = computed(() => (
  knowledgebaseDocs.value.find((doc) => String(doc.id) === String(selectedKnowledgebaseId.value)) || null
));

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
  const currentDocument = activeDocument.value;
  const firstEvent = events.value[0];
  const fileSize = currentDocument
    ? Number.parseFloat(currentDocument.size) || 0
    : (firstEvent?.document_file_size || 0);

  return {
    title: currentDocument?.title || firstEvent?.document_title || firstEvent?.document_filename || '暂无文档',
    company: firstEvent?.company_name || '未识别公司',
    size: currentDocument?.size || (fileSize > 0 ? `${(fileSize / 1024 / 1024).toFixed(1)} MB` : '--'),
    date: currentDocument?.sourceDate || firstEvent?.document_source_date || '--',
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

const pipelinePercent = computed(() => {
  if (pipelineRun.value.status === 'idle' && !pipelineRun.value.fileName) {
    return 0;
  }

  const weighted =
    (pipelineRun.value.uploadProgress * 0.2)
    + (pipelineRun.value.ingestProgress * 0.35)
    + (pipelineRun.value.extractProgress * 0.35)
    + ((pipelineRun.value.reviewReady ? 100 : 0) * 0.1);

  return Math.max(
    pipelineRun.value.status === 'idle' ? 0 : 6,
    Math.min(100, Math.round(weighted)),
  );
});

const pipelineStatusText = computed(() => ({
  idle: '待命',
  uploading: '上传中',
  ingesting: '入库中',
  extracting: '抽取中',
  succeeded: '已完成',
  busy: '系统繁忙',
  timed_out: '已超时',
  failed: '已中断',
}[pipelineRun.value.status] || '处理中'));

const pipelineTone = computed(() => ({
  idle: 'muted',
  uploading: 'active',
  ingesting: 'active',
  extracting: 'active',
  succeeded: 'success',
  busy: 'warning',
  timed_out: 'warning',
  failed: 'danger',
}[pipelineRun.value.status] || 'muted'));

const uploadButtonLabel = computed(() => {
  if (!isUploading.value) {
    return '上传文档';
  }
  return `上传 ${Math.max(1, pipelineRun.value.uploadProgress)}%`;
});

const pipelineSteps = computed(() => ([
  {
    key: 'upload',
    label: '上传',
    progress: pipelineRun.value.uploadProgress,
    note: pipelineRun.value.fileName || 'PDF / DOCX / TXT',
    state: pipelineRun.value.uploadProgress >= 100 ? 'done' : (pipelineRun.value.status === 'uploading' ? 'active' : 'idle'),
  },
  {
    key: 'ingest',
    label: '入库',
    progress: pipelineRun.value.ingestProgress,
    note: pipelineRun.value.ingestLabel,
    state: pipelineRun.value.status === 'failed'
      ? 'failed'
      : (pipelineRun.value.ingestProgress >= 100 ? 'done' : (['ingesting', 'extracting', 'succeeded'].includes(pipelineRun.value.status) ? 'active' : 'idle')),
  },
  {
    key: 'extract',
    label: '提取',
    progress: pipelineRun.value.extractProgress,
    note: pipelineRun.value.extractLabel,
    state: pipelineRun.value.status === 'failed'
      ? 'failed'
      : (pipelineRun.value.extractProgress >= 100 ? 'done' : (pipelineRun.value.status === 'extracting' ? 'active' : 'idle')),
  },
  {
    key: 'review',
    label: '审核',
    progress: pipelineRun.value.reviewReady ? 100 : 0,
    note: pipelineRun.value.reviewReady ? `${pendingReviews.value} 待审核` : '等待结果',
    state: pipelineRun.value.status === 'failed'
      ? 'failed'
      : (pipelineRun.value.reviewReady ? 'done' : 'idle'),
  },
]));

const pipelineMetaCards = computed(() => ([
  {
    key: 'document',
    label: '当前文档',
    value: pipelineRun.value.fileName || sourceDoc.value.title,
  },
  {
    key: 'stage',
    label: '当前阶段',
    value: pipelineRun.value.detail,
  },
  {
    key: 'created',
    label: '已提取',
    value: `${fmt.format(pipelineRun.value.createdCount)} 条`,
  },
  {
    key: 'pending',
    label: '待审核',
    value: `${fmt.format(pendingReviews.value)} 条`,
  },
]));

const isAbortError = (error) => error?.name === 'AbortError';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const updatePipelineRun = (patch) => {
  pipelineRun.value = {
    ...pipelineRun.value,
    ...patch,
  };
};

const resetPipelineRun = () => {
  pipelineRun.value = createPipelineRunState();
  activeDocument.value = null;
};

const startPipelineRun = (file) => {
  pipelineRun.value = {
    ...createPipelineRunState(),
    status: 'uploading',
    fileName: file.name,
    detail: '正在接收文件',
  };
  activeDocument.value = null;
};

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

const fetchKnowledgebaseDocuments = async () => {
  isKnowledgebaseLoading.value = true;
  try {
    const result = await kbApi.listDocuments({
      searchKeyword: knowledgebaseSearch.value,
      statusFilter: 'indexed',
      pageSize: 8,
    });
    knowledgebaseDocs.value = result.documents || [];
    if (!knowledgebaseDocs.value.some((doc) => String(doc.id) === String(selectedKnowledgebaseId.value))) {
      selectedKnowledgebaseId.value = activeDocument.value?.id
        ? String(activeDocument.value.id)
        : String(knowledgebaseDocs.value[0]?.id || '');
    }
  } catch (error) {
    flash.error(error.message || '加载知识库文档失败');
  } finally {
    isKnowledgebaseLoading.value = false;
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

const handleKnowledgebaseExtract = async () => {
  if (!selectedKnowledgebaseId.value) {
    flash.warning('请先选择一份知识库文档');
    return;
  }

  isUploading.value = true;
  try {
    const document = selectedKnowledgeDocument.value || await kbApi.getDocumentDetail(selectedKnowledgebaseId.value);
    activeDocument.value = document;
    updatePipelineRun({
      ...createPipelineRunState(),
      status: 'extracting',
      fileName: document.title,
      documentId: document.id,
      uploadProgress: 100,
      ingestProgress: document.status === 'indexed' ? 100 : 0,
      ingestLabel: document.status === 'indexed' ? '已完成' : '待开始',
      detail: '使用知识库已有文档开始风险提取',
    });
    await runRiskPipeline(document.id);
  } catch (error) {
    applyPipelineFailure(error);
    if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
      flash.warning(error.message || '知识库提取失败');
    } else {
      flash.error(error.message || '知识库提取失败');
    }
  } finally {
    isUploading.value = false;
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

const syncActiveDocument = async (documentId) => {
  const document = await kbApi.getDocumentDetail(documentId);
  activeDocument.value = document;
  updatePipelineRun({
    documentId,
    status: document.processStep.code === 'failed'
      ? 'failed'
      : (pipelineRun.value.status === 'uploading' ? 'ingesting' : pipelineRun.value.status),
    ingestLabel: document.processStep.label,
    ingestProgress: document.processStep.progress,
    detail: document.processStep.detail,
  });
  return document;
};

const applyExtractionProgress = (payload = {}) => {
  const status = String(payload.status || '').toUpperCase();
  const errorCode = payload.error_code || '';
  const resolvedProgress = Number.isFinite(Number(payload.progress))
    ? Math.max(0, Math.min(100, Number(payload.progress)))
    : ({
      QUEUED: 6,
      RUNNING: 72,
      SUCCESS: 100,
      FAILURE: 100,
      BUSY: 100,
      TIMED_OUT: 100,
    }[status] || pipelineRun.value.extractProgress);

  const nextLabel = ({
    QUEUED: '已排队',
    RUNNING: '抽取中',
    SUCCESS: '已完成',
    FAILURE: '已失败',
    BUSY: '系统繁忙',
    TIMED_OUT: '执行超时',
  }[status] || pipelineRun.value.extractLabel);

  const pipelineStatus = status === 'BUSY'
    ? 'busy'
    : (status === 'TIMED_OUT'
      || ['risk_extraction_timeout', 'risk_extraction_stage_timeout', 'risk_extraction_queue_timeout', 'risk_extraction_poll_timeout'].includes(errorCode)
      ? 'timed_out'
      : (status === 'FAILURE'
        ? 'failed'
        : (status === 'SUCCESS' ? 'succeeded' : 'extracting')));

  updatePipelineRun({
    status: pipelineStatus,
    extractStatus: status || pipelineRun.value.extractStatus,
    extractLabel: nextLabel,
    extractProgress: resolvedProgress,
    detail: payload.message || pipelineRun.value.detail,
    createdCount: payload.result?.created_count ?? pipelineRun.value.createdCount,
    reviewReady: status === 'SUCCESS',
    failureCode: errorCode,
  });
};

const applyPipelineFailure = (error) => {
  const failureCode = error?.code || error?.data?.error_code || '';
  const nextStatus = failureCode === 'risk_extraction_busy'
    ? 'busy'
    : ([
      'risk_extraction_timeout',
      'risk_extraction_stage_timeout',
      'risk_extraction_queue_timeout',
      'risk_extraction_poll_timeout',
    ].includes(failureCode)
      ? 'timed_out'
      : 'failed');

  updatePipelineRun({
    status: nextStatus,
    detail: error?.message || '上传或提取失败',
    failureCode,
  });
};

const pollDocumentIndexed = async (documentId, { timeout = 60000, interval = 2000 } = {}) => {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const document = await syncActiveDocument(documentId);
    const status = (document.status || '').toLowerCase();

    if (status === 'indexed') {
      return document;
    }
    if (status === 'failed') {
      throw new Error(document.processError || '文档处理失败');
    }

    await sleep(interval);
  }

  throw new Error('文档处理超时，请稍后重试');
};

const runRiskPipeline = async (documentId) => {
  const currentDocument = activeDocument.value?.id === documentId
    ? activeDocument.value
    : await syncActiveDocument(documentId);
  const currentStatus = String(currentDocument?.status || '').toLowerCase();

  if (currentStatus !== 'indexed') {
    const ingestPayload = await kbApi.ingestDocument(documentId);
    if (ingestPayload.document) {
      activeDocument.value = ingestPayload.document;
      updatePipelineRun({
        status: 'ingesting',
        documentId,
        ingestLabel: ingestPayload.document.processStep.label,
        ingestProgress: ingestPayload.document.processStep.progress,
        detail: ingestPayload.document.processStep.detail,
      });
    }
    await pollDocumentIndexed(documentId);
  } else {
    updatePipelineRun({
      status: 'extracting',
      documentId,
      ingestLabel: '已完成',
      ingestProgress: 100,
      detail: '知识库中已有可用文档，直接开始风险提取',
    });
  }

  updatePipelineRun({
    status: 'extracting',
    extractLabel: '已提交',
    extractProgress: 6,
    detail: '文档已入库，准备抽取风险',
  });
  const result = await riskApi.extractDocumentWithPolling(documentId, {
    onProgress: applyExtractionProgress,
  });
  applyExtractionProgress({
    status: 'SUCCESS',
    progress: 100,
    message: result.message || (result.created_count ? '风险抽取完成' : '未识别到风险事件'),
    result,
  });
  flash.success('风险提取完成');
  await Promise.all([
    refreshWorkspace(),
    fetchKnowledgebaseDocuments(),
  ]);
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  isUploading.value = true;
  startPipelineRun(file);
  try {
    const result = await kbApi.uploadDocument(file, {
      onProgress: (progress) => {
        updatePipelineRun({
          status: 'uploading',
          uploadProgress: progress,
          detail: '文件正在上传',
        });
      },
    });
    const documentId = result.document?.id;

    if (documentId) {
      activeDocument.value = result.document;
      updatePipelineRun({
        uploadProgress: 100,
        status: 'ingesting',
        documentId,
        ingestLabel: result.document.processStep.label,
        ingestProgress: result.document.processStep.progress,
        detail: '文件已保存，正在提交入库任务',
      });
      await runRiskPipeline(documentId);
    }
  } catch (error) {
    if (error.code === 'DUPLICATE' && error.existingDocument) {
      try {
        await ElMessageBox.confirm(
          `知识库已存在《${error.existingDocument.title}》，是否直接使用这份文档进行风险提取？`,
          '使用已有文档',
          { confirmButtonText: '直接使用', cancelButtonText: '取消', type: 'info' },
        );
      } catch {
        resetPipelineRun();
        return;
      }

      try {
        updatePipelineRun({
          fileName: error.existingDocument.filename || error.existingDocument.title || file.name,
          uploadProgress: 100,
          documentId: error.existingDocument.id,
          status: 'ingesting',
          detail: '正在切换到知识库已有文档',
        });
        await syncActiveDocument(error.existingDocument.id);
        await runRiskPipeline(error.existingDocument.id);
      } catch (versionError) {
        applyPipelineFailure(versionError);
        if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
          flash.warning(versionError.message || '使用已有文档失败');
        } else {
          flash.error(versionError.message || '使用已有文档失败');
        }
      }
      return;
    }

    applyPipelineFailure(error);
    if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
      flash.warning(error.message || '上传或提取失败');
    } else {
      flash.error(error.message || '上传或提取失败');
    }
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
  fetchKnowledgebaseDocuments();
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
      <input
        ref="fileInput"
        type="file"
        accept=".pdf,.docx,.txt"
        class="risk-page__file-input"
        @change="handleFileChange"
        aria-hidden="true"
        tabindex="-1"
      />

      <div class="risk-page__hero-copy">
        <span class="risk-page__eyebrow">Risk Extraction</span>
        <h2>先选文档，再提取风险</h2>
        <p>主任务只有一件事，选一份文档，完成提取，然后回到审核队列。</p>
      </div>

      <div class="risk-page__runline">
        <span class="risk-page__run-badge" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
        <strong>{{ pipelineRun.fileName || selectedKnowledgeDocument?.title || '还未选择文档' }}</strong>
        <span>{{ pipelineRun.detail }}</span>
      </div>

      <div class="risk-page__progress-rail" aria-hidden="true">
        <span :style="{ width: `${pipelinePercent}%` }" />
      </div>

      <div class="risk-page__launcher">
        <div class="risk-page__source-switch">
          <span>来源</span>
          <el-radio-group v-model="sourceMode" size="small">
            <el-radio-button label="upload">上传新文档</el-radio-button>
            <el-radio-button label="knowledgebase">从知识库提取</el-radio-button>
          </el-radio-group>
        </div>

        <div v-if="sourceMode === 'upload'" class="risk-page__launcher-body">
          <div class="risk-page__dropzone">
            <div class="risk-page__dropzone-mark">
              <AppIcon name="upload" />
            </div>
            <div>
              <strong>{{ pipelineRun.fileName || 'PDF / DOCX / TXT' }}</strong>
              <span>{{ sourceDoc.size !== '--' ? sourceDoc.size : '单次 50 MB 内' }}</span>
            </div>
          </div>
          <div class="risk-page__launcher-actions">
            <el-button type="primary" :loading="isUploading" @click="triggerUpload">
              <AppIcon name="upload" />
              {{ uploadButtonLabel }}
            </el-button>
            <el-button :loading="isEventsLoading || isAnalyticsLoading" @click="refreshWorkspace">
              <AppIcon name="refresh" />
              刷新结果
            </el-button>
          </div>
        </div>

        <div v-else class="risk-page__launcher-body">
          <div class="risk-page__knowledge-search">
            <el-input
              v-model="knowledgebaseSearch"
              placeholder="搜索知识库文档"
              clearable
              @keyup.enter="fetchKnowledgebaseDocuments"
            />
            <el-button :loading="isKnowledgebaseLoading" @click="fetchKnowledgebaseDocuments">
              <AppIcon name="refresh" />
              刷新
            </el-button>
          </div>

          <div class="risk-page__knowledge-list">
            <button
              v-for="doc in knowledgebaseDocs"
              :key="doc.id"
              type="button"
              class="risk-page__knowledge-item"
              :data-active="String(doc.id) === String(selectedKnowledgebaseId)"
              @click="selectedKnowledgebaseId = String(doc.id)"
            >
              <div>
                <strong>{{ doc.title }}</strong>
                <span>{{ doc.datasetName }} · {{ doc.size }}</span>
              </div>
              <small>{{ doc.processStep.label }}</small>
            </button>
            <div v-if="!knowledgebaseDocs.length && !isKnowledgebaseLoading" class="risk-page__empty">
              暂无已入库文档。
            </div>
          </div>

          <div class="risk-page__launcher-actions">
            <el-button
              type="primary"
              :loading="isUploading"
              :disabled="!selectedKnowledgebaseId"
              @click="handleKnowledgebaseExtract"
            >
              开始提取
            </el-button>
            <el-button @click="eventsDrawerOpen = true">
              查看全部事件
            </el-button>
          </div>
        </div>
      </div>

      <div class="risk-page__step-grid">
        <article
          v-for="step in pipelineSteps"
          :key="step.key"
          class="risk-page__step-card"
          :data-state="step.state"
        >
          <small>{{ step.label }}</small>
          <strong>{{ step.progress }}%</strong>
          <span>{{ step.note }}</span>
        </article>
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

    <section class="risk-page__panel risk-page__utilities">
      <header class="risk-page__panel-head">
        <div>
          <h3>更多工具</h3>
          <p>把证据和导出收起来，需要时再展开。</p>
        </div>
        <el-button text @click="showUtilities = !showUtilities">
          {{ showUtilities ? '收起' : '展开' }}
        </el-button>
      </header>

      <div v-if="showUtilities" class="risk-page__secondary">
        <section class="risk-page__utility-block">
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
              v-for="event in events.slice(0, 3)"
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
        </section>

        <section class="risk-page__utility-block">
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
    </section>

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
  display: grid;
  gap: 16px;
  min-width: 0;
}

.risk-page__hero-copy {
  max-width: 720px;
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

.risk-page__runline {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(36, 87, 197, 0.08), rgba(36, 87, 197, 0.02)),
    var(--surface-2);
}

.risk-page__runline strong,
.risk-page__step-card strong,
.risk-page__dropzone strong,
.risk-page__knowledge-item strong {
  color: var(--text-primary);
}

.risk-page__runline span:last-child,
.risk-page__step-card span,
.risk-page__dropzone span {
  color: var(--text-secondary);
}

.risk-page__run-badge {
  display: inline-flex;
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.risk-page__run-badge[data-tone='muted'] {
  background: rgba(125, 135, 152, 0.12);
  color: var(--text-muted);
}

.risk-page__run-badge[data-tone='active'] {
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.risk-page__run-badge[data-tone='success'] {
  background: rgba(33, 129, 92, 0.12);
  color: var(--success);
}

.risk-page__run-badge[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.12);
  color: var(--risk);
}

.risk-page__progress-rail {
  position: relative;
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: var(--surface-3);
}

.risk-page__progress-rail > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.4), rgba(36, 87, 197, 1));
  transition: width 180ms ease;
}

.risk-page__step-grid,
.risk-page__knowledge-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.risk-page__step-card,
.risk-page__dropzone {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__step-card[data-state='active'] {
  border-color: rgba(36, 87, 197, 0.28);
  box-shadow: inset 0 0 0 1px rgba(36, 87, 197, 0.08);
}

.risk-page__step-card[data-state='done'] {
  border-color: rgba(33, 129, 92, 0.24);
}

.risk-page__step-card[data-state='failed'] {
  border-color: rgba(196, 73, 61, 0.24);
}

.risk-page__dropzone {
  grid-template-columns: auto 1fr;
  align-items: center;
  background:
    radial-gradient(circle at top left, rgba(36, 87, 197, 0.1), transparent 55%),
    var(--surface-2);
}

.risk-page__dropzone-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
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

.risk-page__summary,
.risk-page__report-actions,
.risk-page__actions,
.risk-page__quality {
  display: flex;
  gap: 10px;
}

.risk-page__launcher-actions,
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

.risk-page__launcher,
.risk-page__utility-block {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
}

.risk-page__source-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.risk-page__source-switch > span,
.risk-page__knowledge-item span,
.risk-page__knowledge-item small {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__launcher-body {
  display: grid;
  gap: 12px;
}

.risk-page__launcher-actions {
  display: flex;
  gap: 10px;
}

.risk-page__knowledge-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.risk-page__knowledge-item {
  appearance: none;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-1);
  text-align: left;
  cursor: pointer;
  transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
}

.risk-page__knowledge-item:hover,
.risk-page__knowledge-item[data-active='true'] {
  border-color: rgba(36, 87, 197, 0.24);
  background: rgba(36, 87, 197, 0.06);
  transform: translateY(-1px);
}

.risk-page__knowledge-item > div {
  display: grid;
  gap: 4px;
}

.risk-page__utilities {
  gap: 14px;
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
  .risk-page__hero,
  .risk-page__summary,
  .risk-page__main,
  .risk-page__secondary,
  .risk-page__knowledge-list,
  .risk-page__source-grid,
  .risk-page__report-fields--dates {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .risk-page__hero,
  .risk-page__panel-head,
  .risk-page__step-grid,
  .risk-page__knowledge-search {
    grid-template-columns: 1fr;
  }

  .risk-page__panel-head {
    display: flex;
    flex-direction: column;
  }

  .risk-page__source-switch,
  .risk-page__launcher-actions,
  .risk-page__knowledge-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
