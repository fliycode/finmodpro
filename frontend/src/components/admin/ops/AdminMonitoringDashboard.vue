<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import AdminChart from '../AdminChart.vue';
import ServiceStatusCard from './ServiceStatusCard.vue';
import AlertRuleDialog from './AlertRuleDialog.vue';
import { monitoringApi } from '../../../api/monitoring.js';
import {
  normalizeMonitoringPayload,
  normalizeMetricTimeSeries,
  buildServiceStatusCards,
  buildResourceGauges,
  buildCeleryStatus,
  buildMetricTimeSeriesOption,
  normalizeAlertRule,
  normalizeAlertEvent,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  CONDITION_LABELS,
  STATUS_LABELS,
  STATUS_TONES,
  METRIC_OPTIONS,
} from '../../../lib/admin-monitoring.js';

const loading = ref(true);
const status = ref(null);
const rules = ref([]);
const events = ref([]);
const selectedMetric = ref('cpu_percent');
const timeSeries = ref(null);
const dialogVisible = ref(false);
const editingRule = ref(null);
const timeSeriesLoading = ref(false);

const normalizedStatus = computed(() => normalizeMonitoringPayload(status.value));
const serviceCards = computed(() => buildServiceStatusCards(normalizedStatus.value.metrics));
const resourceGauges = computed(() => buildResourceGauges(normalizedStatus.value.metrics));
const celeryInfo = computed(() => buildCeleryStatus(normalizedStatus.value.metrics));
const normalizedRules = computed(() => (Array.isArray(rules.value) ? rules.value.map(normalizeAlertRule) : []));
const normalizedEvents = computed(() => (Array.isArray(events.value) ? events.value.map(normalizeAlertEvent) : []));
const chartOption = computed(() => {
  if (!timeSeries.value || !timeSeries.value.data_points?.length) return null;
  return buildMetricTimeSeriesOption(normalizeMetricTimeSeries(timeSeries.value));
});

async function loadAll() {
  loading.value = true;
  try {
    const [statusData, rulesData, eventsData] = await Promise.all([
      monitoringApi.getStatus(),
      monitoringApi.listAlertRules(),
      monitoringApi.listAlertEvents({ limit: 50 }),
    ]);
    status.value = statusData;
    rules.value = Array.isArray(rulesData) ? rulesData : [];
    events.value = Array.isArray(eventsData) ? eventsData : [];
    await loadTimeSeries();
  } catch (err) {
    ElMessage.error(err.message || '加载监控数据失败');
  } finally {
    loading.value = false;
  }
}

async function loadTimeSeries() {
  timeSeriesLoading.value = true;
  try {
    timeSeries.value = await monitoringApi.getMetricTimeSeries(selectedMetric.value, 24);
  } catch {
    timeSeries.value = null;
  } finally {
    timeSeriesLoading.value = false;
  }
}

function handleMetricChange() {
  loadTimeSeries();
}

function handleCreateRule() {
  editingRule.value = null;
  dialogVisible.value = true;
}

function handleEditRule(rule) {
  editingRule.value = rule;
  dialogVisible.value = true;
}

async function handleRuleSubmit(payload) {
  try {
    if (editingRule.value) {
      await monitoringApi.updateAlertRule(editingRule.value.id, payload);
      ElMessage.success('规则已更新');
    } else {
      await monitoringApi.createAlertRule(payload);
      ElMessage.success('规则已创建');
    }
    const rulesData = await monitoringApi.listAlertRules();
    rules.value = Array.isArray(rulesData) ? rulesData : [];
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
  }
}

async function handleDeleteRule(ruleId) {
  try {
    await monitoringApi.deleteAlertRule(ruleId);
    ElMessage.success('规则已删除');
    rules.value = rules.value.filter((r) => r.id !== ruleId);
  } catch (err) {
    ElMessage.error(err.message || '删除失败');
  }
}

async function handleToggleRule(rule) {
  try {
    await monitoringApi.updateAlertRule(rule.id, { enabled: !rule.enabled });
    rule.enabled = !rule.enabled;
    ElMessage.success(rule.enabled ? '规则已启用' : '规则已禁用');
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
  }
}

async function handleAcknowledgeEvent(eventId) {
  try {
    await monitoringApi.acknowledgeAlertEvent(eventId);
    ElMessage.success('告警已确认');
    const eventsData = await monitoringApi.listAlertEvents({ limit: 50 });
    events.value = Array.isArray(eventsData) ? eventsData : [];
  } catch (err) {
    ElMessage.error(err.message || '确认失败');
  }
}

