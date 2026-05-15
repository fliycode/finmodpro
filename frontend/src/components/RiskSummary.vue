<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import { kbApi } from '../api/knowledgebase.js';
import { riskApi } from '../api/risk.js';
import { useFlash } from '../lib/flash.js';
import { buildRiskSummaryExportDownload, downloadTextFile } from '../lib/risk-summary-export.js';
import AppSectionCard from './ui/AppSectionCard.vue';
import AppIcon from './ui/AppIcon.vue';

const flash = useFlash();
const fmt = new Intl.NumberFormat('zh-CN');
const levelPriority = { critical: 4, high: 3, medium: 2, low: 1 };
const riskTagTypeMap = { high: 'danger', critical: 'danger', medium: 'warning', low: 'success' };
const riskLevelTextMap = { critical: '严重', high: '高', medium: '中', low: '低' };
const KNOWLEDGE_DOCUMENT_PAGE_SIZE = 24;

const fileInput = ref(null);
const isUploading = ref(false);
const isGeneratingReport = ref(false);
const isLoadingKnowledgeDocuments = ref(false);
const activeDocument = ref(null);
const knowledgeDocuments = ref([]);
const selectedKnowledgeDocumentId = ref(null);
const knowledgeDocumentQuery = ref('');
const documentPickerVisible = ref(false);
const detailDialogVisible = ref(false);
const detailDialogMode = ref('event');
const activeDetailPayload = ref(null);
const resultEvents = ref([]);
const resultErrorMsg = ref('');
let knowledgeDocumentsRequestId = 0;
let knowledgeDocumentSearchTimer = null;

const createPipelineRunState = () => ({
  status: 'idle',
  fileName: '',
  documentId: null,
  detail: '等待选择文档',
  uploadProgress: 0,
  ingestProgress: 0,
  extractProgress: 0,
  createdCount: 0,
  failureCode: '',
});

const pipelineRun = ref(createPipelineRunState());

const sortDocumentsNewestFirst = (documents = []) => [...documents].sort(
  (left, right) => Number(right?.id || 0) - Number(left?.id || 0),
);

const mergeKnowledgeDocuments = (documents = []) => {
  const merged = new Map();
  documents.forEach((document) => {
    if (!document?.id) {
      return;
    }
    merged.set(String(document.id), document);
  });
  return sortDocumentsNewestFirst(Array.from(merged.values()));
};

const normalizeRiskLevel = (level) => String(level || 'low').toLowerCase();

const groupedRiskResults = computed(() => {
  const groups = new Map();

  resultEvents.value.forEach((event) => {
    const key = event.risk_type || '未分类风险';
    const current = groups.get(key);

    if (!current) {
      groups.set(key, {
        key,
        count: 1,
        dominantLevel: normalizeRiskLevel(event.risk_level),
        summary: event.summary || '暂无摘要',
        evidence: event.evidence_text || event.summary || '暂无证据文本。',
        events: [event],
      });
      return;
    }

    current.count += 1;
    current.events.push(event);
    if ((levelPriority[event.risk_level] || 0) > (levelPriority[current.dominantLevel] || 0)) {
      current.dominantLevel = event.risk_level || current.dominantLevel;
      current.summary = event.summary || current.summary;
      current.evidence = event.evidence_text || event.summary || current.evidence;
    }
  });

  return Array.from(groups.values()).sort((left, right) => {
    const levelGap = (levelPriority[right.dominantLevel] || 0) - (levelPriority[left.dominantLevel] || 0);
    if (levelGap !== 0) {
      return levelGap;
    }
    return right.count - left.count;
  });
});

const sortedRiskEvents = computed(() => [...resultEvents.value].sort((left, right) => {
  const levelGap = (levelPriority[normalizeRiskLevel(right.risk_level)] || 0)
    - (levelPriority[normalizeRiskLevel(left.risk_level)] || 0);
  if (levelGap !== 0) {
    return levelGap;
  }

  const confidenceGap = Number(right.confidence_score || 0) - Number(left.confidence_score || 0);
  if (confidenceGap !== 0) {
    return confidenceGap;
  }

  return String(right.event_time || '').localeCompare(String(left.event_time || ''));
}));

const highestRiskGroup = computed(() => groupedRiskResults.value[0] || null);
const severeEventCount = computed(() => resultEvents.value.filter(
  (event) => ['critical', 'high'].includes(String(event.risk_level || '').toLowerCase()),
).length);
const evidenceCoverage = computed(() => {
  if (!resultEvents.value.length) {
    return 0;
  }

  const coveredCount = resultEvents.value.filter((event) => Boolean(event.evidence_text || event.summary)).length;
  return Math.round((coveredCount / resultEvents.value.length) * 100);
});

const pipelinePercent = computed(() => {
  if (pipelineRun.value.status === 'idle' && !pipelineRun.value.fileName) {
    return 0;
  }

  const weighted =
    (pipelineRun.value.uploadProgress * 0.3)
    + (pipelineRun.value.ingestProgress * 0.35)
    + (pipelineRun.value.extractProgress * 0.35);

  return Math.max(
    pipelineRun.value.status === 'idle' ? 0 : 6,
    Math.min(100, Math.round(weighted)),
  );
});

