<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { RouterLink } from 'vue-router';
import AdminChart from '../AdminChart.vue';
import ServiceStatusCard from './ServiceStatusCard.vue';
import AlertRuleDialog from './AlertRuleDialog.vue';
import AppIcon from '../../ui/AppIcon.vue';
import { monitoringApi } from '../../../api/monitoring.js';
import {
  normalizeMonitoringPayload,
  normalizeMetricTimeSeries,
  buildServiceStatusCards,
  buildResourceGauges,
  buildCeleryStatus,
  buildMetricTimeSeriesOption,
  formatAlertTime,
  getMetricLabel,
  getNotificationChannelLabel,
  normalizeAlertRule,
  normalizeAlertEvent,
  ALERT_RULE_TEMPLATES,
  SEVERITY_LABELS,
  SEVERITY_TONES,
  CONDITION_LABELS,
  STATUS_LABELS,
  STATUS_TONES,
  METRIC_OPTIONS,
  sortAlertEventsByPriority,
  summarizeAlertEvents,
  summarizeAlertSeverities,
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
const prioritizedEvents = computed(() => sortAlertEventsByPriority(normalizedEvents.value));
const eventSummary = computed(() => summarizeAlertEvents(normalizedEvents.value));
const severitySummary = computed(() => summarizeAlertSeverities(normalizedEvents.value));
const priorityEvents = computed(() => prioritizedEvents.value.filter((event) => event.status !== 'resolved').slice(0, 3));
const recommendedTemplates = ALERT_RULE_TEMPLATES;
const alertSummaryCards = computed(() => ([
  { key: 'firing', label: '待处理', icon: 'bell-dot', value: eventSummary.value.firing, tone: 'firing' },
  { key: 'critical', label: '严重告警', icon: 'shield-alert', value: severitySummary.value.critical, tone: 'critical' },
  { key: 'acknowledged', label: '已确认', icon: 'check', value: eventSummary.value.acknowledged, tone: 'acknowledged' },
  { key: 'resolved', label: '已恢复', icon: 'shield', value: eventSummary.value.resolved, tone: 'resolved' },
]));
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

function handleCreateFromTemplate(template) {
  editingRule.value = { ...template };
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

async function handleSeedDefaultRules() {
  try {
    const result = await monitoringApi.seedDefaultAlertRules();
    const rulesData = await monitoringApi.listAlertRules();
    rules.value = Array.isArray(rulesData) ? rulesData : [];
    ElMessage.success(
      result.created
        ? `已初始化 ${result.created} 条默认规则`
        : '默认规则已存在，无需重复初始化',
    );
  } catch (err) {
    ElMessage.error(err.message || '初始化默认规则失败');
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
    const nextEnabled = !rule.enabled;
    const rulesData = await monitoringApi.listAlertRules();
    rules.value = Array.isArray(rulesData) ? rulesData : [];
    ElMessage.success(nextEnabled ? '规则已启用' : '规则已禁用');
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

function getPriorityEventIcon(event) {
  if (event?.severity === 'critical') {
    return 'shield-alert';
  }

  if (event?.severity === 'warning') {
    return 'triangle-alert';
  }

  return 'circle-alert';
}

onMounted(loadAll);
</script>

<template>
  <div v-loading="loading" class="monitoring">
    <!-- Service Status -->
    <section class="monitoring__section">
      <div class="monitoring__section-header monitoring__section-header--compact">
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="server" />
          </span>
          <h3 class="monitoring__heading">服务状态</h3>
        </div>
      </div>
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
      <div class="monitoring__section-header monitoring__section-header--compact">
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="gauge" />
          </span>
          <h3 class="monitoring__heading">系统资源</h3>
        </div>
      </div>
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
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="activity" />
          </span>
          <h3 class="monitoring__heading">指标趋势</h3>
        </div>
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

    <section class="monitoring__section">
      <div class="monitoring__section-header">
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="siren" />
          </span>
          <h3 class="monitoring__heading">告警态势</h3>
        </div>
        <RouterLink to="/admin/notifications" class="monitoring__inline-link">
          <AppIcon name="arrow-right" />
          进入告警中心
        </RouterLink>
      </div>
      <div class="monitoring__alert-summary-grid">
        <article
          v-for="card in alertSummaryCards"
          :key="card.key"
          class="monitoring__alert-summary-card"
          :class="`is-${card.tone}`"
        >
          <span class="monitoring__alert-summary-icon">
            <AppIcon :name="card.icon" />
          </span>
          <div class="monitoring__alert-summary-copy">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </div>
        </article>
      </div>

      <div v-if="priorityEvents.length" class="monitoring__priority-grid">
        <article
          v-for="event in priorityEvents"
          :key="event.id"
          class="monitoring__priority-card"
          :class="`tone-${SEVERITY_TONES[event.severity]}`"
        >
          <div class="monitoring__priority-head">
            <div class="monitoring__priority-title">
              <span class="monitoring__priority-icon" :class="`tone-${SEVERITY_TONES[event.severity]}`">
                <AppIcon :name="getPriorityEventIcon(event)" />
              </span>
              <strong>{{ event.ruleName }}</strong>
            </div>
            <el-tag :type="SEVERITY_TONES[event.severity] === 'risk' ? 'danger' : SEVERITY_TONES[event.severity]" size="small">
              {{ SEVERITY_LABELS[event.severity] || event.severity }}
            </el-tag>
          </div>
          <p>{{ getMetricLabel(event.metricName) }} · 触发值 {{ event.triggeredValue?.toFixed(2) }}</p>
          <span>{{ STATUS_LABELS[event.status] || event.status }} · {{ formatAlertTime(event.triggeredAt) }}</span>
        </article>
      </div>
      <div v-else class="monitoring__empty monitoring__empty--compact">当前没有待处理告警</div>
    </section>

    <!-- Alert Rules -->
    <section class="monitoring__section">
      <div class="monitoring__section-header">
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="settings-2" />
          </span>
          <h3 class="monitoring__heading">告警规则</h3>
        </div>
        <div class="monitoring__header-actions">
          <el-button size="small" @click="handleSeedDefaultRules">初始化默认规则</el-button>
          <el-button size="small" type="primary" @click="handleCreateRule">新建规则</el-button>
        </div>
      </div>
      <div v-if="!normalizedRules.length" class="monitoring__setup-panel">
        <div class="monitoring__setup-guide">
          <h4>当前还没有配置任何告警规则</h4>
          <ol>
            <li>先确保定时任务已启用：指标采集和告警评估会定期写入并比对监控数据。</li>
            <li>至少先配置 CPU、内存、磁盘和 Celery Worker 四条基础规则。</li>
            <li>通知方式选择“站内通知”后，管理员可在右上角铃铛和告警中心接收提醒。</li>
          </ol>
          <div class="monitoring__setup-actions">
            <el-button size="small" @click="handleSeedDefaultRules">一键初始化默认规则</el-button>
            <el-button size="small" type="primary" @click="handleCreateRule">手动新建规则</el-button>
          </div>
        </div>
        <div class="monitoring__template-grid">
          <button
            v-for="template in recommendedTemplates"
            :key="template.name"
            type="button"
            class="monitoring__template-card"
            @click="handleCreateFromTemplate(template)"
          >
            <div class="monitoring__template-meta">
              <el-tag
                size="small"
                :type="SEVERITY_TONES[template.severity] === 'risk' ? 'danger' : SEVERITY_TONES[template.severity]"
              >
                {{ SEVERITY_LABELS[template.severity] || template.severity }}
              </el-tag>
              <span>{{ getNotificationChannelLabel(template.notification_channels[0]) }}</span>
            </div>
            <div class="monitoring__template-title">{{ template.name }}</div>
            <div class="monitoring__template-detail">
              {{ getMetricLabel(template.metric_name) }} · {{ CONDITION_LABELS[template.condition] || template.condition }} {{ template.threshold }}
            </div>
            <p>{{ template.description }}</p>
            <span>按此模板创建</span>
          </button>
        </div>
      </div>
      <el-table :data="normalizedRules" size="small" stripe>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="指标" min-width="140">
          <template #default="{ row }">
            {{ getMetricLabel(row.metricName) }}
          </template>
        </el-table-column>
        <el-table-column label="条件" min-width="140">
          <template #default="{ row }">
            {{ CONDITION_LABELS[row.condition] || row.condition }} {{ row.threshold }}
          </template>
        </el-table-column>
        <el-table-column label="通知方式" min-width="180">
          <template #default="{ row }">
            <div v-if="row.notificationChannels.length" class="monitoring__channel-list">
              <el-tag
                v-for="channel in row.notificationChannels"
                :key="`${row.id}-${channel}`"
                size="small"
                effect="plain"
              >
                {{ getNotificationChannelLabel(channel) }}
              </el-tag>
            </div>
            <span v-else class="text-secondary">未配置</span>
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
      <div class="monitoring__section-header monitoring__section-header--compact">
        <div class="monitoring__heading-wrap">
          <span class="monitoring__heading-icon">
            <AppIcon name="bell-dot" />
          </span>
          <h3 class="monitoring__heading">告警事件</h3>
        </div>
      </div>
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
          <template #default="{ row }">{{ formatAlertTime(row.triggeredAt) }}</template>
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
  gap: 12px;
}

.monitoring__section-header--compact {
  margin-bottom: 16px;
}

.monitoring__header-actions,
.monitoring__setup-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.monitoring__heading-wrap {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.monitoring__heading-icon,
.monitoring__alert-summary-icon,
.monitoring__priority-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid var(--line-soft, #e5e7eb);
  background: var(--surface-0, #f9fafb);
  color: var(--brand, #2457c5);
  flex-shrink: 0;
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

.monitoring__inline-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand, #2457c5);
  text-decoration: none;
}

.monitoring__alert-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.monitoring__alert-summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--line-soft, #e5e7eb);
  background: var(--surface-0, #f9fafb);
}

.monitoring__alert-summary-copy {
  display: grid;
  gap: 6px;
}

.monitoring__alert-summary-copy span {
  display: block;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}

.monitoring__alert-summary-copy strong {
  display: block;
  font-size: 26px;
  line-height: 1;
  color: var(--text-primary, #111827);
}

.monitoring__alert-summary-card.is-firing .monitoring__alert-summary-icon,
.monitoring__priority-icon.tone-risk {
  color: var(--risk, #ef4444);
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.08);
}

.monitoring__alert-summary-card.is-critical .monitoring__alert-summary-icon {
  color: var(--risk, #ef4444);
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.08);
}

.monitoring__priority-icon.tone-warning {
  color: var(--warning, #f59e0b);
  border-color: rgba(245, 158, 11, 0.18);
  background: rgba(245, 158, 11, 0.1);
}

.monitoring__alert-summary-card.is-acknowledged .monitoring__alert-summary-icon,
.monitoring__priority-icon.tone-info {
  color: var(--brand, #2457c5);
  border-color: rgba(36, 87, 197, 0.18);
  background: rgba(36, 87, 197, 0.08);
}

.monitoring__alert-summary-card.is-resolved .monitoring__alert-summary-icon {
  color: var(--success, #22c55e);
  border-color: rgba(34, 197, 94, 0.18);
  background: rgba(34, 197, 94, 0.08);
}

.monitoring__priority-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.monitoring__priority-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid var(--line-soft, #e5e7eb);
  background: var(--surface-0, #f9fafb);
}

.monitoring__priority-card.tone-risk {
  border-color: rgba(239, 68, 68, 0.24);
}

.monitoring__priority-card.tone-warning {
  border-color: rgba(245, 158, 11, 0.24);
}

.monitoring__priority-card.tone-info {
  border-color: rgba(36, 87, 197, 0.24);
}

.monitoring__priority-head,
.monitoring__template-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.monitoring__priority-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.monitoring__priority-card strong,
.monitoring__template-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary, #111827);
}

.monitoring__priority-card p,
.monitoring__priority-card span,
.monitoring__template-meta span {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary, #6b7280);
}

.monitoring__empty {
  text-align: center;
  padding: 32px;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
}

.monitoring__empty--compact {
  padding: 20px 0 8px;
}

.text-secondary {
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
}

.monitoring__setup-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 16px;
  padding: 18px;
  margin-bottom: 16px;
  border: 1px dashed var(--line-soft, #e5e7eb);
  border-radius: 14px;
  background: var(--surface-0, #f9fafb);
}

.monitoring__setup-guide h4 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary, #111827);
}

.monitoring__setup-guide ol {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 12px;
}

.monitoring__template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.monitoring__template-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--line-soft, #e5e7eb);
  border-radius: 12px;
  background: var(--surface-1, #fff);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.monitoring__template-card:hover {
  border-color: var(--brand, #2457c5);
  transform: translateY(-1px);
}

.monitoring__template-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary, #111827);
}

.monitoring__template-detail,
.monitoring__template-card p,
.monitoring__template-card span {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  line-height: 1.6;
}

.monitoring__template-card span {
  color: var(--brand, #2457c5);
  font-weight: 600;
}

.monitoring__channel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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
  .monitoring__alert-summary-grid,
  .monitoring__priority-grid,
  .monitoring__service-grid,
  .monitoring__gauge-grid {
    grid-template-columns: 1fr 1fr;
  }

  .monitoring__setup-panel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .monitoring__alert-summary-grid,
  .monitoring__priority-grid,
  .monitoring__service-grid,
  .monitoring__gauge-grid {
    grid-template-columns: 1fr;
  }
}
</style>
