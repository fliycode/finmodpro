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
  <div :class="['kb-detail', 'ui-card', `kb-detail--${document?.statusTone || 'neutral'}`]">
    <template v-if="document">
      <div class="kb-detail__header">
        <div class="kb-detail__title-area">
          <h3>{{ document.title }}</h3>
          <span :class="['status-chip', `tone-${document.statusTone || 'neutral'}`]">
            {{ document.processStep.label }}
          </span>
        </div>
        <div class="kb-detail__header-actions">
          <button class="kb-ghost-btn" @click="$emit('preview')">预览</button>
          <button class="kb-ghost-btn" @click="$emit('open-original')">原文</button>
          <button
            class="kb-secondary-btn"
            :disabled="isUploadingVersion"
            @click="$emit('upload-version')"
          >
            {{ isUploadingVersion ? '上传中...' : '新版本' }}
          </button>
          <button
            v-if="primaryAction"
            :class="primaryAction.emphasis === 'primary' ? 'kb-primary-btn' : 'kb-secondary-btn'"
            :disabled="isSubmittingTask"
            @click="$emit('ingest')"
          >
            {{ isSubmittingTask ? '提交中...' : primaryAction.label }}
          </button>
        </div>
      </div>

      <p v-if="document.processResult" class="kb-detail__summary">{{ document.processResult }}</p>

      <div class="kb-meta-row">
        <span class="kb-meta-chip">{{ document.datasetName || '未分组' }}</span>
        <span class="kb-meta-chip">v{{ document.currentVersion }}</span>
        <span class="kb-meta-chip">{{ document.uploaderName }}</span>
        <span class="kb-meta-chip">{{ document.uploadTime }}</span>
        <span class="kb-meta-chip">{{ document.chunkCount }} 块 / {{ document.vectorCount }} 向量</span>
        <span class="kb-meta-chip">{{ document.size }}</span>
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
          <div class="kb-summary-card">
            <span class="meta-label">根文档 ID</span>
            <strong>{{ document.rootDocumentId }}</strong>
          </div>
          <div class="kb-summary-card">
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
            :class="['kb-version-card', { 'is-current': version.isCurrent }]"
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
  --kb-accent: var(--brand);
  --kb-accent-soft: color-mix(in oklab, var(--kb-accent) 12%, var(--surface-2));
  --kb-accent-wash: color-mix(in oklab, var(--kb-accent) 8%, var(--surface-3));
  --kb-accent-border: color-mix(in oklab, var(--kb-accent) 18%, var(--line-soft));
  --kb-accent-ink: color-mix(in oklab, var(--kb-accent) 48%, var(--text-primary));
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 20px;
  border: 1px solid var(--kb-accent-border);
  background:
    radial-gradient(circle at top right, color-mix(in oklab, var(--kb-accent) 14%, transparent) 0, transparent 42%),
    linear-gradient(180deg, color-mix(in oklab, var(--kb-accent) 8%, var(--surface-2)) 0%, var(--surface-2) 140px);
  padding: 24px;
}

.kb-detail--neutral {
  --kb-accent: color-mix(in oklab, var(--brand) 55%, var(--text-secondary));
}

.kb-detail--accent {
  --kb-accent: var(--brand);
}

.kb-detail--success {
  --kb-accent: var(--success);
}

.kb-detail--danger {
  --kb-accent: var(--risk);
}

.kb-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--kb-accent-border);
}

.kb-detail__title-area {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.kb-detail__title-area h3 {
  margin: 0;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-detail__header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.kb-detail__summary {
  margin: 0;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--kb-accent-ink);
  line-height: 1.6;
  font-size: 14px;
  max-width: 72ch;
}

.kb-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.kb-meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--kb-accent-border);
  background: var(--kb-accent-soft);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: var(--kb-accent-ink);
}

.kb-primary-btn,
.kb-secondary-btn,
.kb-ghost-btn {
  height: 36px;
  border-radius: 10px;
  padding: 0 14px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.kb-primary-btn {
  border: none;
  background: var(--brand);
  color: var(--text-inverse);
}

.kb-primary-btn:hover {
  background: var(--brand-hover);
}

.kb-secondary-btn {
  border: 1px solid var(--kb-accent-border);
  background: color-mix(in oklab, var(--kb-accent) 6%, var(--surface-2));
  color: var(--text-primary);
}

.kb-secondary-btn:hover {
  background: color-mix(in oklab, var(--kb-accent) 12%, var(--surface-2));
}

.kb-ghost-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  padding: 0 10px;
}