const pipelineStatusText = computed(() => ({
  idle: '待命',
  uploading: '上传中',
  ingesting: '入库中',
  extracting: '提取中',
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

  return `处理中 ${Math.max(1, pipelinePercent.value)}%`;
});

const resultSubline = computed(() => {
  if (resultErrorMsg.value) {
    return resultErrorMsg.value;
  }

  if (!activeDocument.value && !pipelineRun.value.fileName) {
    return '上传或选择知识库文档后，仅展示当前文档结果';
  }

  if (isUploading.value || ['uploading', 'ingesting', 'extracting'].includes(pipelineRun.value.status)) {
    return pipelineRun.value.detail;
  }

  if (!groupedRiskResults.value.length) {
    return pipelineRun.value.status === 'succeeded'
      ? '未识别到风险事件'
      : '等待开始提取';
  }

  return `${fmt.format(groupedRiskResults.value.length)} 类风险 · ${fmt.format(resultEvents.value.length)} 条事件`;
});

const isProcessing = computed(() => ['uploading', 'ingesting', 'extracting'].includes(pipelineRun.value.status));
const selectedKnowledgeDocument = computed(() => (
  knowledgeDocuments.value.find(
    (document) => String(document.id) === String(selectedKnowledgeDocumentId.value),
  ) || null
));
const pickerDocuments = computed(() => knowledgeDocuments.value.slice(0, 12));
const canUseKnowledgeDocument = computed(() => (
  !isUploading.value
  && !isProcessing.value
  && Boolean(selectedKnowledgeDocumentId.value)
));
const knowledgeDocumentHint = computed(() => {
  if (isLoadingKnowledgeDocuments.value) {
    return '正在加载你可访问的知识库文档';
  }

  if (!knowledgeDocuments.value.length) {
    return knowledgeDocumentQuery.value
      ? '没有匹配的知识库文档'
      : '暂无可直接用于提取的知识库文档';
  }

  if (knowledgeDocumentQuery.value) {
    return `已匹配 ${fmt.format(knowledgeDocuments.value.length)} 份知识库文档`;
  }

  return `可直接复用最近 ${fmt.format(knowledgeDocuments.value.length)} 份知识库文档`;
});
const documentDisplayTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '等待选择文档');
const documentTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '当前文档');
const canExportResults = computed(() => (
  !isProcessing.value
  && !resultErrorMsg.value
  && pipelineRun.value.status === 'succeeded'
  && Boolean(activeDocument.value?.id || pipelineRun.value.fileName)
));
const exportHint = computed(() => (canExportResults.value ? '导出结果' : '提取完成后导出结果'));
const classificationHint = computed(() => (
  groupedRiskResults.value.length
    ? `${fmt.format(groupedRiskResults.value.length)} 类风险`
    : '按风险类别聚合'
));
const documentContextItems = computed(() => {
  const document = activeDocument.value;

  return [
    document?.filename || pipelineRun.value.fileName || '未选择文件',
    document?.processStep?.label || pipelineStatusText.value,
    document?.size || '大小待识别',
    groupedRiskResults.value.length ? `${fmt.format(groupedRiskResults.value.length)} 类风险` : null,
  ].filter(Boolean);
});
const detailDialogTitle = computed(() => {
  if (detailDialogMode.value === 'group') {
    return activeDetailPayload.value?.key || '风险分类详情';
  }
  return activeDetailPayload.value?.risk_type || '风险详情';
});

const summaryItems = computed(() => [
  {
    label: '风险类别',
    value: groupedRiskResults.value.length ? `${fmt.format(groupedRiskResults.value.length)} 类` : '未识别',
    note: groupedRiskResults.value.length ? '仅当前文档' : '无历史批次',
  },
  {
    label: '风险事件',
    value: pipelineRun.value.status === 'succeeded' ? `${fmt.format(resultEvents.value.length)} 条` : '等待结果',
    note: pipelineRun.value.status === 'succeeded'
      ? (severeEventCount.value ? `${fmt.format(severeEventCount.value)} 条高优先级` : '暂无高风险')
      : '等待提取',
  },
  {
    label: '最高等级',
    value: highestRiskGroup.value ? getRiskLevelText(highestRiskGroup.value.dominantLevel) : '待识别',
    note: highestRiskGroup.value ? highestRiskGroup.value.key : '等待结果',
  },
  {
    label: '证据覆盖',
    value: pipelineRun.value.status === 'succeeded' ? `${evidenceCoverage.value}%` : '等待结果',
    note: pipelineRun.value.status === 'succeeded' ? '用于报告与导出' : '完成后生成',
  },
]);

const documentFacts = computed(() => {
  const document = activeDocument.value;

  return [
    {
      label: '文件名',
      value: document?.filename || pipelineRun.value.fileName || '未选择',
    },
    {
      label: '文件体积',
      value: document?.size || '待识别',
    },
    {
      label: '数据集',
      value: document?.datasetName || '未分组',
    },
    {
      label: '知识库阶段',
      value: document?.processStep?.label || (pipelineRun.value.fileName ? '处理中' : '未开始'),
    },
    {
      label: '上传时间',
      value: document?.uploadTime || '待生成',
    },
    {
      label: '切块 / 向量',
      value: document
        ? `${fmt.format(document.chunkCount || 0)} / ${fmt.format(document.vectorCount || 0)}`
        : '待生成',
    },
  ];
});

