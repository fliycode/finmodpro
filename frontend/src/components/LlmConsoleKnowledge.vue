<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmConsoleApi } from '../api/llm-console.js';
import {
  buildKnowledgePipeline,
  formatConsoleTimestamp,
  normalizeKnowledgeSummary,
} from '../lib/llm-console.js';
import OpsCommandDeck from './admin/ops/OpsCommandDeck.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
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

const statusItems = computed(() => ([
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
const frameMeta = computed(() => [
  `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  `失败任务：${payload.value.recent_failures.length}`,
]);

onMounted(fetchKnowledge);
</script>

<template>
  <OpsSectionFrame
    eyebrow="War room / Knowledge ingestion"
    title="知识链路治理"
    summary="不再把知识链路做成多块装饰面板，而是只保留三类判断：解析能力、入库阶段、最近失败任务。"
    :meta="frameMeta"
  >
    <template #actions>
      <el-button :loading="isLoading" @click="fetchKnowledge">刷新知识链路</el-button>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <template #status-band>
      <OpsStatusBand :items="statusItems" />
    </template>

    <OpsCommandDeck>
      <AppSectionCard title="解析能力状态" desc="每种文档只回答当前走哪条解析链路、是否有 fallback、是否有额外说明。" admin>
        <div v-if="parserRows.length === 0" class="admin-empty-state">当前没有可用解析能力信息</div>
        <div v-else class="parser-list">
          <article v-for="row in parserRows" :key="row.key" class="parser-item">
            <div class="parser-item__head">
              <strong>{{ row.label }}</strong>
              <span class="parser-item__tag">{{ row.fallback }}</span>
            </div>
            <p>解析器：{{ row.parser }}</p>
            <p>状态：{{ row.status || '按默认配置运行' }}</p>
            <p>{{ row.detail }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="入库链路阶段" desc="只保留实际工作流顺序，让解析、切块、向量化和索引一眼可读。" admin>
        <div v-if="pipelineSteps.length === 0" class="admin-empty-state">当前没有返回链路阶段</div>
        <div v-else class="pipeline-list">
          <article v-for="step in pipelineSteps" :key="step.index" class="pipeline-item">
            <span class="pipeline-item__index">{{ step.index }}</span>
            <strong>{{ step.label }}</strong>
          </article>
        </div>
      </AppSectionCard>
    </OpsCommandDeck>

    <OpsInspectorDrawer title="最近失败任务" desc="直接暴露失败文档、失败步骤和最后更新时间，方便回到解析或管线页继续排查。">
      <div v-if="payload.recent_failures.length === 0" class="admin-empty-state">暂无失败任务</div>
      <div v-else class="failure-list">
        <article v-for="item in payload.recent_failures" :key="`${item.document_id}-${item.updated_at}`" class="failure-item">
          <div class="failure-item__head">
            <strong>{{ item.document_title }}</strong>
            <span>{{ formatConsoleTimestamp(item.updated_at) }}</span>
          </div>
          <p>文档类型：{{ item.document_type || '未标记' }}</p>
          <p>步骤：{{ item.current_step || '未提供' }}</p>
          <p>{{ item.message || '失败详情未提供。' }}</p>
        </article>
      </div>
    </OpsInspectorDrawer>
  </OpsSectionFrame>
</template>

<style scoped>
.parser-list,
.pipeline-list,
.failure-list {
  display: grid;
  gap: 12px;
}

.parser-item,
.pipeline-item,
.failure-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.parser-item,
.pipeline-item,
.failure-item {
  padding: 16px 0 0;
  border-top: 1px solid var(--line-soft);
}

.parser-item:first-child,
.pipeline-item:first-child,
.failure-item:first-child {
  padding-top: 0;
  border-top: 0;
}

.parser-item__head,
.failure-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.parser-item__tag {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(141, 208, 208, 0.12);
  color: #8dd0d0;
  font-size: 12px;
  font-weight: 600;
}

.parser-item p,
.failure-item p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.pipeline-item__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
  font-weight: 700;
}

@media (max-width: 1024px) {
  .parser-item__head,
  .failure-item__head {
    flex-direction: column;
  }
}
</style>
