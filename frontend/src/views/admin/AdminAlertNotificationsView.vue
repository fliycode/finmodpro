<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

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
  summarizeAlertEvents,
} from '../../lib/admin-monitoring.js';

const loading = ref(true);
const events = ref([]);
const selectedStatus = ref('all');

const normalizedEvents = computed(() => (Array.isArray(events.value) ? events.value.map(normalizeAlertEvent) : []));
const summary = computed(() => summarizeAlertEvents(normalizedEvents.value));
const filteredEvents = computed(() => {
  if (selectedStatus.value === 'all') {
    return normalizedEvents.value;
  }
  return normalizedEvents.value.filter((event) => event.status === selectedStatus.value);
});

const statusOptions = [
  { value: 'all', label: '全部' },
  { value: 'firing', label: '触发中' },
  { value: 'acknowledged', label: '已确认' },
  { value: 'resolved', label: '已恢复' },
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

onMounted(loadEvents);
</script>

<template>
  <div v-loading="loading" class="alert-center">
    <AppSectionCard
      admin
      title="告警中心"
      desc="右上角铃铛与系统监控页共用同一批告警事件；这里适合集中查看、筛选和确认处理。"
    >
      <div class="alert-center__summary-grid">
        <article class="alert-center__summary-card is-firing">
          <span>触发中</span>
          <strong>{{ summary.firing }}</strong>
        </article>
        <article class="alert-center__summary-card is-acknowledged">
          <span>已确认</span>
          <strong>{{ summary.acknowledged }}</strong>
        </article>
        <article class="alert-center__summary-card is-resolved">
          <span>已恢复</span>
          <strong>{{ summary.resolved }}</strong>
        </article>
        <article class="alert-center__summary-card">
          <span>最近事件</span>
          <strong>{{ summary.all }}</strong>
        </article>
      </div>

      <div class="alert-center__toolbar">
        <el-radio-group v-model="selectedStatus" size="small">
          <el-radio-button
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.value"
          >
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>

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

.alert-center__summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.alert-center__summary-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 18px;
  border: 1px solid rgba(157, 173, 196, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.alert-center__summary-card span {
  font-size: 12px;
  color: var(--text-secondary, #94a3b8);
}

.alert-center__summary-card strong {
  font-size: 28px;
  line-height: 1;
  color: var(--text-primary, #f8fafc);
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

.alert-center__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
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
  .alert-center__summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .alert-center__summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
