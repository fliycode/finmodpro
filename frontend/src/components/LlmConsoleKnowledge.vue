<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmConsoleApi } from '../api/llm-console.js';
import {
  buildKnowledgePipeline,
  formatConsoleTimestamp,
  normalizeKnowledgeSummary,
} from '../lib/llm-console.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const payload = ref(normalizeKnowledgeSummary());
const errorMsg = ref('');
const isLoading = ref(false);
const refreshedAt = ref('');

const fetchKnowledge = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    payload.value = await llmConsoleApi.getKnowledge();
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载知识库接入摘要失败';
  } finally {
    isLoading.value = false;
  }
};

const parserRows = computed(() => Object.entries(payload.value.parser_capabilities || {}).map(([key, capability]) => ({
  key,
  label: key.toUpperCase(),
  parser: capability.parser || '未配置',
  fallback: capability.fallback ? '支持' : '不支持',
  status: capability.status || '',
  detail: capability.detail || '当前未返回额外说明。',
})));

const summaryMetrics = computed(() => ([
  {
    key: 'documents',
    label: '文档总量',
    value: payload.value.ingestion_summary.total_documents,
  },
  {
    key: 'queued',
    label: '排队中',
    value: payload.value.ingestion_summary.queued,
  },
  {
    key: 'running',
    label: '处理中',
    value: payload.value.ingestion_summary.running,
  },
  {
    key: 'failed',
    label: '失败',
    value: payload.value.ingestion_summary.failed,
  },
]));

const pipelineSteps = computed(() => buildKnowledgePipeline(payload.value.pipeline_steps));

onMounted(fetchKnowledge);
</script>

<template>
  <div class="page-stack admin-llm-page">
    <section class="page-hero admin-llm-page__hero">
      <div>
        <div class="page-hero__eyebrow">LLM 中台 / 知识库接入</div>
        <h1 class="page-hero__title">知识库解析与入库链路</h1>
        <p class="page-hero__subtitle">
          重点回答“当前文档解析链路是否真实可用”，把 Unstructured、fallback 语义和近期入库结果放到同一张治理页面里。
        </p>
        <div class="admin-llm-page__meta">
          <span>最近刷新：{{ refreshedAt || '尚未刷新' }}</span>
          <span>失败任务：{{ payload.recent_failures.length }}</span>
        </div>
      </div>

      <div class="admin-llm-page__actions">
        <el-button @click="fetchKnowledge" :loading="isLoading">刷新知识链路</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="llm-console-metrics">
      <article v-for="metric in summaryMetrics" :key="metric.key" class="llm-console-metric">
        <span class="llm-console-metric__label">{{ metric.label }}</span>
        <strong class="llm-console-metric__value">{{ metric.value }}</strong>
      </article>
    </section>

    <AppSectionCard title="解析能力状态" desc="明确每种文档当前走哪条解析链路，以及失败后是否有 fallback。" admin>
      <div class="parser-grid">
        <article v-for="row in parserRows" :key="row.key" class="parser-card">
          <div class="parser-card__head">
            <strong>{{ row.label }}</strong>
            <span class="parser-card__tag">{{ row.fallback }}</span>
          </div>
          <p class="parser-card__detail">解析器：{{ row.parser }}</p>
          <p class="parser-card__detail">状态：{{ row.status || '按默认配置运行' }}</p>
          <p class="parser-card__detail">{{ row.detail }}</p>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="入库链路阶段" desc="把解析 -> 切块 -> 向量化 -> 索引 的真实步骤明确展示出来。" admin>
      <div class="pipeline-grid">
        <article v-for="step in pipelineSteps" :key="step.index" class="pipeline-step">
          <span class="pipeline-step__index">{{ step.index }}</span>
          <strong>{{ step.label }}</strong>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="最近失败任务" desc="优先定位 PDF / DOCX 解析失败以及当前卡住的阶段。" admin>
      <div v-if="payload.recent_failures.length === 0" class="admin-empty-state">暂无失败任务</div>
      <div v-else class="failure-list">
        <article v-for="item in payload.recent_failures" :key="`${item.document_id}-${item.updated_at}`" class="failure-item">
          <div class="failure-item__head">
            <strong>{{ item.document_title }}</strong>
            <span>{{ formatConsoleTimestamp(item.updated_at) }}</span>
          </div>
          <p class="failure-item__meta">文档类型：{{ item.document_type || '未标记' }} · 步骤：{{ item.current_step || '未提供' }}</p>
          <p class="failure-item__message">{{ item.message || '失败详情未提供。' }}</p>
        </article>
      </div>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.admin-llm-page__hero {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(238, 242, 246, 0.9));
}

.admin-llm-page__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  color: var(--text-secondary);
}

.admin-llm-page__actions {
  display: flex;
  gap: 12px;
}

.llm-console-metrics,
.parser-grid,
.pipeline-grid {
  display: grid;
  gap: 16px;
}

.llm-console-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.parser-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.pipeline-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.llm-console-metric,
.parser-card,
.pipeline-step,
.failure-item {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-1);
}

.llm-console-metric__label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.llm-console-metric__value {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.parser-card__head,
.failure-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.parser-card__tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}

.parser-card__detail,
.failure-item__meta,
.failure-item__message {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.pipeline-step {
  display: grid;
  gap: 10px;
}

.pipeline-step__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}

.failure-list {
  display: grid;
  gap: 12px;
}

@media (max-width: 1024px) {
  .llm-console-metrics,
  .parser-grid,
  .pipeline-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .admin-llm-page__actions,
  .llm-console-metrics,
  .parser-grid,
  .pipeline-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .parser-card__head,
  .failure-item__head {
    flex-direction: column;
  }
}
</style>
