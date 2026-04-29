<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { normalizeGatewaySummary } from '../lib/llm-gateway.js';
import OpsCommandDeck from './admin/ops/OpsCommandDeck.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const summary = ref(normalizeGatewaySummary());
const errorMsg = ref('');
const isLoading = ref(false);
const refreshedAt = ref('');

const fetchSummary = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    summary.value = await llmGatewayApi.getSummary();
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载 Gateway 总览失败';
  } finally {
    isLoading.value = false;
  }
};

const gatewayTone = computed(() => {
  const status = String(summary.value.gateway.status || '').toLowerCase();
  if (status === 'healthy') {
    return 'success';
  }
  if (status === 'configured') {
    return 'info';
  }
  return 'warning';
});

const metricCards = computed(() => ([
  {
    key: 'health',
    label: 'Gateway health',
    value: summary.value.gateway.status || 'missing',
    note: `活跃路由 ${summary.value.gateway.active_model_count} / ${summary.value.gateway.total_model_count}`,
  },
  {
    key: 'error-rate',
    label: 'Error rate',
    value: `${summary.value.traffic.error_rate_pct}%`,
    note: `近 24h 失败 ${summary.value.traffic.failed_count} 次`,
  },
  {
    key: 'top-models',
    label: 'Top models',
    value: summary.value.top_models.length,
    note: '按最近请求量排序',
  },
  {
    key: 'recent-errors',
    label: '最近错误',
    value: summary.value.recent_errors.length,
    note: '仅保留需要继续追查的失败样本',
  },
]));

