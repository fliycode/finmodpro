<script setup>
import KnowledgeBaseChunksPanel from './KnowledgeBaseChunksPanel.vue';

defineProps({
  document: {
    type: Object,
    default: null,
  },
  primaryAction: {
    type: Object,
    default: null,
  },
  activeTab: {
    type: String,
    default: 'processing',
  },
  taskHintText: {
    type: String,
    default: '',
  },
  isSubmittingTask: {
    type: Boolean,
    default: false,
  },
  versions: {
    type: Array,
    default: () => [],
  },
  isLoadingVersions: {
    type: Boolean,
    default: false,
  },
  isUploadingVersion: {
    type: Boolean,
    default: false,
  },
  chunks: {
    type: Array,
    default: () => [],
  },
  expandedChunkIds: {
    type: Array,
    default: () => [],
  },
  isLoadingChunks: {
    type: Boolean,
    default: false,
  },
  emptyState: {
    type: Object,
    default: () => ({ title: '', detail: '' }),
  },
});

defineEmits([
  'ingest',
  'upload-version',
  'preview',
  'open-original',
  'change-tab',
  'toggle-chunk',
]);

const tabs = [
  { id: 'processing', label: '处理详情' },
  { id: 'versions', label: '版本记录' },
  { id: 'chunks', label: 'Chunks' },
  { id: 'errors', label: '错误日志' },
];
</script>

<template>
  <div class="kb-detail ui-card">
    <template v-if="document">
      <div class="kb-detail__header">
        <div>
          <p class="eyebrow">文档详情</p>
          <h3>{{ document.title }}</h3>
          <p class="kb-detail__summary">{{ document.processResult }}</p>
        </div>
        <div class="kb-detail__header-actions">
          <button
            v-if="document"
            class="kb-secondary-btn"
            :disabled="isUploadingVersion"
            @click="$emit('upload-version')"
          >
            {{ isUploadingVersion ? '上传中...' : '上传新版本' }}
          </button>
          <button
            v-if="primaryAction"
            :class="primaryAction.emphasis === 'primary' ? 'kb-primary-btn' : 'kb-secondary-btn'"
            :disabled="isSubmittingTask"
            @click="$emit('ingest')"
          >
            {{ isSubmittingTask ? '提交中...' : primaryAction.label }}
          </button>
          <span :class="['status-chip', `tone-${document.statusTone || 'neutral'}`]">
            {{ document.processStep.label }}
          </span>
        </div>
      </div>

      <div class="kb-detail__quick-actions">
        <button class="kb-secondary-btn" @click="$emit('preview')">查看预览</button>
        <button class="kb-secondary-btn" @click="$emit('open-original')">查看原文</button>
      </div>

      <div class="kb-meta-grid">
        <div class="meta-item">
          <span>上传者</span>
          <strong>{{ document.uploaderName }}</strong>
        </div>
        <div class="meta-item">
          <span>归属人</span>
          <strong>{{ document.ownerName }}</strong>
        </div>
        <div class="meta-item">
          <span>上传时间</span>
          <strong>{{ document.uploadTime }}</strong>
        </div>
        <div class="meta-item">
          <span>更新时间</span>
          <strong>{{ document.updateTime }}</strong>
        </div>
        <div class="meta-item">
          <span>数据集</span>
          <strong>{{ document.datasetName }}</strong>
        </div>
        <div class="meta-item">
          <span>当前版本</span>
          <strong>v{{ document.currentVersion }}</strong>
        </div>
        <div class="meta-item">
          <span>来源类型</span>
          <strong>{{ document.sourceType || '未标记' }}</strong>
        </div>
        <div class="meta-item">
          <span>来源标签</span>
          <strong>{{ document.sourceLabel || '未标记' }}</strong>
        </div>
        <div class="meta-item">
          <span>切块数量</span>
          <strong>{{ document.chunkCount }}</strong>
        </div>
        <div class="meta-item">
          <span>向量数量</span>
          <strong>{{ document.vectorCount }}</strong>
        </div>
      </div>

      <div class="kb-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          :class="['kb-tab', { active: activeTab === tab.id }]"
          @click="$emit('change-tab', tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="activeTab === 'processing'" class="kb-detail__section">
        <div class="kb-progress">
          <div class="kb-progress__meta">
            <span>处理进度</span>
            <span>{{ document.processStep.progress }}%</span>
          </div>
          <div class="kb-progress__track">
            <div class="kb-progress__value" :style="{ width: `${document.processStep.progress}%` }" />
          </div>
        </div>

        <div class="kb-task-card">
          <p class="kb-task-card__hint">{{ taskHintText }}</p>
          <div class="task-grid">
            <div>
              <span class="meta-label">任务状态</span>
              <strong>{{ document.latestTask?.status || '未创建' }}</strong>
            </div>
            <div>
              <span class="meta-label">当前步骤</span>
              <strong>{{ document.latestTask?.current_step || '未开始' }}</strong>
            </div>
            <div>
              <span class="meta-label">开始时间</span>
              <strong>{{ document.latestTask?.startedAtText || 'N/A' }}</strong>
            </div>
            <div>
              <span class="meta-label">完成时间</span>
              <strong>{{ document.latestTask?.finishedAtText || 'N/A' }}</strong>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'versions'" class="kb-detail__section">
        <div class="kb-version-summary">
          <div>
            <span class="meta-label">根文档 ID</span>
            <strong>{{ document.rootDocumentId }}</strong>
          </div>
          <div>
            <span class="meta-label">版本总数</span>
            <strong>{{ document.versionCount }}</strong>
          </div>
        </div>

        <div v-if="document.processingNotes" class="kb-provenance-card">
          <span class="meta-label">处理备注</span>
          <p>{{ document.processingNotes }}</p>
        </div>

        <div v-if="document.sourceMetadata && Object.keys(document.sourceMetadata).length" class="kb-provenance-card">
          <span class="meta-label">来源元数据</span>
          <pre>{{ JSON.stringify(document.sourceMetadata, null, 2) }}</pre>
        </div>

        <div v-if="isLoadingVersions" class="kb-empty-state">
          正在加载版本记录...
        </div>
        <div v-else-if="versions.length === 0" class="kb-empty-state">
          当前文档还没有版本记录。
        </div>
        <div v-else class="kb-version-list">
          <article
            v-for="version in versions"
            :key="`${version.documentId}-${version.versionNumber}`"
            class="kb-version-card"
          >
            <div class="kb-version-card__header">
              <strong>v{{ version.versionNumber }}</strong>
              <span
                v-if="version.isCurrent"
                class="status-chip tone-success"
              >
                当前版本
              </span>
            </div>
            <p>{{ version.sourceLabel || '未标记来源' }}</p>
            <div class="task-grid">
              <div>
                <span class="meta-label">来源类型</span>
                <strong>{{ version.sourceType || '未标记' }}</strong>
              </div>
              <div>
                <span class="meta-label">上传时间</span>
                <strong>{{ version.createdAtText }}</strong>
              </div>
            </div>
            <div v-if="Object.keys(version.sourceMetadata || {}).length" class="kb-version-card__metadata">
              <span class="meta-label">来源元数据</span>
              <pre>{{ JSON.stringify(version.sourceMetadata, null, 2) }}</pre>
            </div>
            <div v-if="version.processingNotes" class="kb-version-card__metadata">
              <span class="meta-label">处理备注</span>
              <p>{{ version.processingNotes }}</p>
            </div>
          </article>
        </div>
      </div>

      <div v-else-if="activeTab === 'chunks'" class="kb-detail__section">
        <KnowledgeBaseChunksPanel
          :chunks="chunks"
          :expanded-chunk-ids="expandedChunkIds"
          :is-loading="isLoadingChunks"
          @toggle-chunk="$emit('toggle-chunk', $event)"
        />
      </div>

      <div v-else class="kb-detail__section">
        <div v-if="document.processError" class="kb-error-log">
          {{ document.processError }}
        </div>
        <div v-else class="kb-empty-state">
          当前没有错误日志。
        </div>
      </div>
    </template>

    <div v-else class="kb-empty-state">
      <h4>{{ emptyState.title }}</h4>
      <p>{{ emptyState.detail }}</p>
    </div>
  </div>
