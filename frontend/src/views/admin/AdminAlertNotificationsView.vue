<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';

import { monitoringApi } from '../../api/monitoring.js';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import AppIcon from '../../components/ui/AppIcon.vue';
import {
  SEVERITY_LABELS,
  SEVERITY_TONES,
  STATUS_LABELS,
  STATUS_TONES,
  formatAlertTime,
  getMetricLabel,
  normalizeAlertEvent,
  sortAlertEventsByPriority,
  summarizeAlertEvents,
  summarizeAlertSeverities,
} from '../../lib/admin-monitoring.js';

const router = useRouter();
const loading = ref(true);
const events = ref([]);
const selectedStatus = ref('all');
const selectedSeverity = ref('all');

const normalizedEvents = computed(() => (Array.isArray(events.value) ? events.value.map(normalizeAlertEvent) : []));
const prioritizedEvents = computed(() => sortAlertEventsByPriority(normalizedEvents.value));
const summary = computed(() => summarizeAlertEvents(normalizedEvents.value));
const severitySummary = computed(() => summarizeAlertSeverities(normalizedEvents.value));
const priorityQueue = computed(() => prioritizedEvents.value.filter((event) => event.status !== 'resolved').slice(0, 3));
const leadEvent = computed(() => priorityQueue.value[0] || null);
const severityCards = computed(() => ([
  { key: 'critical', label: '严重', icon: 'shield-alert', value: severitySummary.value.critical, tone: 'critical' },
  { key: 'warning', label: '警告', icon: 'triangle-alert', value: severitySummary.value.warning, tone: 'warning' },
  { key: 'info', label: '提示', icon: 'circle-alert', value: severitySummary.value.info, tone: 'info' },
]));
const summaryCards = computed(() => ([
  { key: 'firing', label: '触发中', icon: 'bell-dot', value: summary.value.firing, tone: 'firing' },
  { key: 'acknowledged', label: '已确认', icon: 'check', value: summary.value.acknowledged, tone: 'acknowledged' },
  { key: 'resolved', label: '已恢复', icon: 'shield', value: summary.value.resolved, tone: 'resolved' },
  { key: 'all', label: '最近事件', icon: 'history', value: summary.value.all, tone: 'all' },
]));
const filteredEvents = computed(() => {
  let currentEvents = prioritizedEvents.value;

  if (selectedStatus.value !== 'all') {
    currentEvents = currentEvents.filter((event) => event.status === selectedStatus.value);
  }

  if (selectedSeverity.value !== 'all') {
    currentEvents = currentEvents.filter((event) => event.severity === selectedSeverity.value);
  }

  return currentEvents;
});

const statusOptions = [
  { value: 'all', label: '全部' },
  { value: 'firing', label: '触发中' },
  { value: 'acknowledged', label: '已确认' },
  { value: 'resolved', label: '已恢复' },
];

const severityOptions = [
  { value: 'all', label: '全部级别' },
  { value: 'critical', label: '严重' },
  { value: 'warning', label: '警告' },
  { value: 'info', label: '提示' },
];

async function loadEvents() {
  loading.value = true;
  try {
    const payload = await monitoringApi.listAlertEvents({ limit: 200 });
    events.value = Array.isArray(payload) ? payload : [];
  } catch (err) {
    ElMessage.error(err.message || '加载告警中心失败');
  } finally {
    loading.value = false;
  }
}

async function handleAcknowledge(eventId) {
  try {
    await monitoringApi.acknowledgeAlertEvent(eventId);
    ElMessage.success('告警已确认');
    await loadEvents();
  } catch (err) {
    ElMessage.error(err.message || '确认失败');
  }
}

function handleOpenMonitoring() {
  router.push('/admin/monitoring');
}

function getPriorityLabel(event) {
  if (!event) {
    return '';
  }

  if (event.status === 'firing' && event.severity === 'critical') {
    return '立即处理';
  }

  if (event.status === 'firing') {
    return '待处理';
  }

  if (event.status === 'acknowledged') {
    return '持续观察';
  }

  return '已恢复';
}

function getLeadIcon(event) {
  if (!event) {
    return 'shield-check';
  }

  if (event.severity === 'critical') {
    return 'shield-alert';
  }

  if (event.severity === 'warning') {
    return 'triangle-alert';
  }

  return 'circle-alert';
}

onMounted(loadEvents);
</script>

