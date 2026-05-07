<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import LightragGraphCanvas from '../../components/lightrag/LightragGraphCanvas.vue';
import LightragWorkspaceShell from '../../components/lightrag/LightragWorkspaceShell.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import {
  buildLightragGraphFacets,
  filterLightragGraph,
  searchLightragGraphNodes,
} from '../../lib/lightrag-workspace.js';
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
const isLoading = ref(false);
const isSearching = ref(false);
const errorMsg = ref('');
const labels = ref([]);
const popularLabels = ref([]);
const graph = ref({ nodes: [], edges: [], isTruncated: false });
const lastLoadedAt = ref('');
const activeNodeTypes = ref([]);
const activeRelationLabels = ref([]);
const selectedNodeId = ref('');
const selectedEdgeId = ref('');

const form = reactive({
  label: '',
  labelSearch: '',
  nodeSearch: '',
  maxDepth: 3,
  maxNodes: 80,
});

const graphFacets = computed(() => buildLightragGraphFacets(graph.value.nodes, graph.value.edges));
const filteredGraph = computed(() => filterLightragGraph(graph.value, {
  activeNodeTypes: activeNodeTypes.value,
  activeRelationLabels: activeRelationLabels.value,
}));
const matchedNodeIds = computed(() => searchLightragGraphNodes(filteredGraph.value.nodes, form.nodeSearch));
const selectedNode = computed(() => filteredGraph.value.nodes.find((node) => node.id === selectedNodeId.value) || null);
const selectedEdge = computed(() => filteredGraph.value.edges.find((edge) => edge.id === selectedEdgeId.value) || null);
const selectedNodeRelations = computed(() => {
  if (!selectedNode.value) {
    return [];
  }
  return filteredGraph.value.edges.filter((edge) => edge.source === selectedNode.value.id || edge.target === selectedNode.value.id);
});
const graphStats = computed(() => ([
  { label: '当前标签', value: form.label || '未选择' },
  { label: '可见节点', value: filteredGraph.value.nodes.length },
  { label: '可见关系', value: filteredGraph.value.edges.length },
  { label: '截断', value: graph.value.isTruncated ? '是' : '否' },
]));

watch(graphFacets, (facets) => {
  activeNodeTypes.value = facets.nodeTypes.map((item) => item.label);
  activeRelationLabels.value = facets.relationLabels.map((item) => item.label);
}, { deep: true });

watch(filteredGraph, (nextGraph) => {
  if (!nextGraph.nodes.some((node) => node.id === selectedNodeId.value)) {
    selectedNodeId.value = '';
  }
  if (!nextGraph.edges.some((edge) => edge.id === selectedEdgeId.value)) {
    selectedEdgeId.value = '';
  }
}, { deep: true });

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
    selectedNodeId.value = graph.value.nodes[0]?.id || '';
    selectedEdgeId.value = '';
    lastLoadedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载图谱失败。';
  } finally {
    isSearching.value = false;
  }
};

const handleLabelSearch = async () => {
  if (!form.labelSearch.trim()) {
    await loadLabels();
    return;
  }
  isSearching.value = true;
  errorMsg.value = '';
  try {
    labels.value = await lightragApi.searchLabels(form.labelSearch.trim(), 20);
  } catch (error) {
    errorMsg.value = error.message || '搜索标签失败。';
  } finally {
    isSearching.value = false;
  }
};

const toggleFilter = (collectionRef, value) => {
  const set = new Set(collectionRef.value);
  if (set.has(value)) {
    set.delete(value);
  } else {
    set.add(value);
  }
  collectionRef.value = [...set];
};

const focusFirstMatch = () => {
  if (!matchedNodeIds.value.length) {
    flash.warning('当前画布里没有匹配的节点。');
    return;
  }
  selectedNodeId.value = matchedNodeIds.value[0];
  selectedEdgeId.value = '';
};

const clearSelection = () => {
  selectedNodeId.value = '';
  selectedEdgeId.value = '';
};

const resetFilters = () => {
  activeNodeTypes.value = graphFacets.value.nodeTypes.map((item) => item.label);
  activeRelationLabels.value = graphFacets.value.relationLabels.map((item) => item.label);
  form.nodeSearch = '';
};

const selectNode = (nodeId) => {
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = '';
};

const selectEdge = (edgeId) => {
  selectedEdgeId.value = edgeId;
  selectedNodeId.value = '';
};

onMounted(loadLabels);
</script>

