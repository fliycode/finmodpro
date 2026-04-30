<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import { riskApi } from '../api/risk.js';
import {
  buildDashboardDocumentOption,
  buildDashboardDonutOption,
  buildDashboardIndustryRows,
  buildDashboardRegionRows,
  buildDashboardRiskLevelOption,
  buildDashboardSourceRows,
  buildDashboardSummaryMetrics,
  buildDashboardTrendOption,
  normalizeDashboardPayload,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppIcon from './ui/AppIcon.vue';

const router = useRouter();
const dashboardStats = ref(normalizeDashboardPayload({}));
const audits = ref([]);
const isLoading = ref(true);
const errorMsg = ref('');
const refreshedAt = ref('');

const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatNumber = (value) => numberFormatter.format(Math.max(0, Math.round(Number(value) || 0)));

const formatTimestamp = (value) => {
  if (!value) {
    return '未更新';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
};

const formatShortTime = (value) => {
  if (!value) {
    return '--';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
};

const formatStatus = (status) => {
  const labels = {
    queued: '排队中',
    running: '进行中',
    succeeded: '成功',
    failed: '失败',
    pending: '待处理',
    approved: '已通过',
    rejected: '已驳回',
    hit: '命中',
    miss: '未命中',
  };

  return labels[status] || status || '状态';
};

const formatAuditAction = (action) => {
  const labels = {
    'knowledgebase.ingest': '知识入库',
    'risk.extract': '风险提取',
    'risk.batch_extract': '批量提取',
    'risk.sentiment': '舆情分析',
  };
  return labels[action] || action || '审计事件';
};

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';

  try {
    const [statsRes, auditRes] = await Promise.all([
      dashboardApi.getStats(),
      dashboardApi.getAudits({ limit: 8 }).catch(() => null),
    ]);
    dashboardStats.value = normalizeDashboardPayload(statsRes);
    audits.value = Array.isArray(auditRes?.audits)
      ? auditRes.audits
      : dashboardStats.value.audit_snippets;
    refreshedAt.value = formatTimestamp(Date.now());
  } catch (error) {
    console.error('Dashboard data fetch failed:', error);
    errorMsg.value = '加载数据看板失败，请稍后重试。';
    ElMessage.error(errorMsg.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const summaryMetrics = computed(() => buildDashboardSummaryMetrics(dashboardStats.value));
const industryRows = computed(() => buildDashboardIndustryRows(dashboardStats.value));
const regionRows = computed(() => buildDashboardRegionRows(dashboardStats.value));
const sourceRows = computed(() => buildDashboardSourceRows({
  ...dashboardStats.value,
  audit_snippets: audits.value,
}));

const trendOption = computed(() => buildDashboardTrendOption(dashboardStats.value));
const industryOption = computed(() => buildDashboardDonutOption(industryRows.value, ['34%', '50%']));
const riskLevelOption = computed(() => buildDashboardRiskLevelOption(dashboardStats.value));
const sourceOption = computed(() => buildDashboardDonutOption(sourceRows.value, ['36%', '50%']));
const documentOption = computed(() => buildDashboardDocumentOption(dashboardStats.value));

const riskLevelRows = computed(() => {
  const distribution = dashboardStats.value.risk_level_distribution || {};
  const high = Number(distribution.high || 0) + Number(distribution.critical || 0);
  const medium = Number(distribution.medium || 0);
  const low = Number(distribution.low || 0);
  const total = Math.max(1, high + medium + low);

  return [
    { label: '高风险', value: high, color: '#f04d5d' },
    { label: '中风险', value: medium, color: '#f3a21b' },
    { label: '低风险', value: low, color: '#2f74ff' },
  ].map((item) => ({
    ...item,
    percent: `${(item.value / total * 100).toFixed(1)}%`,
  }));
});

const regionTiles = computed(() => {
  const positions = [
    [63, 31],
    [73, 49],
    [52, 25],
    [44, 56],
    [55, 48],
    [67, 62],
    [30, 35],
    [73, 21],
  ];

  return regionRows.value.map((row, index) => ({
    ...row,
    style: {
      '--tile-x': `${positions[index]?.[0] ?? 50}%`,
      '--tile-y': `${positions[index]?.[1] ?? 50}%`,
      '--tile-color': row.color,
    },
  }));
});

const processStats = computed(() => [
  {
    label: '文档总量',
    value: formatNumber(dashboardStats.value.document_count),
    icon: 'file-text',
  },
  {
    label: '已索引文档',
    value: formatNumber(dashboardStats.value.indexed_document_count),
    icon: 'database',
  },
  {
    label: '知识库入口',
    value: formatNumber(dashboardStats.value.knowledgebase_count),
    icon: 'layers',
  },
  {
    label: '近 24h 问答',
    value: formatNumber(dashboardStats.value.chat_request_count_24h),
    icon: 'message-square',
  },
  {
    label: '可重试入库',
    value: formatNumber(dashboardStats.value.retryable_ingestion_count),
    icon: 'refresh',
  },
  {
    label: '审计记录',
    value: formatNumber(audits.value.length),
    icon: 'clipboard',
  },
]);

const topEvents = computed(() => {
  const riskActivityRows = dashboardStats.value.recent_activity
    .filter((item) => item.type === 'risk')
    .slice(0, 5)
    .map((item, index) => {
      const [company = '风险样本'] = String(item.message || '').split(' 产生 ');
      const isHigh = item.tone === 'risk';

      return {
        id: `risk-${index}`,
        title: item.message || '风险事件待核查',
        company,
        level: isHigh ? '高' : '中',
        levelClass: isHigh ? 'is-high' : 'is-mid',
        value: isHigh ? '重点' : '观察',
        time: formatShortTime(item.timestamp),
      };
    });

  const failureRows = dashboardStats.value.recent_failures.slice(0, 3).map((item, index) => ({
    id: `failure-${item.id || index}`,
    title: `文档处理失败：${item.document_title || '未命名文档'}`,
    company: '知识库',
    level: '中',
    levelClass: 'is-mid',
    value: `重试 ${item.retry_count ?? 0}`,
    time: formatShortTime(item.updated_at),
  }));

  const auditRows = audits.value.slice(0, 4).map((item, index) => ({
    id: `audit-${item.id || index}`,
    title: item.summary || formatAuditAction(item.action),
    company: item.actor_name || '系统',
    level: item.status === 'failed' ? '高' : '低',
    levelClass: item.status === 'failed' ? 'is-high' : 'is-low',
    value: formatStatus(item.status),
    time: formatShortTime(item.created_at || item.timestamp),
    audit: item,
  }));

  const rows = [...riskActivityRows, ...failureRows, ...auditRows].slice(0, 10);

  if (rows.length > 0) {
    return rows;
  }

  return [
    {
      id: 'pending-risk',
      title: '待审核风险事件池',
      company: '风险中台',
      level: '高',
      levelClass: 'is-high',
      value: formatNumber(dashboardStats.value.pending_risk_event_count),
      time: '实时',
    },
    {
      id: 'failed-docs',
      title: '失败入库影响知识召回',
      company: '知识库',
      level: '中',
      levelClass: 'is-mid',
      value: formatNumber(dashboardStats.value.failed_document_count),
      time: '实时',
    },
  ];
});

const footerSources = computed(() => [
  '知识库文档',
  '风险提取结果',
  'RAG 检索日志',
  '系统审计记录',
].join('、'));

const isRetryableAudit = (item) => (
  item?.status === 'failed'
  && ['risk.extract', 'risk.batch_extract'].includes(item?.action)
  && String(item?.target_id || '').trim() !== ''
);

const retryAuditAction = async (item) => {
  if (!isRetryableAudit(item)) {
    return;
  }

  try {
    if (item.action === 'risk.extract') {
      await riskApi.retryExtractDocument(item.target_id);
    } else {
      const documentIds = String(item.target_id)
        .split(',')
        .map((value) => Number.parseInt(value.trim(), 10))
        .filter((value) => Number.isInteger(value) && value > 0);
      await riskApi.retryBatchExtract(documentIds);
    }

    ElMessage.success('已重新触发风险提取任务。');
    await fetchData();
  } catch (error) {
    console.error('Failed to retry risk audit action:', error);
    ElMessage.error(error?.message || '重新触发失败，请稍后重试。');
  }
};
</script>

<template>
  <section class="ops-board" v-loading="isLoading">
    <div class="ops-board__actions">
      <button type="button" class="ops-board__search" @click="router.push('/workspace/knowledge')">
        <AppIcon name="search" />
        <span>搜索文档、研报、公司、关键词...</span>
      </button>
      <button type="button" class="ops-board__chip">{{ refreshedAt || '等待刷新' }}</button>
      <button type="button" class="ops-board__chip is-primary" @click="fetchData">
        <AppIcon name="refresh" />
        刷新
      </button>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="ops-board__summary">
      <article
        v-for="metric in summaryMetrics"
        :key="metric.key"
        class="summary-tile"
        :class="`is-${metric.tone}`"
      >
        <span class="summary-tile__icon">
          <AppIcon :name="metric.icon" />
        </span>
        <div>
          <span class="summary-tile__label">{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <p>{{ metric.note }} <em>{{ metric.delta }}</em></p>
        </div>
      </article>
    </section>

    <section class="ops-board__grid">
      <article class="board-panel board-panel--trend">
        <div class="board-panel__header">
          <div>
            <strong>风险趋势分析</strong>
            <span>近 7 天请求、命中与高风险预警</span>
          </div>
          <div class="board-tabs">
            <span class="is-active">近7天</span>
            <span>近30天</span>
            <span>近90天</span>
          </div>
        </div>
        <AdminChart :option="trendOption" height="318px" />
      </article>

      <article class="board-panel board-panel--industry">
        <div class="board-panel__header">
          <div>
            <strong>行业风险分布</strong>
            <span>预留维度，按当前风险样本估算</span>
          </div>
        </div>
        <div class="donut-wrap">
          <AdminChart :option="industryOption" height="282px" />
          <div class="donut-center donut-center--industry">
            <strong>{{ formatNumber(dashboardStats.risk_event_count) }}</strong>
            <span>风险信息总数</span>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--map">
        <div class="board-panel__header">
          <div>
            <strong>区域风险热力图</strong>
            <span>区域覆盖为未来地理数据预留</span>
          </div>
          <div class="map-tabs">
            <span class="is-active">中国</span>
            <span>全球</span>
          </div>
        </div>
        <div class="region-map">
          <div class="region-map__shape">
            <span
              v-for="tile in regionTiles"
              :key="tile.label"
              class="region-map__tile"
              :style="tile.style"
              :title="`${tile.label}: ${formatNumber(tile.value)}`"
            />
          </div>
          <div class="region-map__legend">
            <div v-for="row in regionRows" :key="row.label">
              <span :style="{ background: row.color }" />
              <b>{{ row.label }}</b>
              <em>{{ formatNumber(row.value) }}</em>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--level">
        <div class="board-panel__header">
          <div>
            <strong>风险等级分布</strong>
            <span>来自后端风险事件等级聚合</span>
          </div>
        </div>
        <div class="risk-level-layout">
          <div class="donut-wrap">
            <AdminChart :option="riskLevelOption" height="248px" />
            <div class="donut-center donut-center--level">
              <strong>{{ formatNumber(dashboardStats.risk_event_count) }}</strong>
              <span>风险信息总数</span>
            </div>
          </div>
          <div class="risk-level-legend">
            <div v-for="row in riskLevelRows" :key="row.label">
              <span :style="{ background: row.color }" />
              <b>{{ row.label }}</b>
              <em>{{ formatNumber(row.value) }}（{{ row.percent }}）</em>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--table">
        <div class="board-panel__header">
          <div>
            <strong>高风险事项 TOP10</strong>
            <span>风险活动、失败任务与关键审计合并排序</span>
          </div>
        </div>
        <div class="event-table-wrap">
          <table class="event-table">
            <thead>
              <tr>
                <th>事件标题</th>
                <th>涉及对象</th>
                <th>风险等级</th>
                <th>指标</th>
                <th>时间</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in topEvents" :key="row.id">
                <td>
                  <span class="event-rank">{{ index + 1 }}</span>
                  {{ row.title }}
                </td>
                <td>{{ row.company }}</td>
                <td><span class="risk-tag" :class="row.levelClass">{{ row.level }}</span></td>
                <td>{{ row.value }}</td>
                <td>{{ row.time }}</td>
                <td>
                  <button
                    v-if="isRetryableAudit(row.audit)"
                    type="button"
                    class="table-action"
                    @click="retryAuditAction(row.audit)"
                  >
                    重试
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="board-panel board-panel--source">
        <div class="board-panel__header">
          <div>
            <strong>数据来源分布</strong>
            <span>当前平台真实数据面来源</span>
          </div>
        </div>
        <div class="source-layout">
          <div class="donut-wrap">
            <AdminChart :option="sourceOption" height="248px" />
            <div class="donut-center donut-center--source">
              <strong>{{ formatNumber(dashboardStats.document_count + dashboardStats.risk_event_count) }}</strong>
              <span>核心样本量</span>
            </div>
          </div>
          <div class="source-legend">
            <div v-for="row in sourceRows" :key="row.label">
              <span :style="{ background: row.color }" />
              <b>{{ row.label }}</b>
              <em>{{ formatNumber(row.value) }}</em>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--process">
        <div class="board-panel__header">
          <div>
            <strong>数据处理统计</strong>
            <span>知识入库、检索和审计处理状态</span>
          </div>
        </div>
        <div class="process-grid">
          <div v-for="item in processStats" :key="item.label" class="process-item">
            <span><AppIcon :name="item.icon" /></span>
            <div>
              <b>{{ item.label }}</b>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--documents">
        <div class="board-panel__header">
          <div>
            <strong>文档处理状态</strong>
            <span>解析、切块、索引与失败状态</span>
          </div>
        </div>
        <AdminChart :option="documentOption" height="236px" />
      </article>
    </section>

    <footer class="ops-board__footer">
      <span>数据来源：{{ footerSources }}</span>
      <span>最后更新：{{ refreshedAt || '未更新' }}</span>
    </footer>
  </section>
</template>

<style scoped>
.ops-board {
  --board-bg: #050b16;
  --board-panel: rgba(11, 22, 43, 0.92);
  --board-panel-2: rgba(14, 27, 51, 0.92);
  --board-line: rgba(91, 132, 205, 0.2);
  --board-line-strong: rgba(91, 132, 205, 0.34);
  --board-text: #dbe7ff;
  --board-muted: #7f8da7;
  --board-blue: #2f74ff;
  --board-cyan: #2fd3d0;
  --board-red: #f04d5d;
  --board-orange: #f3a21b;
  --board-purple: #8758ff;
  --board-green: #19d59a;
  display: grid;
  gap: 14px;
  color: var(--board-text);
}

.ops-board__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.ops-board__search,
.ops-board__chip {
  height: 40px;
  border: 1px solid var(--board-line);
  border-radius: 8px;
  background: rgba(7, 17, 34, 0.88);
  color: #aebbd2;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.ops-board__search {
  flex: 1 1 340px;
  max-width: 440px;
  border-radius: 22px;
  justify-content: flex-start;
  color: #76859e;
}

.ops-board__chip.is-primary {
  border-color: rgba(64, 125, 255, 0.55);
  background: #164fbf;
  color: #fff;
  font-weight: 800;
}

.ops-board__summary {
  min-height: 118px;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  border: 1px solid var(--board-line);
  border-radius: 9px;
  background:
    linear-gradient(180deg, rgba(12, 27, 54, 0.92), rgba(7, 18, 36, 0.92));
  overflow: hidden;
}

.summary-tile {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 22px 18px;
  border-right: 1px solid rgba(91, 132, 205, 0.16);
}

.summary-tile:last-child {
  border-right: 0;
}

.summary-tile__icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
  background: rgba(47, 116, 255, 0.16);
  box-shadow: 0 0 22px rgba(47, 116, 255, 0.22);
}

.summary-tile__icon :deep(.app-icon) {
  width: 21px;
  height: 21px;
}

.summary-tile.is-blue { color: #5fa4ff; }
.summary-tile.is-red { color: #ff5265; }
.summary-tile.is-cyan { color: #52d7e9; }
.summary-tile.is-purple { color: #b16cff; }
.summary-tile.is-green { color: #28d59a; }
.summary-tile.is-orange { color: #ffad2f; }

.summary-tile__label {
  display: block;
  color: #91a0b8;
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 7px;
}

.summary-tile strong {
  display: block;
  color: currentColor;
  font-size: clamp(22px, 1.9vw, 29px);
  line-height: 1.05;
  font-weight: 900;
}

.summary-tile p {
  margin: 8px 0 0;
  color: #8391aa;
  font-size: 12px;
  font-weight: 700;
}

.summary-tile em {
  color: #19d59a;
  font-style: normal;
  margin-left: 6px;
}

.summary-tile.is-red em,
.summary-tile.is-orange em {
  color: #ff5265;
}

.ops-board__grid {
  display: grid;
  grid-template-columns: minmax(460px, 1.45fr) minmax(340px, 0.9fr) minmax(360px, 0.95fr);
  grid-auto-rows: minmax(220px, auto);
  gap: 10px;
}

.board-panel {
  min-width: 0;
  border: 1px solid var(--board-line);
  border-radius: 9px;
  background:
    linear-gradient(180deg, rgba(12, 27, 54, 0.92), rgba(7, 18, 36, 0.92));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.025),
    0 14px 30px rgba(0, 0, 0, 0.16);
  overflow: hidden;
}

.board-panel--trend {
  min-height: 374px;
}

.board-panel--table {
  grid-column: span 2;
}

.board-panel--process,
.board-panel--documents {
  min-height: 250px;
}

.board-panel__header {
  min-height: 48px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
}

.board-panel__header div:first-child {
  min-width: 0;
}

.board-panel__header strong {
  display: block;
  color: #edf4ff;
  font-size: 16px;
  font-weight: 900;
}

.board-panel__header span {
  display: block;
  margin-top: 3px;
  color: #7f8da7;
  font-size: 12px;
  font-weight: 700;
}

.board-tabs,
.map-tabs {
  display: flex;
  gap: 7px;
  padding: 3px;
  border-radius: 8px;
  border: 1px solid rgba(91, 132, 205, 0.15);
  background: rgba(8, 17, 35, 0.5);
}

.board-tabs span,
.map-tabs span {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 0 11px;
  border-radius: 6px;
  color: #8190a8;
  font-size: 12px;
  font-weight: 800;
}

.board-tabs .is-active,
.map-tabs .is-active {
  color: #fff;
  background: #164fbf;
}

.donut-wrap {
  position: relative;
}

.donut-center {
  position: absolute;
  pointer-events: none;
  text-align: center;
  color: #edf4ff;
}

.donut-center strong {
  display: block;
  font-size: 22px;
  line-height: 1.1;
}

.donut-center span {
  display: block;
  margin-top: 4px;
  color: #a9b6ca;
  font-size: 12px;
  font-weight: 800;
}

.donut-center--industry {
  left: calc(34% - 54px);
  top: 116px;
  width: 108px;
}

.donut-center--level,
.donut-center--source {
  left: calc(35% - 52px);
  top: 102px;
  width: 104px;
}

.region-map {
  position: relative;
  height: 282px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 12px;
  padding: 0 16px 16px;
}

.region-map__shape {
  position: relative;
  min-height: 248px;
  border-radius: 32% 45% 36% 42%;
  background:
    radial-gradient(circle at 78% 22%, rgba(135, 88, 255, 0.34), transparent 20%),
    radial-gradient(circle at 56% 58%, rgba(47, 116, 255, 0.42), transparent 38%),
    radial-gradient(circle at 30% 42%, rgba(47, 211, 208, 0.18), transparent 32%),
    rgba(13, 31, 66, 0.46);
  border: 1px solid rgba(91, 132, 205, 0.18);
  clip-path: polygon(12% 35%, 25% 20%, 43% 16%, 52% 7%, 66% 17%, 83% 16%, 91% 32%, 84% 48%, 92% 62%, 74% 73%, 65% 88%, 48% 80%, 35% 91%, 22% 74%, 8% 65%);
}

.region-map__shape::after {
  content: "";
  position: absolute;
  inset: 18px;
  border: 1px dashed rgba(116, 150, 220, 0.24);
  border-radius: inherit;
}

.region-map__tile {
  position: absolute;
  left: var(--tile-x);
  top: var(--tile-y);
  width: 42px;
  height: 30px;
  border: 1px solid rgba(190, 214, 255, 0.3);
  background: var(--tile-color);
  box-shadow: 0 0 24px color-mix(in srgb, var(--tile-color) 44%, transparent);
  transform: translate(-50%, -50%) skew(-10deg);
  opacity: 0.9;
}

.region-map__legend,
.source-legend,
.risk-level-legend {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  min-width: 0;
  color: #a7b5cb;
  font-size: 12px;
  font-weight: 800;
}

.region-map__legend div,
.source-legend div,
.risk-level-legend div {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.region-map__legend span,
.source-legend span,
.risk-level-legend span {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.region-map__legend b,
.source-legend b,
.risk-level-legend b {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.region-map__legend em,
.source-legend em,
.risk-level-legend em {
  color: #dbe7ff;
  font-style: normal;
  white-space: nowrap;
}

.risk-level-layout,
.source-layout {
  display: grid;
  grid-template-columns: minmax(180px, 0.95fr) minmax(150px, 1fr);
  align-items: center;
  padding: 0 14px 14px;
}

.event-table-wrap {
  overflow-x: auto;
  padding: 0 12px 12px;
}

.event-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  color: #a7b5cb;
  font-size: 12px;
}

.event-table th {
  height: 34px;
  color: #74859f;
  font-weight: 800;
  text-align: left;
  background: rgba(11, 27, 52, 0.75);
  border-bottom: 1px solid rgba(91, 132, 205, 0.12);
}

.event-table td {
  height: 32px;
  max-width: 380px;
  border-bottom: 1px solid rgba(91, 132, 205, 0.08);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-rank {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  margin-right: 8px;
  border-radius: 4px;
  background: rgba(255, 82, 101, 0.15);
  color: #ff5265;
  font-size: 11px;
  font-weight: 900;
}

.risk-tag {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 22px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 900;
}

.risk-tag.is-high { color: #ff5265; background: rgba(255, 82, 101, 0.15); }
.risk-tag.is-mid { color: #f3a21b; background: rgba(243, 162, 27, 0.14); }
.risk-tag.is-low { color: #19d59a; background: rgba(25, 213, 154, 0.14); }

.table-action {
  border: 0;
  background: transparent;
  color: #5fa4ff;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.process-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 14px;
  padding: 8px 14px 16px;
}

.process-item {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.process-item > span {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(47, 116, 255, 0.15);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #5fa4ff;
  border: 1px solid rgba(95, 164, 255, 0.22);
}

.process-item b {
  display: block;
  color: #8897af;
  font-size: 12px;
  font-weight: 800;
}

.process-item strong {
  display: block;
  color: #5fa4ff;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 900;
}

.ops-board__footer {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  border: 1px solid var(--board-line);
  border-radius: 9px;
  background: rgba(7, 18, 36, 0.92);
  color: #718199;
  font-size: 13px;
}

@media (max-width: 1320px) {
  .ops-board__summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .summary-tile:nth-child(3n) {
    border-right: 0;
  }

  .ops-board__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .board-panel--table {
    grid-column: span 2;
  }
}

@media (max-width: 900px) {
  .ops-board__header,
  .ops-board__grid,
  .region-map,
  .risk-level-layout,
  .source-layout {
    grid-template-columns: 1fr;
  }

  .ops-board__summary {
    grid-template-columns: 1fr;
  }

  .summary-tile {
    border-right: 0;
    border-bottom: 1px solid rgba(91, 132, 205, 0.16);
  }

  .board-panel--table {
    grid-column: span 1;
  }

  .process-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-board__footer {
    align-items: flex-start;
    flex-direction: column;
    padding-block: 12px;
  }
}

@media (max-width: 560px) {
  .ops-board__actions,
  .board-panel__header {
    align-items: stretch;
    flex-direction: column;
  }

  .ops-board__search {
    flex-basis: auto;
  }

  .process-grid {
    grid-template-columns: 1fr;
  }
}
</style>