const pipelineStages = computed(() => {
  const stateLabelMap = {
    waiting: '等待开始',
    active: '进行中',
    success: '已完成',
    warning: '需关注',
    danger: '失败',
  };
  const toneMap = {
    waiting: 'muted',
    active: 'active',
    success: 'success',
    warning: 'warning',
    danger: 'danger',
  };
  const extractionFailed = (
    pipelineRun.value.status === 'failed'
    || ['risk_extraction_busy', 'risk_extraction_timeout', 'risk_extraction_stage_timeout', 'risk_extraction_queue_timeout', 'risk_extraction_poll_timeout']
      .includes(pipelineRun.value.failureCode)
  );

  const resolveState = (stageKey) => {
    if (stageKey === 'upload') {
      if (pipelineRun.value.status === 'uploading') {
        return 'active';
      }
      if (pipelineRun.value.fileName || pipelineRun.value.uploadProgress > 0 || activeDocument.value) {
        return 'success';
      }
      return 'waiting';
    }

    if (stageKey === 'ingest') {
      if (pipelineRun.value.status === 'ingesting') {
        return 'active';
      }
      if (
        ['extracting', 'succeeded', 'busy', 'timed_out'].includes(pipelineRun.value.status)
        || pipelineRun.value.ingestProgress >= 100
        || activeDocument.value?.status === 'indexed'
      ) {
        return 'success';
      }
      if (pipelineRun.value.status === 'failed' && (pipelineRun.value.ingestProgress > 0 || activeDocument.value)) {
        return 'danger';
      }
      return 'waiting';
    }

    if (pipelineRun.value.status === 'extracting') {
      return 'active';
    }
    if (pipelineRun.value.status === 'succeeded') {
      return 'success';
    }
    if (['busy', 'timed_out'].includes(pipelineRun.value.status)) {
      return 'warning';
    }
    if (extractionFailed && (pipelineRun.value.extractProgress > 0 || pipelineRun.value.documentId)) {
      return 'danger';
    }
    return 'waiting';
  };

  return [
    {
      key: 'upload',
      icon: 'upload',
      label: '1 选择文档',
      note: pipelineRun.value.fileName || '支持上传文件或复用知识库文档',
      progress: pipelineRun.value.uploadProgress,
    },
    {
      key: 'ingest',
      icon: 'database',
      label: '2 入库索引',
      note: activeDocument.value?.processStep?.detail || '写入知识库并等待索引完成',
      progress: activeDocument.value?.processStep?.progress ?? pipelineRun.value.ingestProgress,
    },
    {
      key: 'extract',
      icon: 'shield',
      label: '3 风险提取',
      note: highestRiskGroup.value
        ? `当前重点：${highestRiskGroup.value.key}`
        : '抽取事件并聚合为可审阅摘要',
      progress: pipelineRun.value.extractProgress,
    },
  ].map((stage) => {
    const state = resolveState(stage.key);
    let statusText = stateLabelMap[state];

    if (stage.key === 'ingest' && state === 'active' && activeDocument.value?.processStep?.label) {
      statusText = activeDocument.value.processStep.label;
    }

    if (stage.key === 'extract' && state !== 'waiting') {
      statusText = pipelineStatusText.value;
    }

    return {
      ...stage,
      state,
      tone: toneMap[state],
      statusText,
      progressText: state === 'success'
        ? '100%'
        : (state === 'waiting' ? '—' : `${Math.max(0, Math.min(100, Math.round(stage.progress || 0)))}%`),
    };
  });
});

const resultSpotlight = computed(() => {
  if (!highestRiskGroup.value) {
    return null;
  }

  return {
    title: highestRiskGroup.value.key,
    levelKey: highestRiskGroup.value.dominantLevel,
    levelText: getRiskLevelText(highestRiskGroup.value.dominantLevel),
    summary: highestRiskGroup.value.summary || '暂无摘要',
    evidence: highestRiskGroup.value.evidence || highestRiskGroup.value.summary || '暂无证据文本。',
    countText: `${fmt.format(highestRiskGroup.value.count)} 条事件`,
  };
});

const resultListCaption = computed(() => (
  groupedRiskResults.value.length
    ? `${fmt.format(groupedRiskResults.value.length)} 类风险按优先级排序`
    : '按等级与事件数排序'
));

const uploadActionLabel = computed(() => (
  activeDocument.value || pipelineRun.value.fileName ? '重新上传' : '上传文档'
));

const canGenerateReport = computed(() => (
  !isProcessing.value
  && !resultErrorMsg.value
  && pipelineRun.value.status === 'succeeded'
  && Boolean(activeDocument.value?.id)
  && resultEvents.value.length > 0
));

const documentSourceFacts = computed(() => [
  {
    label: '文件类型',
    value: (activeDocument.value?.docType || pipelineRun.value.fileName?.split('.').pop() || '未知').toUpperCase(),
  },
  {
    label: '文件体积',
    value: activeDocument.value?.size || '待识别',
  },
  {
    label: '来源日期',
    value: activeDocument.value?.sourceDate || '待生成',
  },
  {
    label: '切块 / 向量',
    value: activeDocument.value
      ? `${fmt.format(activeDocument.value.chunkCount || 0)} / ${fmt.format(activeDocument.value.vectorCount || 0)}`
      : '待生成',
  },
]);

const previewMode = computed(() => {
  if (activeDocument.value?.docType === 'pdf' && activeDocument.value?.previewUrl) {
    return 'pdf';
  }
  return 'text';
});

const documentPreviewText = computed(() => (
  activeDocument.value?.parsedTextPreview
  || activeDocument.value?.processResult
  || pipelineRun.value.detail
  || '上传或选择知识库文档后在这里查看预览。'
));

const updatePipelineRun = (patch) => {
  pipelineRun.value = {
    ...pipelineRun.value,
    ...patch,
  };
};

const resetPipelineRun = () => {
  pipelineRun.value = createPipelineRunState();
  activeDocument.value = null;
  resultEvents.value = [];
  resultErrorMsg.value = '';
};