const frameMeta = computed(() => [
  `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  `近 24h 请求：${summary.value.traffic.request_count}`,
]);

const maxTopModelRequests = computed(() => {
  const counts = summary.value.top_models.map((item) => item.request_count);
  return counts.length ? Math.max(...counts) : 1;
});

const formatGatewayStatus = (status) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'healthy') {
    return '健康';
  }
  if (normalized === 'configured') {
    return '已配置';
  }
  if (normalized === 'degraded') {
    return '降级';
  }
  return '未接入';
};

const formatSyncStatus = (status) => {
  return status === 'success' ? '最近同步成功' : '最近同步失败';
};

const formatCapability = (value) => {
  if (value === 'embedding') {
    return '向量';
  }
  if (value === 'rerank') {
    return '重排';
  }
  return '对话';
};

onMounted(fetchSummary);
</script>

<template>
  <OpsSectionFrame
    eyebrow="War room / Gateway overview"
    title="LiteLLM Gateway 总览"
    summary="只保留四类判断信息：Gateway health、error rate、top models、最近错误。先回答“网关现在稳不稳、热点在哪、错在哪”。"
    :meta="frameMeta"
    :tone="gatewayTone === 'warning' ? 'warning' : 'neutral'"
  >
    <template #actions>
      <div class="gateway-page__hero-actions">
        <el-button :loading="isLoading" @click="fetchSummary">刷新总览</el-button>
      </div>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <template #status-band>
      <OpsStatusBand :items="metricCards" />
    </template>

    <OpsCommandDeck>
      <AppSectionCard title="Gateway health" desc="把网关状态和最近一次同步结论放在同一块判断面板里。" admin>
        <div class="health-panel">
          <div class="health-panel__status">
            <span class="status-chip" :class="`status-chip--${gatewayTone}`">
              {{ formatGatewayStatus(summary.gateway.status) }}
            </span>
            <strong>{{ summary.gateway.active_model_count }} 个活跃路由</strong>
            <p>已登记 {{ summary.gateway.total_model_count }} 条 LiteLLM 路由。</p>
          </div>
          <div class="health-panel__sync">
            <span class="section-kicker">Recent sync</span>
            <strong>{{ summary.recent_sync ? formatSyncStatus(summary.recent_sync.status) : '暂无同步记录' }}</strong>
            <p>{{ summary.recent_sync?.message || '等待首次同步或迁移。' }}</p>
            <span class="muted-text">{{ summary.recent_sync?.created_at || '未记录时间' }}</span>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="Top models" desc="按最近请求量排序，直接回答当前最热的 alias 在哪里。" admin>
        <div v-if="summary.top_models.length === 0" class="admin-empty-state">近 24 小时暂无请求</div>
        <div v-else class="rank-list">
          <article v-for="(item, index) in summary.top_models" :key="`${item.alias}-${index}`" class="rank-list__item">
            <div class="rank-list__main">
              <span class="rank-list__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <strong>{{ item.alias }}</strong>
                <p>{{ item.request_count }} 次请求</p>
              </div>
            </div>
            <div class="rank-list__bar">
              <span
                class="rank-list__fill"
                :style="{ width: `${(item.request_count / maxTopModelRequests) * 100}%` }"
              />
            </div>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="Top models" desc="按最近请求量排序，直接回答当前最热的 alias 在哪里。" admin>
        <div v-if="summary.top_models.length === 0" class="admin-empty-state">近 24 小时暂无请求</div>
        <div v-else class="rank-list">
          <article v-for="(item, index) in summary.top_models" :key="`${item.alias}-${index}`" class="rank-list__item">
            <div class="rank-list__main">
              <span class="rank-list__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div>
                <strong>{{ item.alias }}</strong>
                <p>{{ item.request_count }} 次请求</p>
              </div>
            </div>
            <div class="rank-list__bar">
              <span
                class="rank-list__fill"
                :style="{ width: `${(item.request_count / maxTopModelRequests) * 100}%` }"
              />
            </div>
          </article>
        </div>
      </AppSectionCard>
    </OpsCommandDeck>

    <OpsInspectorDrawer title="错误样本" desc="只保留足够支持二次排查的错误样本，不展开整页复杂日志。">
      <template #header>
        <RouterLink to="/admin/llm/observability" class="gateway-page__jump-link">进入日志观测</RouterLink>
      </template>

      <div v-if="summary.recent_errors.length === 0" class="admin-empty-state">当前窗口内暂无错误样本</div>
      <div v-else class="error-list">
        <article v-for="item in summary.recent_errors" :key="`${item.trace_id}-${item.time}`" class="error-list__item">
          <div class="error-list__headline">
            <div>
              <strong>{{ item.alias }}</strong>
              <span class="muted-text">· {{ formatCapability(item.capability) }}</span>
            </div>
            <span class="mono-text">{{ item.time }}</span>
          </div>
          <div class="error-list__facts">
            <span>错误码：{{ item.error_code || 'unknown' }}</span>
            <span>Trace：{{ item.trace_id || '未登记' }}</span>
            <span>Latency：{{ item.latency_ms }} ms</span>
          </div>
          <p class="error-list__message">{{ item.error_message || '未提供错误信息。' }}</p>
        </article>
      </div>
    </OpsInspectorDrawer>
  </OpsSectionFrame>
</template>

<style scoped>
.gateway-page__hero {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(242, 246, 251, 0.92)),
    radial-gradient(circle at top right, rgba(36, 87, 197, 0.08), transparent 38%);
}

.gateway-page__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  color: var(--text-secondary);
}

.gateway-page__hero-actions {
  display: flex;
  gap: 12px;
}

.gateway-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.gateway-metric-card,
.health-panel__status,
.health-panel__sync,
.rank-list__item,
.error-list__item {
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-1);
}

.gateway-metric-card {
  padding: 18px;
}

.gateway-metric-card__label,
.section-kicker {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.gateway-metric-card__value {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  color: var(--text-primary);
}

.gateway-metric-card__note {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.gateway-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 20px;
}

.health-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 14px;
}

.health-panel__status,
.health-panel__sync {
  padding: 20px;
}

.health-panel__status strong,
.health-panel__sync strong {
  display: block;
  margin-top: 10px;
  color: var(--text-primary);
  font-size: 20px;
}

.health-panel__status p,
.health-panel__sync p {
  margin: 10px 0 0;
  color: var(--text-secondary);
}

.rank-list,
.error-list {
  display: grid;
  gap: 12px;
}

.rank-list__item {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
}

.rank-list__main {
  display: flex;
  align-items: center;
  gap: 14px;
}

.rank-list__main strong {
  color: var(--text-primary);
}

.rank-list__main p {
  margin: 4px 0 0;
  color: var(--text-secondary);
}

.rank-list__index {
  width: 36px;
  color: var(--text-muted);
  font-family: var(--mono);
}

.rank-list__bar {
  height: 10px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.rank-list__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.28), rgba(36, 87, 197, 0.82));
}

.error-list__item {
  padding: 16px 18px;
}

.error-list__headline,
.error-list__facts {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.error-list__facts {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.error-list__message {
  margin: 10px 0 0;
  color: var(--text-primary);
}

.gateway-page__jump-link {
  color: var(--brand);
  text-decoration: none;
  font-weight: 600;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
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

@media (max-width: 1120px) {
  .gateway-metric-strip,
  .gateway-dashboard-grid,
  .health-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .gateway-metric-strip,
  .gateway-dashboard-grid,
  .health-panel {
    grid-template-columns: 1fr;
  }
}
</style>
