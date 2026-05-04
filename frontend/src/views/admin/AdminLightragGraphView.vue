<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import LightragPanel from '../../components/lightrag/LightragPanel.vue';

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

const graphStats = computed(() => ([
  { label: '当前标签', value: form.label || '未选择' },
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
    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="lightrag-strip">
      <article v-for="item in graphStats" :key="item.label" class="lightrag-stat">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>

    <div class="lightrag-layout">
      <LightragPanel title="Labels" desc="先搜标签，再加载图谱；工作流尽量贴近 LightRAG 原生浏览页。">
        <div class="lightrag-label-stack">
          <div class="lightrag-search-bar">
            <el-input v-model="form.search" placeholder="按标签搜索" @keyup.enter="handleLabelSearch" />
            <el-button :loading="isSearching" @click="handleLabelSearch">搜索</el-button>
          </div>

          <section class="lightrag-label-group">
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
          </section>

          <section class="lightrag-label-group">
            <strong>全量标签</strong>
            <div class="lightrag-label-list">
              <button
                v-for="label in labels"
                :key="label"
                type="button"
                class="lightrag-label-item"
                @click="fetchGraph(label)"
              >
                {{ label }}
              </button>
              <div v-if="!labels.length" class="admin-empty-state">暂无可浏览标签</div>
            </div>
          </section>
        </div>
      </LightragPanel>

      <LightragPanel title="Graph request" desc="把标签、深度与节点上限收敛在一个工具栏里。">
        <template #header>
          <el-link href="/admin/lightrag/legacy" target="_blank" rel="noopener">Legacy WebUI</el-link>
        </template>

        <div class="lightrag-control-stack">
          <div class="lightrag-control-grid">
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

          <div class="lightrag-toolbar">
            <el-button type="primary" :loading="isSearching" @click="fetchGraph()">加载图谱</el-button>
            <p class="lightrag-note">如果没有标签，先在左侧点一个热门标签再加载。</p>
          </div>
        </div>
      </LightragPanel>
    </div>

    <div class="lightrag-detail-layout">
      <LightragPanel title="Nodes" desc="保留实体名、类型与原始属性，方便人工校验。">
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
      </LightragPanel>

      <LightragPanel title="Edges" desc="关系与 source / target 分开看，减少页面阅读噪音。">
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
      </LightragPanel>
    </div>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-label-stack,
.lightrag-control-stack,
.lightrag-detail-list {
  display: grid;
  gap: 16px;
}

.lightrag-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-stat,
.lightrag-detail-card,
.lightrag-label-item {
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.lightrag-stat {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
}

.lightrag-stat span,
.lightrag-field span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-stat strong {
  color: var(--text-primary);
  font-size: 1.2rem;
}

.lightrag-layout,
.lightrag-detail-layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.8fr) minmax(0, 1.2fr);
  gap: 18px;
}

.lightrag-search-bar,
.lightrag-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-label-group,
.lightrag-control-grid {
  display: grid;
  gap: 12px;
}

.lightrag-control-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.lightrag-chip-list,
.lightrag-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-chip,
.lightrag-label-item {
  padding: 8px 12px;
  color: var(--text-primary);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.lightrag-chip {
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--surface-3);
}

.lightrag-label-item {
  border: 1px solid var(--line-soft);
}

.lightrag-chip:hover,
.lightrag-label-item:hover {
  border-color: rgba(36, 87, 197, 0.24);
  color: var(--brand);
  background: var(--brand-soft);
}

.lightrag-field {
  display: grid;
  gap: 8px;
  min-width: 180px;
}

.lightrag-note,
.lightrag-detail-card p,
.lightrag-detail-card pre {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-detail-card {
  padding: 16px 18px;
}

.lightrag-detail-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.lightrag-detail-card__head strong,
.lightrag-label-group strong {
  color: var(--text-primary);
}

.lightrag-detail-card details {
  margin-top: 12px;
}

@media (max-width: 1180px) {
  .lightrag-layout,
  .lightrag-detail-layout,
  .lightrag-control-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .lightrag-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .lightrag-strip {
    grid-template-columns: 1fr;
  }
}
</style>