const upsertKnowledgeDocument = (document) => {
  if (!document?.id) {
    return;
  }

  knowledgeDocuments.value = mergeKnowledgeDocuments([document, ...knowledgeDocuments.value]);
};

const fetchKnowledgeDocuments = async ({ searchKeyword = '' } = {}) => {
  const requestId = ++knowledgeDocumentsRequestId;
  isLoadingKnowledgeDocuments.value = true;

  try {
    const result = await kbApi.listDocuments({
      searchKeyword,
      page: 1,
      pageSize: KNOWLEDGE_DOCUMENT_PAGE_SIZE,
    });

    if (requestId !== knowledgeDocumentsRequestId) {
      return;
    }

    const nextDocuments = mergeKnowledgeDocuments([
      ...result.documents,
      ...(activeDocument.value ? [activeDocument.value] : []),
      ...(selectedKnowledgeDocument.value ? [selectedKnowledgeDocument.value] : []),
    ]);

    knowledgeDocuments.value = nextDocuments;

    if (
      selectedKnowledgeDocumentId.value
      && !nextDocuments.some(
        (document) => String(document.id) === String(selectedKnowledgeDocumentId.value),
      )
    ) {
      selectedKnowledgeDocumentId.value = null;
    }
  } catch (error) {
    if (requestId !== knowledgeDocumentsRequestId) {
      return;
    }
    flash.error(error.message || '加载知识库文档失败，请稍后重试');
  } finally {
    if (requestId === knowledgeDocumentsRequestId) {
      isLoadingKnowledgeDocuments.value = false;
    }
  }
};

const queueKnowledgeDocumentSearch = (searchKeyword = '') => {
  if (knowledgeDocumentSearchTimer) {
    clearTimeout(knowledgeDocumentSearchTimer);
  }

  knowledgeDocumentSearchTimer = setTimeout(() => {
    fetchKnowledgeDocuments({ searchKeyword });
  }, 250);
};

const handleKnowledgeDocumentQuery = (query = '') => {
  knowledgeDocumentQuery.value = query.trim();
  queueKnowledgeDocumentSearch(knowledgeDocumentQuery.value);
};

const formatKnowledgeDocumentMeta = (document) => [
  document.processStep?.label || '已上传',
  document.datasetName || '未分组',
  document.size || '大小待识别',
].filter(Boolean).join(' · ');

const formatRiskEventTime = (value) => {
  if (!value) {
    return '时间待补充';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '时间待补充';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date).replace(/\//g, '-');
};

const formatConfidenceScore = (value) => {
  const score = Number(value);
  if (!Number.isFinite(score) || score <= 0) {
    return '置信度待补充';
  }
  return `置信度 ${Math.round(score * 100)}%`;
};

const openRiskEventDetail = (event) => {
  activeDetailPayload.value = event;
  detailDialogMode.value = 'event';
  detailDialogVisible.value = true;
};

const openRiskGroupDetail = (group) => {
  activeDetailPayload.value = group;
  detailDialogMode.value = 'group';
  detailDialogVisible.value = true;
};

const handleUploadCommand = (command) => {
  if (command === 'knowledge') {
    documentPickerVisible.value = true;
    fetchKnowledgeDocuments({ searchKeyword: knowledgeDocumentQuery.value });
    return;
  }
  triggerUpload();
};

const triggerUpload = () => fileInput.value?.click();

const startPipelineRun = (file) => {
  pipelineRun.value = {
    ...createPipelineRunState(),
    status: 'uploading',
    fileName: file.name,
    detail: '正在接收文件',
  };
  activeDocument.value = null;
  resultEvents.value = [];
  resultErrorMsg.value = '';
};

const syncActiveDocument = async (documentId) => {
  const document = await kbApi.getDocumentDetail(documentId);
  activeDocument.value = document;
  selectedKnowledgeDocumentId.value = document.id;
  upsertKnowledgeDocument(document);

  updatePipelineRun({
    documentId,
    status: document.processStep?.code === 'failed'
      ? 'failed'
      : (pipelineRun.value.status === 'uploading' ? 'ingesting' : pipelineRun.value.status),
    ingestProgress: document.processStep?.progress ?? pipelineRun.value.ingestProgress,
    detail: document.processStep?.detail || pipelineRun.value.detail,
  });

  return document;
};

const fetchDocumentEvents = async (documentId) => {
  const data = await riskApi.getEvents({ document_id: documentId });
  resultEvents.value = data.data?.risk_events || data.risk_events || [];
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
    extractProgress: resolvedProgress,
    detail: payload.message || pipelineRun.value.detail,
    createdCount: payload.result?.created_count ?? pipelineRun.value.createdCount,
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
    detail: error?.message || '提取失败',
    failureCode,
  });
  resultErrorMsg.value = error?.message || '提取失败';
};

const notifyPipelineFailure = (error, fallback) => {
  if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
    flash.warning(error.message || fallback);
    return;
  }

  flash.error(error.message || fallback);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const pollDocumentIndexed = async (documentId, { timeout = 60000, interval = 2000 } = {}) => {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    const document = await syncActiveDocument(documentId);
    const status = String(document.status || '').toLowerCase();

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
      upsertKnowledgeDocument(ingestPayload.document);
      updatePipelineRun({
        status: 'ingesting',
        documentId,
        ingestProgress: ingestPayload.document.processStep?.progress ?? pipelineRun.value.ingestProgress,
        detail: ingestPayload.document.processStep?.detail || '文件已保存，正在提交入库任务',
      });
    }

    await pollDocumentIndexed(documentId);
  } else {
    updatePipelineRun({
      status: 'extracting',
      documentId,
      ingestProgress: 100,
      detail: '文档已入库，准备开始风险提取',
    });
  }

  updatePipelineRun({
    status: 'extracting',
    extractProgress: 6,
    detail: '正在分析文档中的风险事件',
  });

  const result = await riskApi.extractDocumentWithPolling(documentId, {
    onProgress: applyExtractionProgress,
  });

  applyExtractionProgress({
    status: 'SUCCESS',
    progress: 100,
    message: result.message || (result.created_count ? '风险提取完成' : '未识别到风险事件'),
    result,
  });

  await fetchDocumentEvents(documentId);
  flash.success('风险提取完成');
};

