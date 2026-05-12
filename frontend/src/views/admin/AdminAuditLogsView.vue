<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { dashboardApi } from '../../api/dashboard.js';
import AdminChart from '../../components/admin/AdminChart.vue';
import OpsSectionFrame from '../../components/admin/ops/OpsSectionFrame.vue';
import AppIcon from '../../components/ui/AppIcon.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import { buildAuditTrendOption } from '../../lib/admin-audit-chart.js';
import {
  DETAIL_LABELS,
  DETAIL_ORDER,
  formatAuditAction,
  formatAuditDetail,
  formatAuditStatus,
  formatDetailValue,
  getAuditActionTone,
  hasDisplayValue,
} from '../../lib/admin-audit.js';

/* ---------- State ---------- */

const audits = ref([]);
const isLoading = ref(false);
const errorMsg = ref('');
const currentPage = ref(1);
const pageSize = ref(25);
const total = ref(0);
const expandedRows = ref([]);
const showRawJson = ref({});

const trendData = ref([]);
const statsCount7d = ref(0);
const statsCountPrev7d = ref(0);

const draftFilters = reactive({ keyword: '', status: '', action: '', dateRange: [] });
const appliedFilters = reactive({ keyword: '', status: '', action: '', dateRange: [] });

/* ---------- Options ---------- */

const statusOptions = [
  { label: '已提交', value: 'submitted' },
  { label: '成功', value: 'succeeded' },
  { label: '失败', value: 'failed' },
  { label: '已重试', value: 'retried' },
  { label: '已跳过', value: 'skipped' },
];

const actionOptions = [
  { label: '知识入库', value: 'knowledgebase.ingest' },
  { label: '上传文档', value: 'knowledgebase.document.upload' },
  { label: '删除文档', value: 'knowledgebase.document.delete' },
  { label: '批量提交入库', value: 'knowledgebase.document.batch_ingest' },
  { label: '批量删除文档', value: 'knowledgebase.document.batch_delete' },
  { label: '创建数据集', value: 'knowledgebase.dataset.create' },
  { label: '上传文档新版本', value: 'knowledgebase.document_version.upload' },
  { label: '新增清洗规则', value: 'knowledgebase.cleaning_rule.create' },
  { label: '更新清洗规则', value: 'knowledgebase.cleaning_rule.update' },
  { label: '删除清洗规则', value: 'knowledgebase.cleaning_rule.delete' },
  { label: '执行文档清洗', value: 'knowledgebase.document.clean' },
  { label: '风险提取', value: 'risk.extract' },
  { label: '重试风险提取', value: 'risk.extract.retry' },
  { label: '批量风险提取', value: 'risk.batch_extract' },
  { label: '重试批量提取', value: 'risk.batch_extract.retry' },
  { label: '舆情分析', value: 'risk.sentiment' },
  { label: '创建用户', value: 'rbac.user.create' },
  { label: '更新用户', value: 'rbac.user.update' },
  { label: '删除用户', value: 'rbac.user.delete' },
  { label: '调整用户角色', value: 'rbac.user.groups.replace' },
  { label: '新增模型配置', value: 'llm.model_config.create' },
  { label: '更新模型配置', value: 'llm.model_config.update' },
  { label: '删除模型配置', value: 'llm.model_config.delete' },
  { label: '切换模型启用状态', value: 'llm.model_config.set_active_state' },
  { label: '测试模型连接', value: 'llm.model_config.test_connection' },
  { label: '更新 Prompt 模板', value: 'llm.prompt_config.update' },
  { label: '执行模型评测', value: 'llm.evaluation.run' },
  { label: '新增训练服务器', value: 'llm.fine_tune_runner_server.create' },
  { label: '更新训练服务器', value: 'llm.fine_tune_runner_server.update' },
  { label: '删除训练服务器', value: 'llm.fine_tune_runner_server.delete' },
  { label: '创建微调任务', value: 'llm.fine_tune_run.create' },
  { label: '更新微调任务', value: 'llm.fine_tune_run.update' },
  { label: '派发微调任务', value: 'llm.fine_tune_run.dispatch' },
];

/* ---------- Computed ---------- */

const trendOption = computed(() => buildAuditTrendOption(trendData.value));

