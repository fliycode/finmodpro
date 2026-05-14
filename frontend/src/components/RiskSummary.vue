<script setup>
import { computed, ref } from 'vue';
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

const fileInput = ref(null);
const isUploading = ref(false);
const activeDocument = ref(null);
const resultEvents = ref([]);
const resultErrorMsg = ref('');

const createPipelineRunState = () => ({
  status: 'idle',
  fileName: '',
  documentId: null,
  detail: '等待上传文档',
  uploadProgress: 0,
  ingestProgress: 0,
  extractProgress: 0,
  createdCount: 0,
  failureCode: '',
});

const pipelineRun = ref(createPipelineRunState());

const groupedRiskResults = computed(() => {
  const groups = new Map();

  resultEvents.value.forEach((event) => {
    const key = event.risk_type || '未分类风险';
    const current = groups.get(key);

    if (!current) {
      groups.set(key, {
        key,
        count: 1,
        dominantLevel: event.risk_level || 'low',
        summary: event.summary || '暂无摘要',
        evidence: event.evidence_text || event.summary || '暂无证据文本。',
      });
      return;
    }

    current.count += 1;
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
    return '上传后仅展示当前文档结果';
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
const documentDisplayTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '等待上传文档');
const documentTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '当前文档');
const canExportResults = computed(() => (
  !isProcessing.value
  && !resultErrorMsg.value
  && pipelineRun.value.status === 'succeeded'
  && Boolean(activeDocument.value?.id || pipelineRun.value.fileName)
));
const exportHint = computed(() => (
  canExportResults.value
    ? '导出 Markdown 留痕摘要'
    : '提取完成后导出当前文档'
));

const summaryItems = computed(() => [
  {
    label: '最高等级',
    value: highestRiskGroup.value ? getRiskLevelText(highestRiskGroup.value.dominantLevel) : '待识别',
    note: highestRiskGroup.value ? highestRiskGroup.value.key : '等待结果',
  },
  {
    label: '风险类别',
    value: groupedRiskResults.value.length ? `${fmt.format(groupedRiskResults.value.length)} 类` : '未识别',
    note: groupedRiskResults.value.length ? '仅当前文档' : '无历史批次',
  },
  {
    label: '高优先事件',
    value: pipelineRun.value.status === 'succeeded' ? `${fmt.format(severeEventCount.value)} 条` : '等待结果',
    note: pipelineRun.value.status === 'succeeded'
      ? (severeEventCount.value ? '优先复核' : '暂无高风险')
      : '等待提取',
  },
  {
    label: '导出准备',
    value: canExportResults.value ? '已就绪' : '未就绪',
    note: canExportResults.value ? `覆盖 ${evidenceCoverage.value}%` : '等待完成',
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
      label: '1 上传文档',
      note: pipelineRun.value.fileName || '支持 PDF / DOCX / TXT',
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

const exportStatusText = computed(() => (
  canExportResults.value
    ? '可导出'
    : (resultErrorMsg.value ? '失败' : (isProcessing.value ? '生成中' : '待完成'))
));

const exportStatusTone = computed(() => (
  canExportResults.value
    ? 'success'
    : (resultErrorMsg.value ? 'danger' : (isProcessing.value ? 'active' : 'muted'))
));

const reviewChecklist = computed(() => [
  {
    label: '链路状态',
    value: pipelineStatusText.value,
    note: pipelineRun.value.detail || '等待上传',
  },
  {
    label: '最高风险',
    value: resultSpotlight.value?.title || '待识别',
    note: resultSpotlight.value
      ? `${resultSpotlight.value.levelText} · ${resultSpotlight.value.countText}`
      : '完成后自动定位',
  },
  {
    label: '留痕摘要',
    value: canExportResults.value ? '可生成' : '未完成',
    note: canExportResults.value ? `证据覆盖 ${evidenceCoverage.value}%` : exportHint.value,
  },
]);

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

    <section class="risk-page__bench" :aria-busy="isProcessing ? 'true' : 'false'">
      <div class="risk-page__bench-header">
        <div class="risk-page__bench-copy">
          <span class="risk-page__eyebrow">风险提取工作台</span>
          <h2>单文档判读链路</h2>
          <p>上传后自动入库、提取，并收束成一份可复核摘要。</p>
        </div>

        <div class="risk-page__bench-actions">
          <span class="risk-page__status" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
          <el-button type="primary" :loading="isUploading" @click="triggerUpload">
            <AppIcon name="upload" />
            {{ uploadButtonLabel }}
          </el-button>
        </div>
      </div>

      <div class="risk-page__bench-body">
        <div class="risk-page__chain-state">
          <span class="risk-page__eyebrow">当前链路</span>
          <strong class="risk-page__chain-title">{{ documentDisplayTitle }}</strong>
          <div class="risk-page__chain-meta">
            <span class="risk-page__chain-percent">{{ pipelinePercent }}%</span>
            <p class="risk-page__chain-detail">{{ resultSubline }}</p>
          </div>
          <div
            class="risk-page__progress"
            role="progressbar"
            :aria-valuenow="pipelinePercent"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-label="风险提取总进度"
          >
            <span :style="{ width: `${pipelinePercent}%` }" />
          </div>
        </div>

        <ol class="risk-page__pipeline-list" aria-label="处理链路">
          <li
            v-for="stage in pipelineStages"
            :key="stage.key"
            class="risk-page__pipeline-item"
            :data-tone="stage.tone"
          >
            <div class="risk-page__pipeline-top">
              <span class="risk-page__pipeline-icon" aria-hidden="true">
                <AppIcon :name="stage.icon" />
              </span>
              <span class="risk-page__status" :data-tone="stage.tone">{{ stage.statusText }}</span>
            </div>
            <div class="risk-page__pipeline-copy">
              <strong>{{ stage.label }}</strong>
              <p>{{ stage.note }}</p>
            </div>
            <span class="risk-page__pipeline-progress">{{ stage.progressText }}</span>
          </li>
        </ol>
      </div>
    </section>

    <div class="risk-page__workspace">
      <AppSectionCard
        class="risk-page__results-card"
        title="最高优先风险"
        :desc="documentDisplayTitle"
        icon="shield"
      >
        <template #header>
          <div class="risk-page__heading-meta">
            <span class="risk-page__status" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
            <span class="risk-page__heading-note" aria-live="polite">{{ resultSubline }}</span>
          </div>
        </template>

        <div class="risk-page__summary-rail" aria-label="结果摘要">
          <div
            v-for="item in summaryItems"
            :key="item.label"
            class="risk-page__summary-item"
          >
            <span class="risk-page__summary-label">{{ item.label }}</span>
            <strong class="risk-page__summary-value">{{ item.value }}</strong>
            <span class="risk-page__summary-note">{{ item.note }}</span>
          </div>
        </div>

        <section
          v-if="resultSpotlight && !isProcessing && !resultErrorMsg"
          class="risk-page__spotlight"
          :data-tone="riskTagTypeMap[resultSpotlight.levelKey] || 'muted'"
        >
          <div class="risk-page__spotlight-main">
            <span class="risk-page__eyebrow">当前最需复核</span>
            <div class="risk-page__spotlight-head">
              <h4>{{ resultSpotlight.title }}</h4>
              <div class="risk-page__spotlight-meta">
                <span class="risk-page__status" :data-tone="riskTagTypeMap[resultSpotlight.levelKey] || 'muted'">
                  {{ resultSpotlight.levelText }}
                </span>
                <strong>{{ resultSpotlight.countText }}</strong>
              </div>
            </div>
            <p>{{ resultSpotlight.summary }}</p>
          </div>
          <p class="risk-page__spotlight-evidence">{{ resultSpotlight.evidence }}</p>
        </section>

        <div v-if="resultErrorMsg" class="risk-page__state risk-page__state--error" role="alert">
          <strong>提取失败</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="!activeDocument && !pipelineRun.fileName" class="risk-page__state" role="status" aria-live="polite">
          <strong>还没有文档</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="isProcessing" class="risk-page__state" role="status" aria-live="polite">
          <strong>{{ pipelineRun.fileName || activeDocument?.title || '正在处理文档' }}</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else-if="!groupedRiskResults.length" class="risk-page__state" role="status" aria-live="polite">
          <strong>{{ activeDocument?.title || '当前文档' }}</strong>
          <p>{{ resultSubline }}</p>
        </div>

        <div v-else class="risk-page__result-stack">
          <div class="risk-page__list-header">
            <span class="risk-page__eyebrow">风险序列</span>
            <span class="risk-page__heading-note">{{ resultListCaption }}</span>
          </div>

          <ol class="risk-page__result-list">
            <li
              v-for="(item, index) in groupedRiskResults"
              :key="item.key"
              class="risk-page__result-item"
              :data-tone="riskTagTypeMap[item.dominantLevel] || 'muted'"
            >
              <div class="risk-page__result-index">{{ String(index + 1).padStart(2, '0') }}</div>
              <div class="risk-page__result-body">
                <div class="risk-page__result-head">
                  <div class="risk-page__result-copy">
                    <strong>{{ item.key }}</strong>
                    <p>{{ item.summary }}</p>
                  </div>
                  <div class="risk-page__result-meta">
                    <el-tag :type="getRiskTagType(item.dominantLevel)" size="small">
                      {{ getRiskLevelText(item.dominantLevel) }}
                    </el-tag>
                    <span>{{ item.count }} 条事件</span>
                  </div>
                </div>
                <p class="risk-page__evidence">{{ item.evidence }}</p>
              </div>
            </li>
          </ol>
        </div>
      </AppSectionCard>

      <AppSectionCard
        class="risk-page__dossier-card"
        title="复核留痕"
        desc="链路状态、文档事实与导出准备"
        icon="clipboard"
      >
        <template #header>
          <span class="risk-page__status" :data-tone="exportStatusTone">{{ exportStatusText }}</span>
        </template>

        <div class="risk-page__dossier-grid">
          <div
            v-for="item in reviewChecklist"
            :key="item.label"
            class="risk-page__dossier-item"
          >
            <span class="risk-page__summary-label">{{ item.label }}</span>
            <strong class="risk-page__summary-value">{{ item.value }}</strong>
            <span class="risk-page__summary-note">{{ item.note }}</span>
          </div>
        </div>

        <dl v-if="activeDocument || pipelineRun.fileName" class="risk-page__facts">
          <div
            v-for="fact in documentFacts"
            :key="fact.label"
            class="risk-page__fact"
          >
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>

        <div v-else class="risk-page__side-empty">
          <strong>等待上传</strong>
          <p>上传后在这里查看链路留痕与文档事实。</p>
        </div>

        <div class="risk-page__export-panel">
          <div class="risk-page__export-copy">
            <span class="risk-page__eyebrow">摘要导出</span>
            <strong>{{ canExportResults ? '生成可留痕 Markdown' : '等待链路完成' }}</strong>
            <p>{{ exportHint }}</p>
          </div>

          <el-button plain :disabled="!canExportResults" @click="handleExport">
            <AppIcon name="download" />
            导出结果
          </el-button>
        </div>
      </AppSectionCard>
    </div>
  </div>
</template>

<style scoped>
.risk-page {
  display: grid;
  gap: 20px;
  min-width: 0;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__bench,
.risk-page__bench-copy,
.risk-page__bench-body,
.risk-page__chain-state,
.risk-page__result-stack,
.risk-page__spotlight,
.risk-page__spotlight-main,
.risk-page__dossier-grid,
.risk-page__export-copy,
.risk-page__side-empty,
.risk-page__pipeline-item,
.risk-page__result-body,
.risk-page__result-copy {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.risk-page__bench {
  gap: 18px;
  padding: 26px 28px;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  box-shadow: 0 20px 48px -34px rgba(16, 24, 40, 0.2);
}

.risk-page__bench-header,
.risk-page__chain-meta,
.risk-page__pipeline-top,
.risk-page__list-header,
.risk-page__result-head,
.risk-page__spotlight-head,
.risk-page__spotlight-meta,
.risk-page__export-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-page__bench-header {
  align-items: end;
  flex-wrap: wrap;
}

.risk-page__eyebrow {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.risk-page__bench-copy h2,
.risk-page__spotlight-head h4 {
  margin: 0;
  color: var(--text-primary);
}

.risk-page__bench-copy h2 {
  font-size: clamp(1.55rem, 2.8vw, 2.1rem);
  line-height: 1.1;
}

.risk-page__bench-copy p,
.risk-page__heading-note,
.risk-page__chain-detail,
.risk-page__summary-note,
.risk-page__state p,
.risk-page__result-head p,
.risk-page__evidence,
.risk-page__pipeline-copy p,
.risk-page__side-empty p,
.risk-page__spotlight p,
.risk-page__export-copy p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__bench-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.risk-page__bench-body {
  grid-template-columns: minmax(280px, 0.86fr) minmax(0, 1.14fr);
  gap: 16px;
  align-items: stretch;
}

.risk-page__chain-state {
  align-content: start;
  padding: 20px 22px;
  border: 1px solid rgba(36, 87, 197, 0.14);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(36, 87, 197, 0.06), rgba(36, 87, 197, 0.02)),
    var(--surface-2);
}

.risk-page__chain-title {
  color: var(--text-primary);
  font-size: 1.1rem;
  line-height: 1.35;
}

.risk-page__chain-meta {
  align-items: end;
  flex-wrap: wrap;
}

.risk-page__chain-percent {
  color: var(--text-primary);
  font-family: var(--mono);
  font-size: clamp(1.5rem, 3.4vw, 2rem);
  line-height: 1;
}

.risk-page__chain-detail {
  max-width: 30ch;
}

.risk-page__pipeline-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-page__pipeline-item {
  align-content: start;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 22px;
  background: var(--surface-2);
}

.risk-page__pipeline-item[data-tone='active'] {
  border-color: rgba(36, 87, 197, 0.22);
  background: rgba(36, 87, 197, 0.05);
}

.risk-page__pipeline-item[data-tone='success'] {
  border-color: rgba(33, 129, 92, 0.22);
  background: rgba(33, 129, 92, 0.05);
}

.risk-page__pipeline-item[data-tone='warning'] {
  border-color: rgba(186, 128, 40, 0.24);
  background: rgba(186, 128, 40, 0.07);
}

.risk-page__pipeline-item[data-tone='danger'] {
  border-color: rgba(196, 73, 61, 0.24);
  background: rgba(196, 73, 61, 0.06);
}

.risk-page__pipeline-icon,
.risk-page__result-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.risk-page__pipeline-icon {
  width: 42px;
  height: 42px;
  border-radius: 15px;
  border: 1px solid rgba(20, 32, 51, 0.08);
  background: rgba(255, 255, 255, 0.78);
  color: var(--text-secondary);
}

.risk-page__pipeline-top {
  align-items: center;
}

.risk-page__pipeline-copy strong,
.risk-page__state strong,
.risk-page__result-head strong,
.risk-page__side-empty strong,
.risk-page__fact dd,
.risk-page__spotlight-meta strong,
.risk-page__export-copy strong {
  color: var(--text-primary);
}

.risk-page__pipeline-progress {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.risk-page__workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.85fr);
  gap: 18px;
  min-width: 0;
}

.risk-page__results-card,
.risk-page__dossier-card {
  min-width: 0;
}

.risk-page__results-card :deep(.el-card__body),
.risk-page__dossier-card :deep(.el-card__body) {
  display: grid;
  gap: 18px;
}

.risk-page__heading-meta {
  display: grid;
  justify-items: end;
  gap: 8px;
  max-width: 34ch;
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

.risk-page__progress {
  position: relative;
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: var(--surface-3);
}

.risk-page__progress > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--brand);
  transition: width 180ms ease;
}

.risk-page__summary-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  padding: 1px;
  border-radius: 20px;
  background: var(--line-soft);
}

.risk-page__summary-item {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 16px 18px;
  background: var(--surface-2);
}

.risk-page__summary-label,
.risk-page__fact dt {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.risk-page__summary-value {
  color: var(--text-primary);
  font-size: 1rem;
}

.risk-page__spotlight {
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 22px;
  background: var(--surface-2);
}

.risk-page__spotlight[data-tone='danger'] {
  border-color: rgba(196, 73, 61, 0.22);
  background: rgba(196, 73, 61, 0.05);
}

.risk-page__spotlight[data-tone='warning'] {
  border-color: rgba(186, 128, 40, 0.22);
  background: rgba(186, 128, 40, 0.06);
}

.risk-page__spotlight[data-tone='success'] {
  border-color: rgba(33, 129, 92, 0.18);
  background: rgba(33, 129, 92, 0.05);
}

.risk-page__spotlight-meta {
  flex-wrap: wrap;
}

.risk-page__spotlight-evidence,
.risk-page__evidence {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-3);
}

.risk-page__state,
.risk-page__side-empty,
.risk-page__dossier-item,
.risk-page__fact,
.risk-page__export-panel {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.risk-page__state,
.risk-page__side-empty {
  align-content: center;
  min-height: 220px;
  padding: 22px 24px;
  border-radius: 20px;
  background: var(--surface-2);
}

.risk-page__state {
  min-height: 260px;
}

.risk-page__state--error {
  color: var(--risk);
  background: rgba(196, 73, 61, 0.06);
}

.risk-page__result-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-page__result-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
}

.risk-page__result-index {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--surface-3);
  color: var(--text-muted);
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.risk-page__result-item[data-tone='danger'] {
  border-color: rgba(196, 73, 61, 0.22);
  background: rgba(196, 73, 61, 0.04);
}

.risk-page__result-item[data-tone='warning'] {
  border-color: rgba(186, 128, 40, 0.22);
  background: rgba(186, 128, 40, 0.05);
}

.risk-page__result-item[data-tone='success'] {
  border-color: rgba(33, 129, 92, 0.18);
  background: rgba(33, 129, 92, 0.04);
}

.risk-page__result-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.risk-page__fact {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.risk-page__fact dd {
  margin: 0;
  line-height: 1.5;
}

.risk-page__dossier-item {
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__export-panel {
  gap: 14px;
  padding: 18px;
  border-radius: 20px;
  background: var(--surface-3);
}

.risk-page__export-panel .el-button {
  justify-self: start;
}

@media (max-width: 1200px) {
  .risk-page__bench-body,
  .risk-page__workspace {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .risk-page__pipeline-list,
  .risk-page__summary-rail,
  .risk-page__facts,
  .risk-page__spotlight {
    grid-template-columns: minmax(0, 1fr);
  }

  .risk-page__heading-meta {
    justify-items: start;
  }

  .risk-page__result-item,
  .risk-page__result-head,
  .risk-page__spotlight-head,
  .risk-page__export-panel {
    grid-template-columns: minmax(0, 1fr);
    flex-direction: column;
  }

  .risk-page__result-index {
    width: 36px;
    height: 36px;
  }

  .risk-page__chain-meta,
  .risk-page__list-header,
  .risk-page__pipeline-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .risk-page__result-meta {
    align-items: flex-start;
  }
}

@media (max-width: 720px) {
  .risk-page__bench,
  .risk-page__state,
  .risk-page__side-empty {
    padding: 20px;
  }

  .risk-page__bench-header,
  .risk-page__bench-actions {
    align-items: flex-start;
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .risk-page__progress > span {
    transition: none;
  }
}
</style>