<template>
  <LightragWorkspaceShell :status-items="graphStats">
    <template #aside>
      <span>最近载入：{{ lastLoadedAt || '尚未载入图谱' }}</span>
      <a href="/admin/lightrag/legacy" target="_blank" rel="noopener">打开 Legacy WebUI</a>
    </template>
    <template #actions>
      <el-button :loading="isLoading" @click="loadLabels">刷新标签</el-button>
    </template>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <div class="lightrag-graph">
      <div class="lightrag-graph__sidebar">
        <AppSectionCard title="图谱范围" desc="先选标签，再控制深度和节点上限。" admin>
          <div class="lightrag-graph__sidebar-stack">
            <div class="lightrag-graph__search-row">
              <el-input
                v-model="form.labelSearch"
                placeholder="按标签搜索"
                @keyup.enter="handleLabelSearch"
              />
              <el-button :loading="isSearching" @click="handleLabelSearch">搜索</el-button>
            </div>

            <div class="lightrag-graph__field-grid">
              <label class="lightrag-graph__field">
                <span>当前标签</span>
                <el-input v-model="form.label" placeholder="例如：流动性风险" />
              </label>
              <label class="lightrag-graph__field">
                <span>最大深度</span>
                <el-input-number v-model="form.maxDepth" :min="1" :max="6" />
              </label>
              <label class="lightrag-graph__field">
                <span>最大节点数</span>
                <el-input-number v-model="form.maxNodes" :min="10" :max="300" :step="10" />
              </label>
            </div>

            <div class="lightrag-graph__actions">
              <el-button type="primary" :loading="isSearching" @click="fetchGraph()">加载图谱</el-button>
            </div>

            <section class="lightrag-graph__facet-group">
              <strong>热门标签</strong>
              <div class="lightrag-graph__chip-list">
                <button
                  v-for="label in popularLabels"
                  :key="label"
                  type="button"
                  class="lightrag-graph__chip"
                  @click="fetchGraph(label)"
                >
                  {{ label }}
                </button>
              </div>
            </section>

            <section class="lightrag-graph__facet-group">
              <strong>可选标签</strong>
              <div class="lightrag-graph__label-list">
                <button
                  v-for="label in labels"
                  :key="label"
                  type="button"
                  :class="['lightrag-graph__label-item', { 'lightrag-graph__label-item--active': form.label === label }]"
                  @click="form.label = label"
                >
                  {{ label }}
                </button>
                <div v-if="!labels.length" class="admin-empty-state">暂无可浏览标签。</div>
              </div>
            </section>
          </div>
        </AppSectionCard>

        <AppSectionCard title="画布筛选" desc="筛掉不关心的类型，只保留当前需要看的结构。" admin>
          <div class="lightrag-graph__sidebar-stack">
            <div class="lightrag-graph__search-row">
              <el-input
                v-model="form.nodeSearch"
                placeholder="高亮节点名称、类型或描述"
                @keyup.enter="focusFirstMatch"
              />
              <el-button @click="focusFirstMatch">定位</el-button>
            </div>

            <section class="lightrag-graph__facet-group">
              <div class="lightrag-graph__facet-head">
                <strong>实体类型</strong>
                <button type="button" class="lightrag-graph__text-button" @click="resetFilters">重置</button>
              </div>
              <div class="lightrag-graph__chip-list">
                <button
                  v-for="item in graphFacets.nodeTypes"
                  :key="item.label"
                  type="button"
                  :class="['lightrag-graph__chip', { 'lightrag-graph__chip--active': activeNodeTypes.includes(item.label) }]"
                  @click="toggleFilter(activeNodeTypes, item.label)"
                >
                  {{ item.label }} · {{ item.count }}
                </button>
              </div>
            </section>

            <section class="lightrag-graph__facet-group">
              <strong>关系类型</strong>
              <div class="lightrag-graph__chip-list">
                <button
                  v-for="item in graphFacets.relationLabels"
                  :key="item.label"
                  type="button"
                  :class="['lightrag-graph__chip', { 'lightrag-graph__chip--active': activeRelationLabels.includes(item.label) }]"
                  @click="toggleFilter(activeRelationLabels, item.label)"
                >
                  {{ item.label }} · {{ item.count }}
                </button>
              </div>
            </section>
          </div>
        </AppSectionCard>
      </div>

      <AppSectionCard class="lightrag-graph__canvas-card" title="图谱画布" desc="拖拽、缩放和选中节点，结构会比列表更先暴露问题。" admin>
        <template #header>
          <div class="lightrag-graph__canvas-actions">
            <span v-if="form.nodeSearch.trim()" class="lightrag-graph__match-note">
              匹配 {{ matchedNodeIds.length }} 个节点
            </span>
            <el-button text @click="clearSelection">清除选中</el-button>
          </div>
        </template>

        <div v-if="filteredGraph.nodes.length" class="lightrag-graph__canvas">
          <LightragGraphCanvas
            :nodes="filteredGraph.nodes"
            :edges="filteredGraph.edges"
            :selected-node-id="selectedNodeId"
            :selected-edge-id="selectedEdgeId"
            :highlight-node-ids="matchedNodeIds"
            @select-node="selectNode"
            @select-edge="selectEdge"
          />
        </div>
        <div v-else class="admin-empty-state">
          先加载一个标签，或者检查筛选条件是否把当前画布全部隐藏了。
        </div>
      </AppSectionCard>

      <AppSectionCard title="检查器" desc="点一个节点或关系，再决定是否继续查原始返回。" admin>
        <div v-if="selectedNode" class="lightrag-graph__inspector">
          <div class="lightrag-graph__inspector-head">
            <strong>{{ selectedNode.label }}</strong>
            <span>{{ selectedNode.type }}</span>
          </div>
          <p>{{ selectedNode.description || '当前节点没有返回描述。' }}</p>

          <section class="lightrag-graph__facet-group">
            <strong>关联关系</strong>
            <div class="lightrag-graph__relation-list">
              <button
                v-for="edge in selectedNodeRelations"
                :key="edge.id"
                type="button"
                class="lightrag-graph__relation-item"
                @click="selectEdge(edge.id)"
              >
                <span>{{ edge.label }}</span>
                <strong>{{ edge.source === selectedNode.id ? edge.target : edge.source }}</strong>
              </button>
            </div>
          </section>

          <details>
            <summary>原始数据</summary>
            <pre>{{ JSON.stringify(selectedNode.raw, null, 2) }}</pre>
          </details>
        </div>

        <div v-else-if="selectedEdge" class="lightrag-graph__inspector">
          <div class="lightrag-graph__inspector-head">
            <strong>{{ selectedEdge.label }}</strong>
            <span>{{ selectedEdge.source }} → {{ selectedEdge.target }}</span>
          </div>
          <p>{{ selectedEdge.description || '当前关系没有返回额外描述。' }}</p>

          <details>
            <summary>原始数据</summary>
            <pre>{{ JSON.stringify(selectedEdge.raw, null, 2) }}</pre>
          </details>
        </div>

        <div v-else class="admin-empty-state">
          先在画布里选中一个节点或关系，这里再展开对应细节。
        </div>
      </AppSectionCard>
    </div>
  </LightragWorkspaceShell>