const useExistingDocument = async (documentInfo, fallbackName) => {
  isUploading.value = true;
  resultEvents.value = [];
  resultErrorMsg.value = '';
  selectedKnowledgeDocumentId.value = documentInfo.id;
  upsertKnowledgeDocument(documentInfo);

  updatePipelineRun({
    ...createPipelineRunState(),
    fileName: documentInfo.filename || documentInfo.title || fallbackName,
    uploadProgress: 100,
    documentId: documentInfo.id,
    status: 'ingesting',
    detail: '正在切换到已存在的文档',
  });

  try {
    await syncActiveDocument(documentInfo.id);
    await runRiskPipeline(documentInfo.id);
  } catch (error) {
    applyPipelineFailure(error);
    notifyPipelineFailure(error, '使用已有文档失败');
  } finally {
    isUploading.value = false;
  }
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
      selectedKnowledgeDocumentId.value = documentId;
      upsertKnowledgeDocument(result.document);
      updatePipelineRun({
        uploadProgress: 100,
        status: 'ingesting',
        documentId,
        ingestProgress: result.document.processStep?.progress ?? 0,
        detail: '文件已保存，正在准备提取',
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
        if (event.target) {
          event.target.value = '';
        }
        isUploading.value = false;
        return;
      }

      await useExistingDocument(error.existingDocument, file.name);
      if (event.target) {
        event.target.value = '';
      }
      return;
    }

    applyPipelineFailure(error);
    notifyPipelineFailure(error, '上传或提取失败');
  } finally {
    isUploading.value = false;
    if (event.target) {
      event.target.value = '';
    }
  }
};

const handleUseKnowledgeDocument = async () => {
  if (!selectedKnowledgeDocumentId.value) {
    flash.warning('请先选择知识库文档');
    return;
  }

  try {
    const selectedDocument = selectedKnowledgeDocument.value
      || await kbApi.getDocumentDetail(selectedKnowledgeDocumentId.value);

    documentPickerVisible.value = false;
    await useExistingDocument(
      selectedDocument,
      selectedDocument.filename || selectedDocument.title || '知识库文档',
    );
  } catch (error) {
    flash.error(error.message || '加载知识库文档失败，请稍后重试');
  }
};

onMounted(() => {
  fetchKnowledgeDocuments();
});

onBeforeUnmount(() => {
  if (knowledgeDocumentSearchTimer) {
    clearTimeout(knowledgeDocumentSearchTimer);
  }
});

const getRiskTagType = (level) => riskTagTypeMap[level] || 'info';
const getRiskLevelText = (level) => riskLevelTextMap[level] || level;

const handleExport = () => {
  if (!canExportResults.value) {
    flash.warning('提取完成后才可导出结果');
    return;
  }

  try {
    downloadTextFile(buildRiskSummaryExportDownload({
      documentTitle: documentTitle.value,
      statusText: pipelineStatusText.value,
      detail: resultSubline.value,
      groupedResults: groupedRiskResults.value,
      resultEvents: resultEvents.value,
      createdCount: pipelineRun.value.createdCount || resultEvents.value.length,
    }));
    flash.success('导出文件已生成');
  } catch (error) {
    console.error('导出风险提取结果失败:', error);
    flash.error('导出结果失败，请稍后重试');
  }
};

const handleGenerateReport = async () => {
  if (!canGenerateReport.value) {
    flash.warning('提取完成并识别到风险后才可生成报告');
    return;
  }

  isGeneratingReport.value = true;
  try {
    const payload = await riskApi.generateDocumentReport(activeDocument.value.id);
    const report = payload?.data?.report || payload?.report || null;
    if (!report?.id) {
      throw new Error('未获取到报告结果');
    }

    const attachment = await riskApi.exportReport(report.id);
    downloadTextFile(attachment);
    flash.success('风险报告已生成');
  } catch (error) {
    flash.error(error.message || '生成风险报告失败，请稍后重试');
  } finally {
    isGeneratingReport.value = false;
  }
};
</script>

