<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';

const flash = useFlash();
const isLoading = ref(false);
const isSearching = ref(false);
const errorMsg = ref('');
const labels = ref([]);
const popularLabels = ref([]);
const graph = ref({ nodes: [], edges: [], isTruncated: false });

const form = reactive({
  label: '',
  search: '',
  maxDepth: 3,
  maxNodes: 80,
});

const graphSummary = computed(() => ([
  { label: '节点', value: graph.value.nodes.length },
  { label: '关系', value: graph.value.edges.length },
  { label: '截断', value: graph.value.isTruncated ? '是' : '否' },
]));

const loadLabels = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const [list, popular] = await Promise.all([
      lightragApi.getLabelList(),
      lightragApi.getPopularLabels(10),
    ]);
    labels.value = list;
    popularLabels.value = popular;
  } catch (error) {
    errorMsg.value = error.message || '加载图谱标签失败。';
  } finally {
    isLoading.value = false;
  }
};

const fetchGraph = async (label = form.label) => {
  if (!label) {
    flash.warning('请先选择一个标签。');
    return;
  }
  isSearching.value = true;
  errorMsg.value = '';
  try {
    form.label = label;
    graph.value = await lightragApi.getGraph(label, {
      maxDepth: form.maxDepth,
      maxNodes: form.maxNodes,
    });
  } catch (error) {
    errorMsg.value = error.message || '加载图谱失败。';
  } finally {
    isSearching.value = false;
  }
};

const handleLabelSearch = async () => {
  if (!form.search.trim()) {
    await loadLabels();
    return;
  }
  isSearching.value = true;
  errorMsg.value = '';
  try {
    labels.value = await lightragApi.searchLabels(form.search.trim(), 20);
  } catch (error) {
    errorMsg.value = error.message || '搜索标签失败。';
  } finally {
    isSearching.value = false;
  }
};

onMounted(loadLabels);
</script>

<template>
  <div class="page-stack lightrag-page">
    <section class="lightrag-hero">
      <div>
        <span class="lightrag-hero__eyebrow">Knowledge graph explorer</span>
        <h2 class="lightrag-hero__title">图谱浏览</h2>
        <p class="lightrag-hero__subtitle">
          先选标签，再把节点与关系拆开看，避免把复杂图谱探索压缩成一块不可控的嵌入画布。
        </p>
      </div>
      <div class="lightrag-summary">
        <article v-for="item in graphSummary" :key="item.label" class="lightrag-summary__item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard
      title="图谱取数"
      desc="以标签为入口控制图深度与节点上限，先看结构轮廓，再看节点和关系明细。"
      admin
    >
      <div class="lightrag-graph-grid">
        <aside class="lightrag-labels">
          <div class="lightrag-labels__toolbar">
            <el-input v-model="form.search" placeholder="按标签搜索" @keyup.enter="handleLabelSearch" />
            <el-button :loading="isSearching" @click="handleLabelSearch">搜索</el-button>
          </div>

          <div class="lightrag-labels__section">
            <strong>热门标签</strong>
            <div class="lightrag-chip-list">
              <button
                v-for="label in popularLabels"
                :key="label"
                type="button"
                class="lightrag-chip"
                @click="fetchGraph(label)"
              >
                {{ label }}
              </button>
            </div>
          </div>

          <div class="lightrag-labels__section">
            <strong>全量标签</strong>
            <div class="lightrag-label-list">
              <button
                v-for="label in labels"
                :key="label"
                type="button"
                class="lightrag-label-list__item"
                @click="fetchGraph(label)"
              >
                {{ label }}
              </button>
              <div v-if="!labels.length" class="admin-empty-state">暂无可浏览标签</div>
            </div>
          </div>
        </aside>

        <div class="lightrag-graph-controls">
          <div class="lightrag-graph-controls__inputs">
            <label class="lightrag-field">
              <span>当前标签</span>
              <el-input v-model="form.label" placeholder="例如：流动性风险" />
            </label>
            <label class="lightrag-field">
              <span>最大深度</span>
              <el-input-number v-model="form.maxDepth" :min="1" :max="6" />
            </label>
            <label class="lightrag-field">
              <span>最大节点数</span>
              <el-input-number v-model="form.maxNodes" :min="10" :max="300" :step="10" />
            </label>
          </div>

          <div class="lightrag-graph-controls__actions">
            <el-button type="primary" :loading="isSearching" @click="fetchGraph()">加载图谱</el-button>
            <el-link href="/admin/lightrag/legacy" target="_blank" rel="noopener">Legacy WebUI</el-link>
          </div>
        </div>
      </div>
    </AppSectionCard>

    <div class="lightrag-detail-grid">
      <AppSectionCard title="节点清单" desc="保留节点原始属性，优先展示实体名、类型与摘要。" admin>
        <div v-if="graph.nodes.length" class="lightrag-detail-list">
          <article v-for="node in graph.nodes" :key="node.id" class="lightrag-detail-card">
            <div class="lightrag-detail-card__head">
              <strong>{{ node.label }}</strong>
              <span>{{ node.type }}</span>
            </div>
            <p>{{ node.description || '当前节点没有返回描述。' }}</p>
            <details>
              <summary>原始数据</summary>
              <pre>{{ JSON.stringify(node.raw, null, 2) }}</pre>
            </details>
          </article>
        </div>
        <div v-else class="admin-empty-state">当前标签还没有可展示节点。</div>
      </AppSectionCard>

      <AppSectionCard title="关系清单" desc="把边信息独立展示，便于人工检查 source / target / relation 是否合理。" admin>
        <div v-if="graph.edges.length" class="lightrag-detail-list">
          <article v-for="edge in graph.edges" :key="edge.id" class="lightrag-detail-card">
            <div class="lightrag-detail-card__head">
              <strong>{{ edge.label }}</strong>
              <span>{{ edge.source }} → {{ edge.target }}</span>
            </div>
            <p>{{ edge.description || '当前关系没有返回额外描述。' }}</p>
            <details>
              <summary>原始数据</summary>
              <pre>{{ JSON.stringify(edge.raw, null, 2) }}</pre>
            </details>
          </article>
        </div>
        <div v-else class="admin-empty-state">当前标签还没有可展示关系。</div>
      </AppSectionCard>
    </div>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-labels,