</template>

<style scoped>
.lightrag-graph,
.lightrag-graph__sidebar,
.lightrag-graph__sidebar-stack,
.lightrag-graph__field-grid,
.lightrag-graph__inspector,
.lightrag-graph__relation-list {
  display: grid;
  gap: 16px;
}

.lightrag-graph {
  display: grid;
  grid-template-columns: minmax(280px, 0.88fr) minmax(0, 1.45fr) minmax(300px, 0.9fr);
  gap: 18px;
}

.lightrag-graph__search-row,
.lightrag-graph__actions,
.lightrag-graph__facet-head,
.lightrag-graph__canvas-actions,
.lightrag-graph__inspector-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-graph__facet-head,
.lightrag-graph__inspector-head {
  justify-content: space-between;
}

.lightrag-graph__field {
  display: grid;
  gap: 8px;
}

.lightrag-graph__field span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-graph__facet-group {
  display: grid;
  gap: 10px;
}

.lightrag-graph__facet-group strong,
.lightrag-graph__inspector-head strong {
  color: var(--text-primary);
}

.lightrag-graph__chip-list,
.lightrag-graph__label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-graph__chip,
.lightrag-graph__label-item,
.lightrag-graph__relation-item {
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.lightrag-graph__chip,
.lightrag-graph__label-item {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
}

.lightrag-graph__chip:hover,
.lightrag-graph__chip--active,
.lightrag-graph__label-item:hover,
.lightrag-graph__label-item--active,
.lightrag-graph__relation-item:hover {
  border-color: rgba(36, 87, 197, 0.24);
  background: var(--brand-soft);
  color: var(--brand);
}

.lightrag-graph__canvas-card {
  min-width: 0;
}

.lightrag-graph__canvas {
  border: 1px solid var(--line-soft);
  border-radius: 22px;
  background:
    radial-gradient(circle at top, rgba(36, 87, 197, 0.08), transparent 42%),
    #111822;
}

.lightrag-graph__match-note {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.lightrag-graph__text-button {
  border: none;
  padding: 0;
  background: none;
  color: var(--brand);
  cursor: pointer;
}

.lightrag-graph__relation-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 16px;
  text-align: left;
}

.lightrag-graph__relation-item strong {
  color: inherit;
}

.lightrag-graph__inspector p,
.lightrag-graph__inspector pre {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 1360px) {
  .lightrag-graph {
    grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
  }

  .lightrag-graph__canvas-card {
    grid-column: span 1;
  }
}

@media (max-width: 1120px) {
  .lightrag-graph {
    grid-template-columns: 1fr;
  }
}
</style>