const weekDelta = computed(() => {
  const cur = statsCount7d.value;
  const prev = statsCountPrev7d.value;
  if (prev <= 0) return cur > 0 ? { label: '本周开始有记录', tone: 'up' } : { label: '较上周持平', tone: 'neutral' };
  const pct = ((cur - prev) / prev) * 100;
  const rounded = `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
  if (pct > 0) return { label: `较上周 ${rounded}`, tone: 'up' };
  if (pct < 0) return { label: `较上周 ${rounded}`, tone: 'down' };
  return { label: '较上周持平', tone: 'neutral' };
});

const statsCards = computed(() => {
  const all = audits.value;
  const succeeded = all.filter((r) => r.status === 'succeeded').length;
  const failed = all.filter((r) => r.status === 'failed').length;
  const submitted = all.filter((r) => r.status === 'submitted').length;
  const actors = new Set(all.map((r) => r.actor_name).filter(Boolean)).size;
  return [
    { label: '总记录', value: total.value || all.length, tone: '' },
    { label: '成功', value: succeeded, tone: '' },
    { label: '失败', value: failed, tone: failed > 0 ? 'risk' : '' },
    { label: '已提交', value: submitted, tone: '' },
    { label: '操作人员', value: actors, tone: '' },
  ];
});

const filteredAudits = computed(() => {
  const [start, end] = appliedFilters.dateRange || [];
  if (!start && !end) return audits.value;
  const startTime = start ? new Date(start).getTime() : 0;
  const endTime = end ? new Date(end).getTime() + 86400000 : Infinity;
  return audits.value.filter((row) => {
    const t = new Date(row.created_at).getTime();
    return t >= startTime && t < endTime;
  });
});

const ACTION_TONES_MAP = {};

/* ---------- Data fetching ---------- */

const fetchStats = async () => {
  try {
    const data = await dashboardApi.getStats();
    trendData.value = Array.isArray(data.audit_operations_7d) ? data.audit_operations_7d : [];
    statsCount7d.value = Number(data.audit_operation_count_7d) || 0;
    statsCountPrev7d.value = Number(data.audit_operation_count_prev_7d) || 0;
  } catch {
    /* non-critical, trend just stays empty */
  }
};

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = { page: currentPage.value, page_size: pageSize.value };
    if (appliedFilters.keyword) params.search = appliedFilters.keyword.trim();
    if (appliedFilters.status) params.status = appliedFilters.status;
    if (appliedFilters.action) params.action = appliedFilters.action;
    const data = await dashboardApi.getAudits(params);
    audits.value = data.results || data.audits || [];
    total.value = data.total || 0;
  } catch (err) {
    errorMsg.value = err.message || '加载操作日志失败';
  } finally {
    isLoading.value = false;
  }
};

/* ---------- Filter actions ---------- */

const applyFilters = () => {
  Object.assign(appliedFilters, {
    keyword: draftFilters.keyword,
    status: draftFilters.status,
    action: draftFilters.action,
    dateRange: draftFilters.dateRange,
  });
  currentPage.value = 1;
  fetchData();
};

const resetFilters = () => {
  Object.assign(draftFilters, { keyword: '', status: '', action: '', dateRange: [] });
  Object.assign(appliedFilters, { keyword: '', status: '', action: '', dateRange: [] });
  currentPage.value = 1;
  fetchData();
};

/* ---------- Pagination ---------- */

const handlePageChange = (page) => {
  currentPage.value = page;
  fetchData();
};

const handleSizeChange = (size) => {
  pageSize.value = size;
  currentPage.value = 1;
  fetchData();
};

/* ---------- Row expand ---------- */

const toggleExpand = (row) => {
  const idx = expandedRows.value.findIndex((r) => r.id === row.id);
  if (idx >= 0) {
    expandedRows.value.splice(idx, 1);
  } else {
    expandedRows.value.push(row);
  }
};

const isExpanded = (row) => expandedRows.value.some((r) => r.id === row.id);

/* ---------- Detail helpers ---------- */

const orderedDetailEntries = (payload) => {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return [];
  return Object.entries(payload)
    .filter(([, v]) => hasDisplayValue(v))
    .sort(([a], [b]) => {
      const ia = DETAIL_ORDER.indexOf(a);
      const ib = DETAIL_ORDER.indexOf(b);
      const sa = ia === -1 ? DETAIL_ORDER.length : ia;
      const sb = ib === -1 ? DETAIL_ORDER.length : ib;
      return sa !== sb ? sa - sb : a.localeCompare(b, 'zh-CN');
    });
};

const detailLabel = (key) => DETAIL_LABELS[key] || key;

const toggleRawJson = (id) => {
  showRawJson.value[id] = !showRawJson.value[id];
};

const copyJson = async (payload) => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
  } catch {
    /* ignore */
  }
};

/* ---------- Time formatting ---------- */

const pad = (n) => String(n).padStart(2, '0');
const formatTime = (iso) => {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return iso;
  }
};

/* ---------- Lifecycle ---------- */

onMounted(() => {
  fetchStats();
  fetchData();
});
</script>

<template>
  <OpsSectionFrame>
    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <!-- Stats strip -->
    <div class="audit-stats">
      <div
        v-for="card in statsCards"
        :key="card.label"
        class="audit-stat"
        :class="{ 'has-risk': card.tone === 'risk' }"
      >
        <span class="audit-stat__label">{{ card.label }}</span>
        <strong class="audit-stat__num">{{ card.value }}</strong>
      </div>
    </div>

    <!-- 7-day trend -->
    <AppSectionCard admin class="audit-trend-card">
      <div class="audit-trend-header">
        <span class="audit-trend-title">近 7 日操作趋势</span>
        <span v-if="weekDelta" :class="['audit-trend-delta', `is-${weekDelta.tone}`]">
          {{ weekDelta.label }}
        </span>
      </div>
      <AdminChart :option="trendOption" height="200px" />
    </AppSectionCard>

    <!-- Filters -->
    <section class="audit-filters">
      <div class="audit-filters__grid">
        <label class="audit-field audit-field--keyword">
          <span>搜索</span>
          <el-input
            v-model="draftFilters.keyword"
            clearable
            placeholder="操作人或操作类型"
            @keyup.enter="applyFilters"
          >
            <template #prefix>
              <AppIcon name="search" />
            </template>
          </el-input>
        </label>

        <label class="audit-field">
          <span>状态</span>
          <el-select v-model="draftFilters.status" clearable placeholder="全部状态">
            <el-option
              v-for="opt in statusOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </label>

        <label class="audit-field">
          <span>操作类型</span>
          <el-select v-model="draftFilters.action" clearable filterable placeholder="全部操作">
            <el-option
              v-for="opt in actionOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </label>

        <label class="audit-field">
          <span>时间范围</span>
          <el-date-picker
            v-model="draftFilters.dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            :default-time="[new Date(0, 0, 0, 0, 0, 0), new Date(0, 0, 0, 23, 59, 59)]"
          />
        </label>
      </div>

      <div class="audit-filters__actions">
        <el-button type="primary" :loading="isLoading" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <!-- Table card -->
    <AppSectionCard admin class="audit-table-card">
      <el-table
        :data="filteredAudits"
        row-key="id"
        size="small"
        stripe
        v-loading="isLoading"
        element-loading-text="加载中..."
      >
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div class="audit-detail-panel">
              <div class="audit-detail-panel__header">
                <span class="audit-detail-panel__title">操作详情</span>
                <div class="audit-detail-panel__actions">
                  <el-button text size="small" @click="copyJson(row.detail_payload)">
                    <AppIcon name="copy" /> 复制 JSON
                  </el-button>
                  <el-button text size="small" @click="toggleRawJson(row.id)">
                    {{ showRawJson[row.id] ? '收起原始数据' : '查看原始数据' }}
                  </el-button>
                </div>
              </div>

              <div v-if="orderedDetailEntries(row.detail_payload).length" class="audit-detail-grid">
                <div
                  v-for="[key, value] in orderedDetailEntries(row.detail_payload)"
                  :key="key"
                  class="audit-detail-item"
                >
                  <span class="audit-detail-item__key">{{ detailLabel(key) }}</span>
                  <span class="audit-detail-item__value">{{ formatDetailValue(value) }}</span>
                </div>
              </div>
              <div v-else class="audit-detail-empty">无详细信息</div>

              <pre
                v-if="showRawJson[row.id]"
                class="audit-detail-raw"
              >{{ JSON.stringify(row.detail_payload, null, 2) }}</pre>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="id" label="ID" width="64" />

        <el-table-column prop="actor_name" label="操作人" width="120">
          <template #default="{ row }">
            <span class="audit-actor">{{ row.actor_name || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="action" label="操作" min-width="140">
          <template #default="{ row }">
            <span class="audit-action-badge" :class="`is-${getAuditActionTone(row.action)}`">
              {{ formatAuditAction(row.action) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="detail_payload" label="详情" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="audit-detail-summary">{{ formatAuditDetail(row.detail_payload) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="target_type" label="目标类型" width="100">
          <template #default="{ row }">
            <span class="audit-muted">{{ row.target_type || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <span class="audit-status-badge" :class="`is-${row.status}`">
              {{ formatAuditStatus(row.status) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            <span class="audit-time">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80" align="right" fixed="right">
          <template #default="{ row }">
            <div class="audit-row-actions">
              <el-tooltip content="展开详情" placement="top">
                <button
                  type="button"
                  class="audit-icon-btn"
                  @click="toggleExpand(row)"
                >
                  <AppIcon name="chevron-down" />
                </button>
              </el-tooltip>
              <el-tooltip content="复制 JSON" placement="top">
                <button
                  type="button"
                  class="audit-icon-btn"
                  @click="copyJson(row.detail_payload)"
                >
                  <AppIcon name="copy" />
                </button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <div class="audit-empty">暂无操作记录</div>
        </template>
      </el-table>

      <div class="audit-pagination">
        <el-pagination
          small
          background
          :current-page="currentPage"
          :page-size="pageSize"
          :page-sizes="[10, 25, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </AppSectionCard>
  </OpsSectionFrame>
</template>

<style scoped>
/* ---- Stats Strip ---- */

.audit-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.audit-stat {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  padding: 14px 16px;
}

.audit-stat__label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.audit-stat__num {
  display: block;
  margin-top: 4px;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1;
}

.audit-stat.has-risk .audit-stat__num {
  color: var(--risk-red, #c4493d);
}

/* ---- Trend Card ---- */

.audit-trend-card {
  margin-top: var(--page-stack-gap, 12px);
}

.audit-trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.audit-trend-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.audit-trend-delta {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.audit-trend-delta.is-up {
  color: #3aab7a;
  background: rgba(33, 129, 92, 0.1);
}

.audit-trend-delta.is-down {
  color: #e07060;
  background: rgba(196, 73, 61, 0.1);
}

.audit-trend-delta.is-neutral {
  color: var(--text-muted);
  background: var(--surface-3);
}

/* ---- Filters ---- */

.audit-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  margin-top: var(--page-stack-gap, 12px);
  border: 1px solid var(--line-strong);
  border-radius: 20px;
  background: var(--surface-1);
}

.audit-filters__grid {
  display: grid;
  flex: 1 1 720px;
  grid-template-columns: minmax(200px, 2fr) repeat(3, minmax(160px, 1fr));
  gap: 12px;
}

.audit-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.audit-field span {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.audit-field--keyword {
  grid-column: span 1;
}

.audit-filters__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

/* ---- Table Card ---- */

.audit-table-card {
  margin-top: var(--page-stack-gap, 12px);
}

.audit-table-card :deep(.admin-section-card) {
  padding: 18px 20px;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
}

.audit-table-card :deep(.el-input__wrapper),
.audit-table-card :deep(.el-select__wrapper) {
  min-height: 36px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  border-radius: 12px;
}

.audit-table-card :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
}

.audit-table-card :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.audit-table-card :deep(.el-table th.el-table__cell) {
  height: 40px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
}

.audit-table-card :deep(.el-table td.el-table__cell) {
  padding-block: 8px;
  border-bottom-color: var(--line-soft);
}

.audit-table-card :deep(.el-table .cell) {
  min-height: 24px;
  padding-inline: 14px;
}

/* ---- Cell content ---- */

.audit-actor {
  font-weight: 600;
}

.audit-detail-summary {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.45;
}

.audit-muted {
  color: var(--text-secondary);
}

.audit-time {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.audit-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.audit-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.audit-icon-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

/* ---- Badges ---- */

.audit-action-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-3);
  color: var(--text-secondary);
}

.audit-action-badge.is-brand {
  background: rgba(36, 87, 197, 0.1);
  color: #5b8af5;
}

.audit-action-badge.is-risk {
  background: rgba(196, 73, 61, 0.1);
  color: #e07060;
}

.audit-action-badge.is-accent {
  background: rgba(91, 108, 255, 0.1);
  color: #7d8cff;
}

.audit-status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.audit-status-badge.is-succeeded {
  background: rgba(33, 129, 92, 0.1);
  color: #3aab7a;
}

.audit-status-badge.is-failed {
  background: rgba(196, 73, 61, 0.1);
  color: #e07060;
}

.audit-status-badge.is-pending {
  background: rgba(183, 121, 31, 0.1);
  color: #c9922a;
}

.audit-status-badge.is-retried {
  background: rgba(91, 108, 255, 0.1);
  color: #7d8cff;
}

.audit-status-badge.is-submitted {
  background: rgba(36, 87, 197, 0.12);
  color: #5b8af5;
}

.audit-status-badge.is-skipped {
  background: rgba(120, 128, 145, 0.12);
  color: #9ea9bc;
}

/* ---- Expanded Row ---- */

.audit-detail-panel {
  padding: 16px 20px;
  background: var(--surface-3);
  border-radius: 8px;
  margin: 4px 8px;
}

.audit-detail-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.audit-detail-panel__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.audit-detail-panel__actions {
  display: flex;
  gap: 4px;
}

.audit-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 24px;
}

.audit-detail-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.audit-detail-item__key {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  min-width: 80px;
}

.audit-detail-item__value {
  font-size: 12px;
  color: var(--text-primary);
  word-break: break-all;
}

.audit-detail-empty {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 0;
}

.audit-detail-raw {
  margin-top: 12px;
  padding: 12px;
  background: var(--surface-1);
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  font-family: 'Fira Code', monospace;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-x: auto;
  white-space: pre;
}

/* ---- Pagination ---- */

.audit-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 6px;
}

/* ---- Empty state ---- */

.audit-empty {
  padding: 40px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- Responsive ---- */

@media (max-width: 720px) {
  .audit-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .audit-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .audit-filters__grid {
    grid-template-columns: 1fr;
  }

  .audit-detail-grid {
    grid-template-columns: 1fr;
  }

  .audit-table-card :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }
}
</style>
