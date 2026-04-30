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

const usedStorageBytes = computed(() =>
  props.documents.reduce((sum, document) => sum + parseSizeToBytes(document.size), 0),
);

const storagePercent = computed(() => {
  if (usedStorageBytes.value <= 0) {
    return 0;
  }

  return Math.min(99, Math.max(1, Math.round((usedStorageBytes.value / storageCapacityBytes) * 100)));
});

const vectorTotal = computed(() =>
  props.documents.reduce((sum, document) => sum + Number(document.vectorCount || 0), 0),
);

const vectorCapacity = computed(() => Math.max(vectorTotal.value + 1, 1_000_000));

const vectorPercent = computed(() =>
  Math.min(100, Math.round((vectorTotal.value / vectorCapacity.value) * 100)),
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
    <section class="metric-panel">
      <header class="metric-panel__header">
        <h3>存储使用情况</h3>
        <span>500 GB</span>
      </header>
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
    </section>

    <section class="metric-panel">
      <header class="metric-panel__header">
        <h3>向量数据库</h3>
        <span>{{ vectorPercent }}%</span>
      </header>
      <div class="rail-progress">
        <span :style="{ width: `${vectorPercent}%` }"></span>
      </div>
      <p class="metric-note">
        {{ vectorTotal.toLocaleString('zh-CN') }} / {{ vectorCapacity.toLocaleString('zh-CN') }} vectors
      </p>
      <div class="metric-split">
        <span>{{ indexedCount }} 可检索</span>
        <span>{{ activeCount }} 处理中</span>
        <span>{{ failedCount }} 失败</span>
      </div>
    </section>

    <section class="metric-panel">
      <header class="metric-panel__header">
        <h3>数据源分布</h3>
        <span>{{ totalDocuments }} docs</span>
      </header>
      <div class="distribution-list">
        <div v-for="item in datasetDistribution" :key="item.label" class="distribution-row">
          <span>{{ item.label }}</span>
          <strong>{{ distributionTotal ? Math.round((item.value / distributionTotal) * 100) : 0 }}%</strong>
        </div>
        <p v-if="datasetDistribution.length === 0" class="metric-note">暂无数据源分布。</p>
      </div>
    </section>

    <section class="metric-panel">
      <header class="metric-panel__header">
        <h3>最近操作</h3>
        <span>当前筛选</span>
      </header>
      <div class="activity-list">
        <article
          v-for="activity in recentActivities"
          :key="activity.id"
          :class="['activity-item', `activity-item--${activity.tone}`]"
        >
          <span class="activity-item__mark"></span>
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
  gap: 14px;
  align-content: start;
}

.metric-panel {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
}

.metric-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.metric-panel h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

.metric-panel__header span,
.metric-note {
  color: var(--text-muted);
  font-size: 12px;
}

.donut {
  --percent: 0;
  width: 112px;
  height: 112px;
  display: grid;
  place-items: center;
  margin: 4px auto 16px;
  border-radius: 50%;
  background:
    radial-gradient(circle, var(--surface-2) 0 58%, transparent 59%),
    conic-gradient(var(--brand) calc(var(--percent) * 1%), rgba(33, 129, 92, 0.72) 0);
}

.donut strong,
.donut span {
  grid-area: 1 / 1;
}

.donut strong {
  color: var(--text-primary);
  font-size: 22px;
}

.donut span {
  margin-top: 40px;
  color: var(--text-muted);
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
  font-size: 12px;
}

.metric-list strong,
.distribution-row strong {
  color: var(--text-primary);
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
  background: linear-gradient(90deg, var(--brand), #9a78f4);
}

.metric-note {
  margin: 10px 0 0;
}

.metric-split {
  flex-wrap: wrap;
  justify-content: flex-start;
  margin-top: 12px;
}

.metric-split span {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--surface-3);
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
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-item span {
  color: var(--text-muted);
  font-size: 11px;
}
</style>