<template>
  <div v-loading="loading" class="alert-center">
    <AppSectionCard
      admin
      title="告警中心"
    >
      <section class="alert-center__triage-grid">
        <article
          class="alert-center__focus-card"
          :class="leadEvent ? `tone-${SEVERITY_TONES[leadEvent.severity]}` : 'is-calm'"
        >
          <template v-if="leadEvent">
            <div class="alert-center__focus-topline">
              <span class="alert-center__focus-icon" :class="`tone-${SEVERITY_TONES[leadEvent.severity]}`">
                <AppIcon :name="getLeadIcon(leadEvent)" />
              </span>
              <span class="alert-center__focus-kicker">{{ SEVERITY_LABELS[leadEvent.severity] || leadEvent.severity }}</span>
            </div>
            <div class="alert-center__focus-head">
              <div>
                <h4>{{ leadEvent.ruleName }}</h4>
                <p>{{ getMetricLabel(leadEvent.metricName) }} · 触发值 {{ leadEvent.triggeredValue?.toFixed(2) }}</p>
              </div>
              <span class="alert-center__priority-pill" :class="`tone-${SEVERITY_TONES[leadEvent.severity]}`">
                {{ getPriorityLabel(leadEvent) }}
              </span>
            </div>

            <dl class="alert-center__focus-meta">
              <div>
                <dt>严重程度</dt>
                <dd>{{ SEVERITY_LABELS[leadEvent.severity] || leadEvent.severity }}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>{{ STATUS_LABELS[leadEvent.status] || leadEvent.status }}</dd>
              </div>
              <div>
                <dt>触发时间</dt>
                <dd>{{ formatAlertTime(leadEvent.triggeredAt) }}</dd>
              </div>
            </dl>

            <div class="alert-center__focus-actions">
              <el-button
                v-if="leadEvent.status === 'firing'"
                type="danger"
                size="small"
                @click="handleAcknowledge(leadEvent.id)"
              >
                立即确认
              </el-button>
              <el-button size="small" @click="handleOpenMonitoring">
                前往系统监控
              </el-button>
            </div>
          </template>
          <template v-else>
            <div class="alert-center__focus-empty">
              <span class="alert-center__focus-icon is-calm">
                <AppIcon name="shield-check" />
              </span>
              <h4>当前无待处理告警</h4>
            </div>
            <div class="alert-center__focus-actions">
              <el-button size="small" @click="handleOpenMonitoring">
                查看规则配置
              </el-button>
            </div>
          </template>
        </article>

        <div class="alert-center__severity-grid">
          <article
            v-for="card in severityCards"
            :key="card.key"
            class="alert-center__severity-card"
            :class="`is-${card.tone}`"
          >
            <span class="alert-center__severity-icon">
              <AppIcon :name="card.icon" />
            </span>
            <div class="alert-center__stat-copy">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </div>
          </article>
        </div>
      </section>

      <div class="alert-center__summary-grid">
        <article
          v-for="card in summaryCards"
          :key="card.key"
          class="alert-center__summary-card"
          :class="card.tone !== 'all' ? `is-${card.tone}` : ''"
        >
          <span class="alert-center__summary-icon">
            <AppIcon :name="card.icon" />
          </span>
          <div class="alert-center__stat-copy">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </div>
        </article>
      </div>

      <div class="alert-center__toolbar">
        <div class="alert-center__filter-cluster">
          <el-radio-group v-model="selectedStatus" size="small">
            <el-radio-button
              v-for="option in statusOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>

          <el-radio-group v-model="selectedSeverity" size="small">
            <el-radio-button
              v-for="option in severityOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
        </div>

        <el-button size="small" @click="loadEvents">
          <AppIcon name="refresh" />
          刷新
        </el-button>
      </div>

      <el-table :data="filteredEvents" size="small" stripe>
        <el-table-column prop="ruleName" label="规则" min-width="180" />
        <el-table-column label="指标" min-width="140">
          <template #default="{ row }">
            {{ getMetricLabel(row.metricName) }}
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="96">
          <template #default="{ row }">
            <el-tag :type="SEVERITY_TONES[row.severity] === 'risk' ? 'danger' : SEVERITY_TONES[row.severity]" size="small">
              {{ SEVERITY_LABELS[row.severity] || row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="STATUS_TONES[row.status] === 'risk' ? 'danger' : STATUS_TONES[row.status]" size="small">
              {{ STATUS_LABELS[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发值" width="96">
          <template #default="{ row }">{{ row.triggeredValue?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="触发时间" width="140">
          <template #default="{ row }">{{ formatAlertTime(row.triggeredAt) }}</template>
        </el-table-column>
        <el-table-column label="确认人" min-width="120">
          <template #default="{ row }">{{ row.acknowledgedByName || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'firing'"
              size="small"
              text
              type="primary"
              @click="handleAcknowledge(row.id)"
            >
              确认
            </el-button>
            <span v-else class="alert-center__muted">无需操作</span>
          </template>
        </el-table-column>

        <template #empty>
          <div class="alert-center__empty">当前筛选下没有告警事件</div>
        </template>
      </el-table>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.alert-center {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.alert-center__triage-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 14px;
}

.alert-center__focus-card,
.alert-center__severity-card,
.alert-center__summary-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 18px;
  border: 1px solid rgba(157, 173, 196, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.alert-center__focus-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.alert-center__focus-head h4,
.alert-center__focus-card h4 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary, #f8fafc);
}

.alert-center__focus-head p,
.alert-center__focus-card p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary, #94a3b8);
}

.alert-center__focus-topline,
.alert-center__focus-empty {
  display: flex;
  align-items: center;
  gap: 10px;
}

.alert-center__focus-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--text-secondary, #94a3b8);
}

.alert-center__focus-icon,
.alert-center__severity-icon,
.alert-center__summary-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  border: 1px solid rgba(157, 173, 196, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary, #f8fafc);
  flex-shrink: 0;
}

.alert-center__focus-icon.tone-risk,
.alert-center__severity-card.is-critical .alert-center__severity-icon {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.24);
}

.alert-center__focus-icon.tone-warning,
.alert-center__severity-card.is-warning .alert-center__severity-icon {
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.14);
  border-color: rgba(245, 158, 11, 0.24);
}

.alert-center__focus-icon.tone-info,
.alert-center__severity-card.is-info .alert-center__severity-icon,
.alert-center__summary-card.is-acknowledged .alert-center__summary-icon {
  color: #93c5fd;
  background: rgba(36, 87, 197, 0.14);
  border-color: rgba(36, 87, 197, 0.24);
}

.alert-center__focus-icon.is-calm,
.alert-center__summary-card.is-resolved .alert-center__summary-icon {
  color: #86efac;
  background: rgba(34, 197, 94, 0.14);
  border-color: rgba(34, 197, 94, 0.22);
}

.alert-center__focus-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.alert-center__focus-meta dt,
.alert-center__severity-card span,
.alert-center__summary-card span {
  font-size: 12px;
  color: var(--text-secondary, #94a3b8);
}

.alert-center__focus-meta dd {
  margin: 4px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #f8fafc);
}

.alert-center__focus-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.alert-center__priority-pill {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.alert-center__priority-pill.tone-risk {
  background: rgba(239, 68, 68, 0.14);
  color: #fecaca;
}

.alert-center__priority-pill.tone-warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}

.alert-center__priority-pill.tone-info {
  background: rgba(36, 87, 197, 0.14);
  color: #93c5fd;
}

.alert-center__focus-card.tone-risk {
  border-color: rgba(239, 68, 68, 0.32);
  background: linear-gradient(180deg, rgba(239, 68, 68, 0.08), rgba(255, 255, 255, 0.03));
}

.alert-center__focus-card.tone-warning {
  border-color: rgba(245, 158, 11, 0.32);
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.08), rgba(255, 255, 255, 0.03));
}