.lightrag-labels__section,
.lightrag-detail-list {
  display: grid;
  gap: 16px;
}

.lightrag-hero,
.lightrag-summary__item,
.lightrag-labels,
.lightrag-detail-card {
  border: 1px solid var(--line-soft);
  border-radius: 24px;
  background: rgba(24, 34, 49, 0.92);
  box-shadow: var(--shadow-md);
}

.lightrag-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
  gap: 18px;
  padding: 24px 28px;
}

.lightrag-hero__eyebrow,
.lightrag-field span {
  color: rgba(141, 208, 208, 0.92);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.lightrag-hero__title {
  margin: 0;
  font-size: 32px;
  color: var(--text-primary);
}

.lightrag-hero__subtitle {
  margin: 12px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-summary__item {
  padding: 16px;
  display: grid;
  gap: 6px;
}

.lightrag-summary__item span {
  color: var(--text-muted);
}

.lightrag-summary__item strong {
  color: var(--text-primary);
  font-size: 24px;
}

.lightrag-graph-grid,
.lightrag-detail-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(0, 1.2fr);
  gap: 18px;
}

.lightrag-labels,
.lightrag-detail-card {
  padding: 18px;
}

.lightrag-labels__toolbar,
.lightrag-graph-controls__actions,
.lightrag-graph-controls__inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.lightrag-chip-list,
.lightrag-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-chip,
.lightrag-label-list__item {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(141, 208, 208, 0.16);
  background: rgba(15, 23, 34, 0.86);
  color: var(--text-primary);
  cursor: pointer;
}

.lightrag-graph-controls {
  display: grid;
  gap: 16px;
}

.lightrag-field {
  display: grid;
  gap: 8px;
  min-width: 180px;
}

.lightrag-detail-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.lightrag-detail-card p,
.lightrag-detail-card pre {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-detail-card details {
  margin-top: 12px;
}

@media (max-width: 1180px) {
  .lightrag-hero,
  .lightrag-graph-grid,
  .lightrag-detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .lightrag-summary {
    grid-template-columns: 1fr;
  }
}
</style>