function formatTime(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

onMounted(loadAll);
</script>

<template>
  <div v-loading="loading" class="monitoring">
    <!-- Service Status -->
    <section class="monitoring__section">
      <h3 class="monitoring__heading">服务状态</h3>
      <div class="monitoring__service-grid">
        <ServiceStatusCard
          v-for="card in serviceCards"
          :key="card.key"
          :label="card.label"
          :status="card.status"
          :detail="card.detail"
          :tone="card.tone"
          :icon="card.icon"
        />
        <div class="service-card" :class="`tone-${celeryInfo.tone}`">
          <div class="service-card__icon"><span class="service-card__dot" /></div>
          <div class="service-card__body">
            <span class="service-card__label">Celery Workers</span>
            <span class="service-card__detail">{{ celeryInfo.count }} 个活跃</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Resource Gauges -->
    <section class="monitoring__section">
      <h3 class="monitoring__heading">系统资源</h3>
      <div class="monitoring__gauge-grid">
        <div v-for="gauge in resourceGauges" :key="gauge.key" class="gauge-card">
          <div class="gauge-card__header">
            <span class="gauge-card__label">{{ gauge.label }}</span>
            <span class="gauge-card__value" :class="`tone-${gauge.tone}`">
              {{ gauge.value.toFixed(1) }}{{ gauge.unit }}
            </span>
          </div>
          <el-progress
            :percentage="Math.min(gauge.value, 100)"
            :stroke-width="8"
            :show-text="false"
            :color="gauge.tone === 'risk' ? 'var(--risk)' : gauge.tone === 'warning' ? 'var(--warning)' : 'var(--success)'"
          />
          <div v-if="gauge.tags?.total_gb" class="gauge-card__meta">
            总量: {{ gauge.tags.total_gb }} GB
          </div>
        </div>
      </div>
    </section>

    <!-- Metric Time Series -->
    <section class="monitoring__section">
      <div class="monitoring__section-header">
        <h3 class="monitoring__heading">指标趋势</h3>
        <el-select
          v-model="selectedMetric"
          size="small"
          style="width: 180px"
          @change="handleMetricChange"
        >
          <el-option
            v-for="opt in METRIC_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
      <div v-if="chartOption" class="monitoring__chart-wrapper">
        <AdminChart :option="chartOption" height="300px" />
      </div>
      <div v-else class="monitoring__empty">暂无数据</div>
    </section>

    <!-- Alert Rules -->
    <section class="monitoring__section">
      <div class="monitoring__section-header">
        <h3 class="monitoring__heading">告警规则</h3>
        <el-button size="small" type="primary" @click="handleCreateRule">新建规则</el-button>
      </div>
      <el-table :data="normalizedRules" size="small" stripe>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="指标" min-width="140">
          <template #default="{ row }">
            {{ METRIC_OPTIONS.find((o) => o.value === row.metricName)?.label || row.metricName }}
          </template>
        </el-table-column>
        <el-table-column label="条件" min-width="140">
          <template #default="{ row }">
            {{ CONDITION_LABELS[row.condition] || row.condition }} {{ row.threshold }}
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="90">
          <template #default="{ row }">
            <el-tag :type="SEVERITY_TONES[row.severity] === 'risk' ? 'danger' : SEVERITY_TONES[row.severity]" size="small">
              {{ SEVERITY_LABELS[row.severity] || row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" size="small" @change="() => handleToggleRule(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="handleEditRule(row)">编辑</el-button>
            <el-popconfirm title="确定删除此规则？" @confirm="handleDeleteRule(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- Alert Events -->
    <section class="monitoring__section">
      <h3 class="monitoring__heading">告警事件</h3>
      <el-table :data="normalizedEvents" size="small" stripe>
        <el-table-column label="规则" min-width="140" prop="ruleName" />
        <el-table-column label="严重程度" width="90">
          <template #default="{ row }">
            <el-tag :type="SEVERITY_TONES[row.severity] === 'risk' ? 'danger' : SEVERITY_TONES[row.severity]" size="small">
              {{ SEVERITY_LABELS[row.severity] || row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="STATUS_TONES[row.status] === 'risk' ? 'danger' : STATUS_TONES[row.status]" size="small">
              {{ STATUS_LABELS[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发值" width="100">
          <template #default="{ row }">{{ row.triggeredValue?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="触发时间" width="140">
          <template #default="{ row }">{{ formatTime(row.triggeredAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'firing'"
              size="small"
              text
              type="primary"
              @click="handleAcknowledgeEvent(row.id)"
            >
              确认
            </el-button>
            <span v-else-if="row.acknowledgedByName" class="text-secondary">
              {{ row.acknowledgedByName }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!normalizedEvents.length" class="monitoring__empty">暂无告警事件</div>
    </section>

    <!-- Dialog -->
    <AlertRuleDialog
      v-model:visible="dialogVisible"
      :rule="editingRule"
      @submit="handleRuleSubmit"
    />
  </div>
</template>

<style scoped>
.monitoring {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.monitoring__section {
  background: var(--surface-1, #fff);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--line-soft, #e5e7eb);
}

.monitoring__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.monitoring__heading {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin: 0 0 16px 0;
}

.monitoring__section-header .monitoring__heading {
  margin: 0;
}

.monitoring__service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.monitoring__gauge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.gauge-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface-0, #f9fafb);
  border: 1px solid var(--line-soft, #e5e7eb);
}

.gauge-card__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.gauge-card__label {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.gauge-card__value {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.gauge-card__value.tone-success { color: var(--success, #22c55e); }
.gauge-card__value.tone-warning { color: var(--warning, #f59e0b); }
.gauge-card__value.tone-risk { color: var(--risk, #ef4444); }

.gauge-card__meta {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-secondary, #6b7280);
}

.monitoring__chart-wrapper {
  margin-top: 8px;
}

.monitoring__empty {
  text-align: center;
  padding: 32px;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
}

.text-secondary {
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
}

/* Reuse service card styles for Celery */
.service-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  background: var(--surface-1, #fff);
  border: 1px solid var(--line-soft, #e5e7eb);
}

.service-card__dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--success, #22c55e);
}

.tone-risk .service-card__dot { background: var(--risk, #ef4444); }
.tone-warning .service-card__dot { background: var(--warning, #f59e0b); }

.service-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.service-card__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.service-card__detail {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}

@media (max-width: 900px) {
  .monitoring__service-grid,
  .monitoring__gauge-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 600px) {
  .monitoring__service-grid,
  .monitoring__gauge-grid {
    grid-template-columns: 1fr;
  }
}
</style>