.alert-center__focus-card.tone-info {
  border-color: rgba(36, 87, 197, 0.28);
}

.alert-center__focus-card.is-calm {
  justify-content: center;
}

.alert-center__focus-card.is-calm .alert-center__focus-actions {
  margin-top: 4px;
}

.alert-center__severity-grid,
.alert-center__summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.alert-center__summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.alert-center__severity-card,
.alert-center__summary-card {
  gap: 12px;
}

.alert-center__stat-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.alert-center__severity-card strong,
.alert-center__summary-card strong {
  font-size: 28px;
  line-height: 1;
  color: var(--text-primary, #f8fafc);
}

.alert-center__severity-card.is-critical {
  border-color: rgba(239, 68, 68, 0.24);
}

.alert-center__severity-card.is-warning {
  border-color: rgba(245, 158, 11, 0.24);
}

.alert-center__severity-card.is-info {
  border-color: rgba(36, 87, 197, 0.24);
}

.alert-center__summary-card.is-firing {
  border-color: rgba(239, 68, 68, 0.24);
}

.alert-center__summary-card.is-acknowledged {
  border-color: rgba(36, 87, 197, 0.24);
}

.alert-center__summary-card.is-resolved {
  border-color: rgba(34, 197, 94, 0.24);
}

.alert-center__summary-card.is-firing .alert-center__summary-icon {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.24);
}

.alert-center__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.alert-center__filter-cluster {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.alert-center__muted,
.alert-center__empty {
  font-size: 12px;
  color: var(--text-secondary, #94a3b8);
}

.alert-center__empty {
  padding: 32px 0;
}

@media (max-width: 900px) {
  .alert-center__triage-grid,
  .alert-center__focus-meta,
  .alert-center__summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alert-center__severity-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .alert-center__triage-grid,
  .alert-center__focus-meta,
  .alert-center__summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
