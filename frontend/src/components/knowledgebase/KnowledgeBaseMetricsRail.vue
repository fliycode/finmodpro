<script setup>
import { computed } from 'vue';

const props = defineProps({
  documents: {
    type: Array,
    default: () => [],
  },
  datasets: {
    type: Array,
    default: () => [],
  },
  stats: {
    type: Object,
    default: () => null,
  },
  totalDocuments: {
    type: Number,
    default: 0,
  },
  activeCount: {
    type: Number,
    default: 0,
  },
  indexedCount: {
    type: Number,
    default: 0,
  },
  failedCount: {
    type: Number,
    default: 0,
  },
});

const parseSizeToBytes = (value) => {
  const match = String(value || '').match(/^([\d.]+)\s*(B|KB|MB|GB)$/i);
  if (!match) {
    return 0;
  }

  const multipliers = {
    B: 1,
    KB: 1024,
    MB: 1024 ** 2,
    GB: 1024 ** 3,
  };

  return Number(match[1]) * (multipliers[match[2].toUpperCase()] || 1);
};

const toNumber = (value, fallback = 0) => {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
};

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }

  if (bytes >= 1024 ** 3) {
    return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  }

  if (bytes >= 1024 ** 2) {
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  }

  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${Math.round(bytes)} B`;
};

const storageCapacityBytes = 500 * 1024 ** 3;

const usedStorageBytes = computed(() => {
  const total = toNumber(props.stats?.total_storage_bytes, -1);
  if (total >= 0) {
    return total;
  }

  return props.documents.reduce((sum, document) => sum + parseSizeToBytes(document.size), 0);
});

const storagePercent = computed(() => {
  if (usedStorageBytes.value <= 0) {
    return 0;
  }

  return Math.min(99, Math.max(1, Math.round((usedStorageBytes.value / storageCapacityBytes) * 100)));
});

const vectorTotal = computed(() => {
  const total = toNumber(props.stats?.total_vectors, -1);
  if (total >= 0) {
    return total;
  }

  return props.documents.reduce((sum, document) => sum + Number(document.vectorCount || 0), 0);
});

const vectorCapacity = computed(() => Math.max(vectorTotal.value + 1, 1_000_000));

const vectorPercent = computed(() =>
  Math.min(100, Math.round((vectorTotal.value / vectorCapacity.value) * 100)),
);

const indexedDocuments = computed(() => toNumber(props.stats?.indexed_count, props.indexedCount));
const processingDocuments = computed(() => toNumber(props.stats?.processing_count, props.activeCount));
const failedDocuments = computed(() => toNumber(props.stats?.failed_count, props.failedCount));
const normalizedTotalDocuments = computed(() =>
  toNumber(props.stats?.total_documents, props.totalDocuments || props.documents.length),
);

const datasetDistribution = computed(() => {
  const rows = props.datasets
    .map((dataset) => ({
      label: dataset.name || '未命名数据集',
      value: Number(dataset.documentCount || 0),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 5);

  if (rows.length > 0) {
    return rows;
  }

  const grouped = props.documents.reduce((bucket, document) => {
    const label = document.datasetName || '未分组';
    bucket[label] = (bucket[label] || 0) + 1;
    return bucket;
  }, {});

  return Object.entries(grouped)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 5);
});

const distributionTotal = computed(() =>
  datasetDistribution.value.reduce((sum, item) => sum + item.value, 0),
);

const recentActivities = computed(() =>
  props.documents
    .slice(0, 4)
    .map((document) => ({
      id: document.id,
      title: document.title,
      status: document.processStep?.label || '未开始',
      time: document.updateTime || document.uploadTime,
      tone: document.statusTone || 'neutral',
    })),
);
</script>

<template>
  <aside class="kb-metrics-rail" aria-label="管理员知识库指标">
    <section class="kb-metrics-rail__section">
      <header class="kb-metrics-rail__header">
        <div>
          <h3>存储占用</h3>
          <p>聚焦整体库容与剩余空间，避免新增文档时发生无感拥堵。</p>
        </div>
        <span>500 GB</span>
      </header>
      <div class="kb-metrics-rail__storage">
        <div class="donut" :style="{ '--percent': storagePercent }">
          <strong>{{ storagePercent }}%</strong>
          <span>已使用</span>
        </div>
        <div class="metric-list">
          <div>
            <span class="dot dot--blue"></span>
            <span>已使用</span>
            <strong>{{ formatBytes(usedStorageBytes) }}</strong>
          </div>
          <div>
            <span class="dot dot--green"></span>
            <span>可用空间</span>
            <strong>{{ formatBytes(storageCapacityBytes - usedStorageBytes) }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="kb-metrics-rail__section">
      <header class="kb-metrics-rail__header">
        <div>
          <h3>向量健康度</h3>
          <p>用总向量量级和处理分布判断当前入库链路的可用性。</p>
        </div>
        <span>{{ vectorPercent }}%</span>
      </header>
      <div class="rail-progress" aria-hidden="true">
        <span :style="{ width: `${vectorPercent}%` }"></span>
      </div>
      <p class="metric-note">
        {{ vectorTotal.toLocaleString('zh-CN') }} / {{ vectorCapacity.toLocaleString('zh-CN') }} vectors
      </p>
      <div class="metric-split">
        <span>{{ indexedDocuments }} 可检索</span>
        <span>{{ processingDocuments }} 处理中</span>
        <span>{{ failedDocuments }} 失败</span>
      </div>
    </section>

    <section class="kb-metrics-rail__section">
      <header class="kb-metrics-rail__header">
        <div>
          <h3>数据集分布</h3>
          <p>优先暴露文档量最大的知识域，便于发现单点堆积。</p>
        </div>
        <span>{{ normalizedTotalDocuments }} docs</span>
      </header>
      <div class="distribution-list">
        <div v-for="item in datasetDistribution" :key="item.label" class="distribution-row">
          <span>{{ item.label }}</span>
          <strong>{{ distributionTotal ? Math.round((item.value / distributionTotal) * 100) : 0 }}%</strong>
        </div>
        <p v-if="datasetDistribution.length === 0" class="metric-note">暂无数据源分布。</p>
      </div>
    </section>

    <section class="kb-metrics-rail__section">
      <header class="kb-metrics-rail__header">
        <div>
          <h3>最近操作</h3>
          <p>仅保留当前筛选范围内最值得继续追查的近期文档状态。</p>
        </div>
        <span>当前筛选</span>
      </header>
      <div class="activity-list">
        <article
          v-for="activity in recentActivities"
          :key="activity.id"
          :class="['activity-item', `activity-item--${activity.tone}`]"
        >
          <span class="activity-item__mark" aria-hidden="true"></span>
          <div>
            <strong>{{ activity.status }}：{{ activity.title }}</strong>
            <span>{{ activity.time }}</span>
          </div>
        </article>
        <p v-if="recentActivities.length === 0" class="metric-note">暂无最近操作。</p>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.kb-metrics-rail {
  display: grid;
  gap: 20px;
  align-content: start;
}

.kb-metrics-rail__section {
  display: grid;
  gap: 14px;
}

.kb-metrics-rail__section + .kb-metrics-rail__section {
  padding-top: 18px;
  border-top: 1px solid var(--line-soft);
}

.kb-metrics-rail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.kb-metrics-rail__header h3 {
  margin: 0;
  color: var(--text-primary);
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1rem;
  font-weight: 600;
}

.kb-metrics-rail__header p,
.kb-metrics-rail__header span,
.metric-note {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  line-height: 1.6;
}

.kb-metrics-rail__header > span {
  margin: 0;
  white-space: nowrap;
}

.kb-metrics-rail__storage {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.donut {
  --percent: 0;
  width: 92px;
  height: 92px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background:
    radial-gradient(circle, var(--surface-2) 0 58%, transparent 59%),
    conic-gradient(var(--brand) calc(var(--percent) * 1%), rgba(31, 122, 100, 0.74) 0);
}

.donut strong,
.donut span {
  grid-area: 1 / 1;
}

.donut strong {
  color: var(--text-primary);
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.donut span {
  margin-top: 32px;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
}

.metric-list,
.distribution-list,
.activity-list {
  display: grid;
  gap: 10px;
}

.metric-list div,
.distribution-row,
.metric-split {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
}

.metric-list strong,
.distribution-row strong {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot--blue {
  background: var(--brand);
}

.dot--green {
  background: var(--success);
}

.rail-progress {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-3);
}

.rail-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--brand), rgba(36, 87, 197, 0.34));
}

.metric-note {
  margin: 0;
}

.metric-split {
  flex-wrap: wrap;
  justify-content: flex-start;
}

.metric-split span {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--surface-3);
  font-size: 11px;
  font-weight: 500;
}

.activity-item {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 10px;
}

.activity-item__mark {
  width: 20px;
  height: 20px;
  margin-top: 2px;
  border-radius: 50%;
  background: var(--brand-soft);
  box-shadow: inset 0 0 0 5px var(--brand);
}

.activity-item--success .activity-item__mark {
  background: var(--success-50);
  box-shadow: inset 0 0 0 5px var(--success);
}

.activity-item--danger .activity-item__mark {
  background: var(--risk-50);
  box-shadow: inset 0 0 0 5px var(--risk);
}

.activity-item strong {
  display: block;
  overflow: hidden;
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-item span {
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
}

@media (max-width: 720px) {
  .kb-metrics-rail__storage {
    grid-template-columns: 1fr;
  }

  .donut {
    margin: 0 auto;
  }
}
</style>