</template>

<style scoped>
.kb-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #fff;
  padding: 22px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b7b93;
}

.kb-detail h3 {
  margin: 0;
  color: #142033;
}

.kb-detail__summary {
  margin: 8px 0 0;
  color: #5a677d;
  line-height: 1.6;
}

.kb-detail__header,
.kb-detail__header-actions,
.kb-detail__quick-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.kb-detail__header-actions,
.kb-detail__quick-actions {
  justify-content: flex-end;
}

.kb-primary-btn,
.kb-secondary-btn {
  height: 40px;
  border-radius: 12px;
  padding: 0 16px;
  font-weight: 700;
  cursor: pointer;
}

.kb-primary-btn {
  border: none;
  background: #2457c5;
  color: #fff;
}

.kb-secondary-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  color: #142033;
}

.kb-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.meta-item {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 16px;
  padding: 14px;
  background: #f7f9fc;
}

.kb-version-summary,
.kb-version-list {
  display: grid;
  gap: 12px;
}

.kb-version-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.kb-provenance-card,
.kb-version-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 16px;
  padding: 16px;
  background: #f7f9fc;
}

.kb-version-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.kb-version-card__metadata pre,
.kb-provenance-card pre {
  overflow-x: auto;
  white-space: pre-wrap;
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
}

.meta-item span,
.meta-label {
  display: block;
  margin-bottom: 6px;
  color: #6b7b93;
  font-size: 12px;
}

.meta-item strong,
.task-grid strong {
  color: #142033;
}

.kb-tabs {
  display: flex;
  gap: 10px;
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  padding-bottom: 12px;
}

.kb-tab {
  border: 1px solid rgba(20, 32, 51, 0.1);
  border-radius: 999px;
  padding: 8px 14px;
  background: #fff;
  color: #5a677d;
  cursor: pointer;
}

.kb-tab.active {
  border-color: rgba(36, 87, 197, 0.15);
  background: rgba(36, 87, 197, 0.08);
  color: #2457c5;
}

.kb-detail__section {
  min-height: 220px;
}

.kb-progress__meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #6b7b93;
  font-size: 13px;
}

.kb-progress__track {
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: #eef2f7;
}

.kb-progress__value {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2457c5, #4c7de0);
}

.kb-task-card {
  margin-top: 16px;
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 16px;
  padding: 16px;
  background: #f9fbfd;
}

.kb-task-card__hint,
.kb-empty-state,
.kb-error-log {
  color: #5a677d;
  line-height: 1.7;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.kb-empty-state h4 {
  margin: 0 0 8px;
  color: #142033;
}

.kb-empty-state p {
  margin: 0;
}

.kb-error-log {
  border: 1px solid rgba(181, 58, 58, 0.15);
  border-radius: 16px;
  padding: 16px;
  background: rgba(181, 58, 58, 0.06);
  color: #8d3030;
  white-space: pre-wrap;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.tone-neutral {
  background: #eef2f7;
  color: #516176;
}

.tone-accent {
  background: rgba(36, 87, 197, 0.12);
  color: #2457c5;
}

.tone-success {
  background: rgba(35, 138, 86, 0.12);
  color: #238a56;
}

.tone-danger {
  background: rgba(204, 61, 61, 0.12);
  color: #b53a3a;
}
</style>