.kb-ghost-btn:hover {
  color: var(--kb-accent-ink);
  background: var(--kb-accent-soft);
}

.kb-primary-btn:focus-visible,
.kb-secondary-btn:focus-visible,
.kb-ghost-btn:focus-visible,
.kb-tab:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--kb-accent) 55%, transparent);
  outline-offset: 2px;
}

.kb-version-summary,
.kb-version-list {
  display: grid;
  gap: 12px;
}

.kb-version-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.kb-summary-card,
.kb-provenance-card,
.kb-version-card {
  border: 1px solid var(--kb-accent-border);
  border-radius: 12px;
  padding: 14px;
  background: var(--kb-accent-wash);
}

.kb-summary-card strong {
  color: var(--kb-accent-ink);
}

.kb-version-card.is-current {
  background: color-mix(in oklab, var(--success) 10%, var(--surface-2));
  border-color: color-mix(in oklab, var(--success) 24%, var(--line-soft));
}

.kb-version-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.kb-version-card__header strong {
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
}

.kb-version-card__metadata pre,
.kb-provenance-card pre {
  overflow-x: auto;
  white-space: pre-wrap;
  margin: 8px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: color-mix(in oklab, var(--kb-accent) 5%, var(--surface-2));
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.meta-label {
  display: block;
  margin-bottom: 6px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.task-grid strong {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-primary);
}

.task-grid > div,
.kb-summary-card {
  padding: 12px;
  border-radius: 14px;
}

.task-grid > div {
  border: 1px solid color-mix(in oklab, var(--kb-accent) 16%, var(--line-soft));
  background: color-mix(in oklab, var(--kb-accent) 5%, var(--surface-2));
}

.kb-tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--kb-accent-border);
  padding-bottom: 12px;
}

.kb-tab {
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 6px 12px;
  background: transparent;
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.kb-tab:hover {
  background: var(--kb-accent-soft);
}

.kb-tab.active {
  border-color: var(--kb-accent-border);
  background: var(--kb-accent-soft);
  color: var(--kb-accent-ink);
}

.kb-detail__section {
  min-height: 180px;
}

.kb-progress__meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-muted);
  font-size: 13px;
}

.kb-progress__track {
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--kb-accent) 8%, var(--surface-3));
}

.kb-progress__value {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    color-mix(in oklab, var(--kb-accent) 64%, var(--surface-2)),
    var(--kb-accent)
  );
}

.kb-task-card {
  margin-top: 14px;
  border: 1px solid var(--kb-accent-border);
  border-radius: 12px;
  padding: 14px;
  background: var(--kb-accent-wash);
}

.kb-task-card__hint,
.kb-empty-state {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: 14px;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.kb-empty-state h4 {
  margin: 0 0 8px;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-empty-state p {
  margin: 0;
}

.kb-error-log {
  border: 1px solid color-mix(in oklab, var(--risk) 24%, var(--line-soft));
  border-radius: 12px;
  padding: 14px;
  background: color-mix(in oklab, var(--risk) 8%, var(--surface-2));
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: color-mix(in oklab, var(--risk) 74%, var(--text-primary));
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 14px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.tone-neutral {
  border: 1px solid var(--kb-accent-border);
  background: var(--kb-accent-soft);
  color: var(--kb-accent-ink);
}

.tone-accent {
  border: 1px solid color-mix(in oklab, var(--brand) 22%, var(--line-soft));
  background: color-mix(in oklab, var(--brand) 12%, var(--surface-2));
  color: color-mix(in oklab, var(--brand) 72%, var(--text-primary));
}

.tone-success {
  border: 1px solid color-mix(in oklab, var(--success) 22%, var(--line-soft));
  background: color-mix(in oklab, var(--success) 12%, var(--surface-2));
  color: color-mix(in oklab, var(--success) 72%, var(--text-primary));
}

.tone-danger {
  border: 1px solid color-mix(in oklab, var(--risk) 22%, var(--line-soft));
  background: color-mix(in oklab, var(--risk) 12%, var(--surface-2));
  color: color-mix(in oklab, var(--risk) 72%, var(--text-primary));
}

@media (max-width: 900px) {
  .kb-detail__header {
    flex-direction: column;
  }

  .kb-detail__header-actions {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .kb-version-summary,
  .task-grid {
    grid-template-columns: 1fr;
  }

  .kb-tabs {
    flex-wrap: wrap;
  }
}
</style>