<template>
  <div class="risk-page">
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.docx,.txt"
      class="risk-page__file-input"
      @change="handleFileChange"
      aria-hidden="true"
      tabindex="-1"
    />

    <section class="risk-page__toolbar">
      <el-dropdown trigger="click" @command="handleUploadCommand">
        <el-button class="risk-page__toolbar-button" :loading="isUploading" aria-label="上传文档">
          <AppIcon name="upload" />
          上传文档
          <AppIcon name="chevron-down" />
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="knowledge">从知识库选择</el-dropdown-item>
            <el-dropdown-item command="direct">直接上传</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button plain class="risk-page__toolbar-button" :disabled="!canExportResults" @click="handleExport">
        <AppIcon name="download" />
        {{ exportHint }}
      </el-button>
    </section>

    <section class="risk-page__studio">
      <AppSectionCard
        class="risk-page__info-card"
        title="风险信息"
        :desc="documentDisplayTitle"
        icon="file-text"
      >
        <template #header>
          <div class="risk-page__context-bar">
            <span
              v-for="item in documentContextItems"
              :key="item"
              class="risk-page__context-pill"
            >
              {{ item }}
            </span>
          </div>
        </template>

        <div v-if="resultErrorMsg" class="risk-page__state risk-page__state--error" role="alert">
          <strong>提取失败</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="!activeDocument && !pipelineRun.fileName" class="risk-page__state" role="status" aria-live="polite">
          <strong>先选择一份文档</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="isProcessing" class="risk-page__state" role="status" aria-live="polite">
          <strong>{{ pipelineRun.fileName || activeDocument?.title || '正在处理文档' }}</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <template v-else-if="sortedRiskEvents.length">
          <div class="risk-page__summary-strip" aria-label="风险摘要">
            <div
              v-for="item in summaryItems"
              :key="item.label"
              class="risk-page__summary-card"
            >
              <span class="risk-page__summary-label">{{ item.label }}</span>
              <strong class="risk-page__summary-value">{{ item.value }}</strong>
              <span class="risk-page__summary-note">{{ item.note }}</span>
            </div>
          </div>

          <ol class="risk-page__insight-list">
            <li
              v-for="event in sortedRiskEvents"
              :key="`${event.id || event.risk_type}-${event.event_time || event.summary}`"
            >
              <button
                type="button"
                class="risk-page__insight"
                :data-tone="riskTagTypeMap[normalizeRiskLevel(event.risk_level)] || 'muted'"
                @click="openRiskEventDetail(event)"
              >
                <div class="risk-page__insight-head">
                  <div class="risk-page__insight-meta">
                    <span class="risk-page__status" :data-tone="riskTagTypeMap[normalizeRiskLevel(event.risk_level)] || 'muted'">
                      {{ getRiskLevelText(normalizeRiskLevel(event.risk_level)) }}
                    </span>
                    <strong>{{ event.risk_type || '未分类风险' }}</strong>
                    <span>{{ formatRiskEventTime(event.event_time) }}</span>
                  </div>
                  <span class="risk-page__insight-confidence">{{ formatConfidenceScore(event.confidence_score) }}</span>
                </div>

                <p class="risk-page__insight-summary">{{ event.summary || '暂无摘要' }}</p>
                <p class="risk-page__insight-evidence">
                  <mark :data-tone="riskTagTypeMap[normalizeRiskLevel(event.risk_level)] || 'muted'">
                    {{ event.evidence_text || event.summary || '暂无证据文本。' }}
                  </mark>
                </p>
              </button>
            </li>
          </ol>

          <div class="risk-page__document-note">
            <span class="risk-page__heading-note">原文片段</span>
            <p>{{ documentPreviewText }}</p>
          </div>
        </template>

        <iframe
          v-else-if="previewMode === 'pdf' && activeDocument?.previewUrl"
          class="risk-page__preview-frame"
          :src="activeDocument.previewUrl"
          title="文档预览"
          loading="lazy"
        />

        <div v-else class="risk-page__text-preview">
          <pre>{{ documentPreviewText }}</pre>
        </div>
      </AppSectionCard>

      <AppSectionCard
        class="risk-page__classification-card"
        title="风险分类"
        :desc="classificationHint"
        icon="shield"
      >
        <div v-if="resultErrorMsg" class="risk-page__state risk-page__state--error" role="alert">
          <strong>提取失败</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="!activeDocument && !pipelineRun.fileName" class="risk-page__state" role="status" aria-live="polite">
          <strong>等待分类结果</strong>
          <p>选择文档后，这里会按风险类别聚合。</p>
        </div>

        <div v-else-if="isProcessing" class="risk-page__state" role="status" aria-live="polite">
          <strong>正在聚合分类</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <ol v-else-if="groupedRiskResults.length" class="risk-page__category-list">
          <li v-for="group in groupedRiskResults" :key="group.key">
            <button
              type="button"
              class="risk-page__category"
              :data-tone="riskTagTypeMap[normalizeRiskLevel(group.dominantLevel)] || 'muted'"
              @click="openRiskGroupDetail(group)"
            >
              <div class="risk-page__category-head">
                <strong>{{ group.key }}</strong>
                <span class="risk-page__status" :data-tone="riskTagTypeMap[normalizeRiskLevel(group.dominantLevel)] || 'muted'">
                  {{ getRiskLevelText(normalizeRiskLevel(group.dominantLevel)) }}
                </span>
              </div>
              <p>{{ group.summary }}</p>
              <div class="risk-page__category-meta">
                <span>{{ group.count }} 条事件</span>
                <span>点击查看详情</span>
              </div>
            </button>
          </li>
        </ol>

        <div v-else class="risk-page__state" role="status" aria-live="polite">
          <strong>{{ activeDocument?.title || '当前文档' }}</strong>
          <p>{{ resultSubline }}</p>
        </div>
      </AppSectionCard>
    </section>

    <el-dialog
      v-model="documentPickerVisible"
      title="从知识库选择"
      width="680px"
      class="risk-page__dialog"
      destroy-on-close
    >
      <div class="risk-page__picker">
        <label class="risk-page__field">
          <span class="risk-page__field-label">搜索知识库文档</span>
          <el-input
            v-model="knowledgeDocumentQuery"
            clearable
            placeholder="搜索标题、文件名或正文片段"
            @input="handleKnowledgeDocumentQuery"
          >
            <template #prefix>
              <AppIcon name="search" />
            </template>
          </el-input>
        </label>

        <p class="risk-page__picker-hint">{{ knowledgeDocumentHint }}</p>

        <ol v-if="pickerDocuments.length" class="risk-page__picker-list">
          <li v-for="document in pickerDocuments" :key="document.id">
            <button
              type="button"
              class="risk-page__picker-item"
              :data-selected="String(selectedKnowledgeDocumentId) === String(document.id)"
              @click="selectedKnowledgeDocumentId = document.id"
            >
              <div class="risk-page__picker-item-head">
                <strong>{{ document.title }}</strong>
                <span class="risk-page__status" :data-tone="document.isSearchReady ? 'success' : 'muted'">
                  {{ document.processStep?.label || '已上传' }}
                </span>
              </div>
              <span>{{ document.filename }}</span>
              <p>{{ formatKnowledgeDocumentMeta(document) }}</p>
            </button>
          </li>
        </ol>

        <div v-else class="risk-page__state" role="status" aria-live="polite">
          <strong>没有匹配的文档</strong>
          <p>可以换个关键词，或直接上传新文件。</p>
        </div>
      </div>

      <template #footer>
        <div class="risk-page__dialog-actions">
          <el-button @click="documentPickerVisible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="!canUseKnowledgeDocument"
            :loading="isUploading"
            @click="handleUseKnowledgeDocument"
          >
            使用并提取
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailDialogVisible"
      :title="detailDialogTitle"
      width="720px"
      class="risk-page__dialog"
      destroy-on-close
    >
      <div v-if="detailDialogMode === 'event' && activeDetailPayload" class="risk-page__detail">
        <div class="risk-page__detail-head">
          <span class="risk-page__status" :data-tone="riskTagTypeMap[normalizeRiskLevel(activeDetailPayload.risk_level)] || 'muted'">
            {{ getRiskLevelText(normalizeRiskLevel(activeDetailPayload.risk_level)) }}
          </span>
          <span>{{ formatRiskEventTime(activeDetailPayload.event_time) }}</span>
          <span>{{ formatConfidenceScore(activeDetailPayload.confidence_score) }}</span>
        </div>

        <div class="risk-page__detail-section">
          <span class="risk-page__field-label">摘要</span>
          <p>{{ activeDetailPayload.summary || '暂无摘要' }}</p>
        </div>

        <div class="risk-page__detail-section">
          <span class="risk-page__field-label">证据</span>
          <p class="risk-page__detail-evidence">{{ activeDetailPayload.evidence_text || activeDetailPayload.summary || '暂无证据文本。' }}</p>
        </div>
      </div>

      <div v-else-if="activeDetailPayload" class="risk-page__detail">
        <div class="risk-page__detail-head">
          <span class="risk-page__status" :data-tone="riskTagTypeMap[normalizeRiskLevel(activeDetailPayload.dominantLevel)] || 'muted'">
            {{ getRiskLevelText(normalizeRiskLevel(activeDetailPayload.dominantLevel)) }}
          </span>
          <span>{{ activeDetailPayload.count }} 条事件</span>
        </div>

        <div class="risk-page__detail-section">
          <span class="risk-page__field-label">分类摘要</span>
          <p>{{ activeDetailPayload.summary || '暂无摘要' }}</p>
        </div>

        <ol class="risk-page__detail-list">
          <li
            v-for="event in activeDetailPayload.events || []"
            :key="`${event.id || event.summary}-${event.event_time || ''}`"
          >
            <button type="button" class="risk-page__detail-item" @click="openRiskEventDetail(event)">
              <div class="risk-page__detail-item-head">
                <strong>{{ event.summary || event.risk_type || '风险事件' }}</strong>
                <span>{{ formatRiskEventTime(event.event_time) }}</span>
              </div>
              <p>{{ event.evidence_text || '暂无证据文本。' }}</p>
            </button>
          </li>
        </ol>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.risk-page {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.risk-page :deep(.section-heading__main) {
  min-width: 0;
}

.risk-page :deep(.section-heading__desc) {
  max-width: 68ch;
  overflow-wrap: anywhere;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__toolbar,
.risk-page__context-bar,
.risk-page__insight-head,
.risk-page__insight-meta,
.risk-page__category-head,
.risk-page__category-meta,
.risk-page__detail-head,
.risk-page__detail-item-head,
.risk-page__dialog-actions,
.risk-page__picker-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.risk-page__toolbar {
  flex-wrap: wrap;
}

.risk-page__toolbar-button {
  min-height: 44px;
}

.risk-page__studio {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(320px, 0.95fr);
  gap: 20px;
  align-items: start;
}

.risk-page__info-card :deep(.el-card__body),
.risk-page__classification-card :deep(.el-card__body) {
  display: grid;
  gap: 20px;
}

.risk-page__info-card :deep(.section-heading--card) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.risk-page__info-card :deep(.section-heading__meta) {
  margin-left: 0;
  min-width: 0;
}

.risk-page__context-bar {
  flex-wrap: wrap;
  justify-content: flex-start;
  row-gap: 8px;
}

.risk-page__context-pill,
.risk-page__heading-note,
.risk-page__picker-hint,
.risk-page__field-label {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.risk-page__context-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
}

.risk-page__summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  overflow: hidden;
  background: color-mix(in oklab, var(--surface-2) 90%, var(--surface-3));
}

.risk-page__summary-card,
.risk-page__document-note,
.risk-page__state,
.risk-page__detail-section,
.risk-page__picker-item,
.risk-page__detail-item {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.risk-page__summary-card {
  padding: 16px 18px;
  background: transparent;
}

.risk-page__summary-card + .risk-page__summary-card {
  border-inline-start: 1px solid var(--line-soft);
}

.risk-page__summary-label,
.risk-page__summary-note,
.risk-page__document-note p,
.risk-page__state p,
.risk-page__category p,
.risk-page__picker-item span,
.risk-page__picker-item p,
.risk-page__detail-section p,
.risk-page__detail-item p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__summary-value,
.risk-page__insight strong,
.risk-page__category strong,
.risk-page__state strong,
.risk-page__picker-item strong,
.risk-page__detail-section,
.risk-page__detail-item strong {
  color: var(--text-primary);
}

.risk-page__insight-list,
.risk-page__category-list,
.risk-page__picker-list,
.risk-page__detail-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  overflow: hidden;
  background: color-mix(in oklab, var(--surface-2) 92%, var(--surface-3));
}

.risk-page__insight-list > li,
.risk-page__category-list > li,
.risk-page__picker-list > li,
.risk-page__detail-list > li {
  min-width: 0;
}

.risk-page__insight-list > li + li,
.risk-page__category-list > li + li,
.risk-page__picker-list > li + li,
.risk-page__detail-list > li + li {
  border-top: 1px solid var(--line-soft);
}

.risk-page__insight,
.risk-page__category,
.risk-page__picker-item,
.risk-page__detail-item {
  width: 100%;
  padding: 18px 20px;
  border: none;
  border-radius: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 180ms ease, color 180ms ease;
}

.risk-page__insight:hover,
.risk-page__category:hover,
.risk-page__picker-item:hover,
.risk-page__detail-item:hover {
  background: color-mix(in oklab, var(--brand-soft) 36%, var(--surface-hover));
}

.risk-page__insight:focus-visible,
.risk-page__category:focus-visible,
.risk-page__picker-item:focus-visible,
.risk-page__detail-item:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--brand) 64%, white);
  outline-offset: -2px;
}

