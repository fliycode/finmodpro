<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { llmConsoleApi } from '../api/llm-console.js';
import {
  buildProviderTone,
  normalizeConsoleSummary,
} from '../lib/llm-console.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const summary = ref(normalizeConsoleSummary());
const errorMsg = ref('');
const isLoading = ref(false);
const refreshedAt = ref('');

const fetchSummary = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    summary.value = await llmConsoleApi.getSummary();
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载 LLM 中台总览失败';
  } finally {
    isLoading.value = false;
  }
};

const providerCards = computed(() => summary.value.providers || []);
const quickLinks = computed(() => summary.value.quick_links || []);
const activeModels = computed(() => Object.entries(summary.value.active_models || {}));
const activityMetrics = computed(() => ([
  {
    key: 'chat',
    label: '近 24h 问答',
    value: summary.value.recent_activity.chat_request_count_24h,
    note: '用于判断当前 LLM 调用是否持续发生。',
  },
  {
    key: 'ingestion',
    label: '失败入库',
    value: summary.value.recent_activity.failed_ingestion_count,
    note: '优先判断知识库解析链路是否出现阻塞。',
  },
  {
    key: 'fine-tunes',
    label: '运行中微调',
    value: summary.value.recent_activity.running_fine_tune_count,
    note: '展示当前微调控制面是否存在活跃任务。',
  },
  {
    key: 'latest-fine-tune',
    label: '最近微调状态',
    value: summary.value.recent_activity.latest_fine_tune_status || '暂无',
    note: '保留最近一次微调任务状态，便于继续排查。',
  },
]));

const formatProviderStatus = (status) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'connected') {
    return '已接入';
  }
  if (normalized === 'configured') {
    return '已配置';
  }
  if (normalized === 'idle') {
    return '待启动';
  }
  return '未接入';
};

const formatModelLabel = (key) => (key === 'embedding' ? '向量链路' : '对话链路');

onMounted(fetchSummary);
</script>

<template>
  <div class="page-stack admin-llm-page">
    <div class=”admin-llm-page__toolbar”>
      <div class=”admin-llm-page__meta”>
        <span>最近刷新：{{ refreshedAt || '尚未刷新' }}</span>
        <span>基础设施：{{ providerCards.length }}</span>
      </div>
      <div class=”admin-llm-page__actions”>
        <el-button @click=”fetchSummary” :loading=”isLoading”>刷新总览</el-button>
      </div>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="llm-console-metrics">
      <article v-for="metric in activityMetrics" :key="metric.key" class="llm-console-metric">
        <span class="llm-console-metric__label">{{ metric.label }}</span>
        <strong class="llm-console-metric__value">{{ metric.value }}</strong>
        <p class="llm-console-metric__note">{{ metric.note }}</p>
      </article>
    </section>

    <AppSectionCard title="基础设施状态" desc="直接回答当前项目已经接入了哪些 LLM 基础设施，以及每类能力处于什么阶段。" admin>
      <div class="provider-grid">
        <article v-for="provider in providerCards" :key="provider.key" class="provider-card">
          <div class="provider-card__head">
            <strong>{{ provider.label }}</strong>
            <span class="status-chip" :class="`status-chip--${buildProviderTone(provider)}`">
              {{ formatProviderStatus(provider.status) }}
            </span>
          </div>
          <dl class="provider-card__facts">
            <div>
              <dt>活跃实例</dt>
              <dd>{{ provider.active_count }}</dd>
            </div>
            <div>
              <dt>当前模型</dt>
              <dd>{{ provider.model_name || '按路由或外部控制面决定' }}</dd>
            </div>
            <div>
              <dt>入口</dt>
              <dd class="mono-text">{{ provider.endpoint || '由当前页面汇总，不直接暴露 endpoint' }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="当前模型与链路关系" desc="用当前启用的 chat / embedding 入口解释主链路到底在走什么模型。" admin>
      <div class="model-grid">
        <article v-for="[key, model] in activeModels" :key="key" class="model-card">
          <span class="model-card__eyebrow">{{ formatModelLabel(key) }}</span>
          <strong class="model-card__title">{{ model.model_name || '尚未启用' }}</strong>
          <p class="model-card__meta">Provider：{{ model.provider || '未配置' }}</p>
          <p class="model-card__meta">Alias：{{ model.alias || '未登记' }}</p>
          <p class="model-card__meta mono-text">Endpoint：{{ model.endpoint || '沿用 provider 默认入口' }}</p>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="快捷操作" desc="保持总览页偏判断，不把操作埋在深层表单里。" admin>
      <div class="inline-actions admin-llm-page__links">
        <RouterLink
          v-for="link in quickLinks"
          :key="link.to"
          :to="link.to"
          class="admin-llm-page__link"
        >
          {{ link.label }}
        </RouterLink>
      </div>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.admin-llm-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
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

.llm-console-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.llm-console-metric,
.provider-card,
.model-card {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-1);
}

.llm-console-metric__label,
.model-card__eyebrow {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.llm-console-metric__value,
.model-card__title {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.llm-console-metric__note,
.model-card__meta {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.provider-grid,
.model-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.provider-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.provider-card__facts {
  display: grid;
  gap: 12px;
  margin: 16px 0 0;
}

.provider-card__facts div {
  display: grid;
  gap: 4px;
}

.provider-card__facts dt {
  font-size: 12px;
  color: var(--text-muted);
}

.provider-card__facts dd {
  margin: 0;
  color: var(--text-primary);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.status-chip--success {
  color: #166534;
  background: #dcfce7;
}

.status-chip--info {
  color: #1d4ed8;
  background: #dbeafe;
}

.status-chip--warning {
  color: #b45309;
  background: #fef3c7;
}

.admin-llm-page__links {
  gap: 12px;
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

.mono-text {
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}

@media (max-width: 1024px) {
  .llm-console-metrics,
  .provider-grid,
  .model-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .admin-llm-page__actions,
  .llm-console-metrics,
  .provider-grid,
  .model-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .provider-card__head {
    flex-direction: column;
  }
}
</style>
