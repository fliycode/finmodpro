<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmConsoleApi } from '../api/llm-console.js';
import {
  formatConsoleTimestamp,
  normalizeObservabilitySummary,
} from '../lib/llm-console.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const payload = ref(normalizeObservabilitySummary());
const errorMsg = ref('');
const isLoading = ref(false);
const refreshedAt = ref('');

const fetchObservability = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    payload.value = await llmConsoleApi.getObservability();
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载观测摘要失败';
  } finally {
    isLoading.value = false;
  }
};

const metrics = computed(() => ([
  {
    key: 'chat',
    label: '近 24h 请求',
    value: payload.value.overview.chat_request_count_24h,
    note: '判断当前管理链路是否持续发生调用。',
  },
  {
    key: 'retrieval',
    label: '近 24h 命中',
    value: payload.value.overview.retrieval_hit_count_24h,
    note: '用于快速判断检索链路是否真正返回内容。',
  },
  {
    key: 'latency',
    label: '平均延迟 (ms)',
    value: payload.value.overview.avg_duration_ms_24h,
    note: '延迟升高时优先查看外部 trace 与最近失败事件。',
  },
  {
    key: 'ingestion',
    label: '失败入库',
    value: payload.value.overview.failed_ingestion_count,
    note: '把知识链路失败与调用观测放在同一处查看。',
  },
]));

const langfuseFacts = computed(() => ([
  {
    label: '接入状态',
    value: payload.value.langfuse.configured ? '已配置' : '未配置',
  },
  {
    label: 'Host',
    value: payload.value.langfuse.host || '未设置',
  },
  {
    label: 'Public Key',
    value: payload.value.langfuse.has_public_key ? '已提供' : '未提供',
  },
  {
    label: 'Secret Key',
    value: payload.value.langfuse.has_secret_key ? '已提供' : '未提供',
  },
]));

onMounted(fetchObservability);
</script>

<template>
  <div class="page-stack admin-llm-page">
    <section class="page-hero admin-llm-page__hero">
      <div>
        <div class="page-hero__eyebrow">LLM 中台 / 观测</div>
        <h1 class="page-hero__title">观测与异常摘要</h1>
        <p class="page-hero__subtitle">
          不在 FinModPro 内重做 Langfuse，而是把调用量、命中情况、失败事件和外部观测入口压缩成一页治理摘要。
        </p>
        <div class="admin-llm-page__meta">
          <span>最近刷新：{{ refreshedAt || '尚未刷新' }}</span>
          <span>失败事件：{{ payload.recent_failures.length }}</span>
        </div>
      </div>

      <div class="admin-llm-page__actions">
        <el-button @click="fetchObservability" :loading="isLoading">刷新观测</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="llm-console-metrics">
      <article v-for="metric in metrics" :key="metric.key" class="llm-console-metric">
        <span class="llm-console-metric__label">{{ metric.label }}</span>
        <strong class="llm-console-metric__value">{{ metric.value }}</strong>
        <p class="llm-console-metric__note">{{ metric.note }}</p>
      </article>
    </section>

    <AppSectionCard title="最近失败事件" desc="只保留需要管理员继续追查的失败语义，不堆砌无意义监控图表。" admin>
      <div v-if="payload.recent_failures.length === 0" class="admin-empty-state">近 24 小时暂无失败事件</div>
      <div v-else class="failure-list">
        <article v-for="item in payload.recent_failures" :key="`${item.document_id}-${item.updated_at}`" class="failure-item">
          <div class="failure-item__head">
            <strong>{{ item.document_title }}</strong>
            <span>{{ formatConsoleTimestamp(item.updated_at) }}</span>
          </div>
          <p class="failure-item__meta">文档类型：{{ item.document_type || '未标记' }} · 当前步骤：{{ item.current_step || '未提供' }}</p>
          <p class="failure-item__message">{{ item.message || '失败详情未提供。' }}</p>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="Langfuse 外部观测" desc="保留配置状态与外链入口，复杂 trace 细节继续在外部系统查看。" admin>
      <div class="langfuse-grid">
        <article v-for="fact in langfuseFacts" :key="fact.label" class="langfuse-card">
          <span class="langfuse-card__label">{{ fact.label }}</span>
          <strong class="langfuse-card__value">{{ fact.value }}</strong>
        </article>
      </div>
      <div class="inline-actions langfuse-actions">
        <a
          v-if="payload.langfuse.host"
          :href="payload.langfuse.host"
          target="_blank"
          rel="noreferrer"
          class="admin-llm-page__link"
        >
          打开 Langfuse
        </a>
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
.langfuse-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.llm-console-metric,
.langfuse-card,
.failure-item {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-1);
}

.llm-console-metric__label,
.langfuse-card__label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.llm-console-metric__value,
.langfuse-card__value {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.llm-console-metric__note {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.failure-list {
  display: grid;
  gap: 12px;
}

.failure-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.failure-item__meta,
.failure-item__message {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.langfuse-actions {
  margin-top: 16px;
}

.admin-llm-page__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  color: var(--text-primary);
  background: var(--surface-1);
  text-decoration: none;
}

.admin-llm-page__link:hover {
  border-color: var(--line-strong);
  background: var(--surface-2);
}

@media (max-width: 1024px) {
  .llm-console-metrics,
  .langfuse-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .admin-llm-page__actions,
  .llm-console-metrics,
  .langfuse-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .failure-item__head {
    flex-direction: column;
  }
}
</style>