.risk-page__insight[data-tone='danger'],
.risk-page__category[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.04);
}

.risk-page__insight[data-tone='warning'],
.risk-page__category[data-tone='warning'] {
  background: rgba(186, 128, 40, 0.05);
}

.risk-page__insight[data-tone='success'],
.risk-page__category[data-tone='success'] {
  background: rgba(33, 129, 92, 0.04);
}

.risk-page__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}

.risk-page__status[data-tone='muted'] {
  background: rgba(125, 135, 152, 0.12);
  color: var(--text-muted);
}

.risk-page__status[data-tone='active'] {
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.risk-page__status[data-tone='success'] {
  background: rgba(33, 129, 92, 0.12);
  color: var(--success);
}

.risk-page__status[data-tone='warning'] {
  background: rgba(186, 128, 40, 0.14);
  color: var(--warning);
}

.risk-page__status[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.12);
  color: var(--risk);
}

.risk-page__insight-meta,
.risk-page__category-meta,
.risk-page__detail-head,
.risk-page__insight-confidence {
  flex-wrap: wrap;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__insight-summary,
.risk-page__insight-evidence {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.7;
}

.risk-page__insight-evidence mark,
.risk-page__detail-evidence {
  display: inline-block;
  padding: 6px 8px;
  border-radius: 8px;
  color: var(--text-primary);
  background: rgba(36, 87, 197, 0.08);
}

.risk-page__insight-evidence mark[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.12);
}

.risk-page__insight-evidence mark[data-tone='warning'] {
  background: rgba(186, 128, 40, 0.14);
}

.risk-page__insight-evidence mark[data-tone='success'] {
  background: rgba(33, 129, 92, 0.12);
}

.risk-page__document-note,
.risk-page__text-preview,
.risk-page__preview-frame {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: color-mix(in oklab, var(--surface-2) 90%, var(--surface-3));
}

.risk-page__text-preview pre {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--text-primary);
}

.risk-page__preview-frame {
  width: 100%;
  min-height: 620px;
}

.risk-page__state {
  align-content: center;
  min-height: 220px;
  padding: 24px;
  border-radius: 18px;
  border: 1px solid var(--line-soft);
  background: color-mix(in oklab, var(--surface-2) 90%, var(--surface-3));
}

.risk-page__state--error {
  background: rgba(196, 73, 61, 0.06);
}

.risk-page__picker {
  display: grid;
  gap: 14px;
}

.risk-page__field {
  display: grid;
  gap: 8px;
}

.risk-page__picker-item[data-selected='true'] {
  background: color-mix(in oklab, var(--brand) 6%, var(--surface-2));
}

.risk-page__detail {
  display: grid;
  gap: 16px;
}

.risk-page__detail-head {
  justify-content: flex-start;
}

.risk-page__detail-item-head {
  align-items: flex-start;
}

.risk-page__dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}

@media (max-width: 1200px) {
  .risk-page__studio {
    grid-template-columns: minmax(0, 1fr);
  }

  .risk-page__info-card :deep(.section-heading--card) {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .risk-page__summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .risk-page__summary-strip {
    grid-template-columns: minmax(0, 1fr);
  }

  .risk-page__toolbar,
  .risk-page__insight-head,
  .risk-page__category-head,
  .risk-page__category-meta,
  .risk-page__picker-item-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .risk-page__preview-frame {
    min-height: 460px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .risk-page__insight,
  .risk-page__category,
  .risk-page__picker-item,
  .risk-page__detail-item {
    transition: none;
  }
}
</style>
