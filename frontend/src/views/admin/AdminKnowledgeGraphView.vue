<script setup>
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import {
  buildLightragGraphFacets,
  buildLightragGraphNeighbors,
  filterLightragGraph,
  filterLightragGraphLabels,
  findLightragGraphMatches,
} from '../../lib/lightrag-workspace.js';
import { useFlash } from '../../lib/flash.js';

const LightragGraphCanvas = defineAsyncComponent(() => import('../../components/lightrag/LightragGraphCanvas.vue'));

const flash = useFlash();
const isLoading = ref(false);
const isSearching = ref(false);
const errorMsg = ref('');
const labels = ref([]);
const graph = ref({ nodes: [], edges: [], isTruncated: false });
const activeNodeTypes = ref([]);
const activeRelationLabels = ref([]);
const selectedNodeId = ref('');
const selectedEdgeId = ref('');

const form = reactive({
  label: '',
  labelQuery: '',
  nodeSearch: '',
  maxDepth: 3,
  maxNodes: 120,
});

const graphFacets = computed(() => buildLightragGraphFacets(graph.value.nodes, graph.value.edges));
const filteredGraph = computed(() => filterLightragGraph(graph.value, {
  activeNodeTypes: activeNodeTypes.value,
  activeRelationLabels: activeRelationLabels.value,
}));
const filteredLabels = computed(() => filterLightragGraphLabels(labels.value, form.labelQuery));
const matchedNodes = computed(() => findLightragGraphMatches(graph.value.nodes, form.nodeSearch, 12));
const matchedNodeIds = computed(() => matchedNodes.value.map((node) => node.id));
const visibleNodeIds = computed(() => new Set(filteredGraph.value.nodes.map((node) => node.id)));
const visibleMatchedNodeIds = computed(() => matchedNodeIds.value.filter((nodeId) => visibleNodeIds.value.has(nodeId)));
const hasGraphData = computed(() => graph.value.nodes.length > 0 || graph.value.edges.length > 0);
const hasVisibleGraph = computed(() => filteredGraph.value.nodes.length > 0);
const selectedNode = computed(() => graph.value.nodes.find((node) => node.id === selectedNodeId.value) || null);
const selectedEdge = computed(() => graph.value.edges.find((edge) => edge.id === selectedEdgeId.value) || null);
const selectedNodeNeighbors = computed(() => buildLightragGraphNeighbors(graph.value, selectedNodeId.value, 8));
const formatGraphMetaValue = (value) => {
  if (value === undefined || value === null || value === '') {
    return '';
  }

  if (typeof value === 'number' && Number.isFinite(value) && value > 1000000000) {
    return new Date(value * 1000).toLocaleString('zh-CN', { hour12: false });
  }

  return String(value);
};
const buildMetaRows = (properties = {}) => [
  ['来源文件', properties.file_path],
  ['来源块', properties.source_id],
  ['关键词', properties.keywords],
  ['创建时间', properties.created_at],
]
  .map(([label, value]) => ({ label, value: formatGraphMetaValue(value) }))
  .filter((item) => item.value);
const selectedNodeMetaRows = computed(() => buildMetaRows(selectedNode.value?.properties));
const selectedEdgeMetaRows = computed(() => buildMetaRows(selectedEdge.value?.properties));
const activeFacetSummary = computed(() => ({
  nodeTypeCount: activeNodeTypes.value.length,
  relationLabelCount: activeRelationLabels.value.length,
}));
const searchSummary = computed(() => {
  if (!form.nodeSearch.trim()) {
    return hasGraphData.value
      ? '输入节点名称、类型或描述，结果会直接列在右侧。'
      : '左侧标签载入后，可以在这里定位节点。';
  }

  if (!matchedNodes.value.length) {
    return '没有匹配项，可以换一个关键词，或者先切换左侧标签。';
  }

  const hiddenCount = matchedNodes.value.length - visibleMatchedNodeIds.value.length;
  if (hiddenCount > 0) {
    return `找到 ${matchedNodes.value.length} 个匹配项，其中 ${hiddenCount} 个被当前筛选隐藏。点击结果时会自动恢复筛选。`;
  }
  return `找到 ${matchedNodes.value.length} 个匹配项。按 Enter 会直接定位到第一个结果。`;
});

const resetFacetFilters = (facets = graphFacets.value) => {
  activeNodeTypes.value = facets.nodeTypes.map((item) => item.label);
  activeRelationLabels.value = facets.relationLabels.map((item) => item.label);
};

const clearSelection = () => {
  selectedNodeId.value = '';
  selectedEdgeId.value = '';
};

watch(graphFacets, (facets) => {
  resetFacetFilters(facets);
}, { deep: true });

watch(filteredGraph, (nextGraph) => {
  if (!nextGraph.nodes.some((node) => node.id === selectedNodeId.value)) {
    selectedNodeId.value = '';
  }
  if (!nextGraph.edges.some((edge) => edge.id === selectedEdgeId.value)) {
    selectedEdgeId.value = '';
  }
}, { deep: true });

const fetchGraph = async (label = form.label, options = {}) => {
  if (!label) {
    if (!options.suppressEmptyWarning) {
      flash.warning('当前还没有可加载的图谱标签。');
    }
    graph.value = { nodes: [], edges: [], isTruncated: false };
    clearSelection();
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
  } catch (error) {
    errorMsg.value = error.message || '加载图谱失败。';
  } finally {
    isSearching.value = false;
  }
};

const loadLabels = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    labels.value = await lightragApi.getLabelList();
    if (!labels.value.length) {
      form.label = '';
      graph.value = { nodes: [], edges: [], isTruncated: false };
      clearSelection();
      return;
    }

    const nextLabel = labels.value.includes(form.label) ? form.label : labels.value[0];
    await fetchGraph(nextLabel, { suppressEmptyWarning: true });
  } catch (error) {
    errorMsg.value = error.message || '加载标签失败。';
  } finally {
    isLoading.value = false;
  }
};

const selectLabel = async (label) => {
  if (!label || (label === form.label && hasGraphData.value)) {
    return;
  }
  await fetchGraph(label, { suppressEmptyWarning: true });
};

const focusNode = (nodeId, options = {}) => {
  if (!nodeId) {
    return;
  }
  if (options.resetFilters) {
    resetFacetFilters();
  }
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = '';
};

const handleNodeSearch = () => {
  if (!form.nodeSearch.trim()) {
    flash.warning('请输入关键词后再定位节点。');
    return;
  }
  if (!matchedNodes.value.length) {
    flash.warning('当前图谱里没有找到匹配节点。');
    return;
  }
  focusNode(matchedNodes.value[0].id, { resetFilters: true });
};

const selectNode = (nodeId) => {
  focusNode(nodeId);
};

const selectEdge = (edgeId) => {
  selectedEdgeId.value = edgeId;
  selectedNodeId.value = '';
};

const toggleFilter = (collectionRef, value) => {
  const next = new Set(collectionRef.value);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  collectionRef.value = [...next];
};

const clearSearch = () => {
  form.nodeSearch = '';
};

const resetView = () => {
  clearSearch();
  resetFacetFilters();
  selectedNodeId.value = graph.value.nodes[0]?.id || '';
  selectedEdgeId.value = '';
};

onMounted(() => {
  void loadLabels();
});
</script>

<template>
  <div class="knowledge-graph">
    <header class="knowledge-graph__hero">
      <div class="knowledge-graph__hero-copy">
        <p class="knowledge-graph__eyebrow">Graph Explorer</p>
        <h2>知识图谱总览</h2>
        <p>默认直接载入图谱，左侧切换标签，中间看全图，右侧查看搜索结果和节点详情。</p>
      </div>
      <div class="knowledge-graph__hero-meta">
        <span class="knowledge-graph__meta-pill">标签 {{ labels.length }}</span>
        <span class="knowledge-graph__meta-pill">节点 {{ graph.nodes.length }}</span>
        <span class="knowledge-graph__meta-pill">关系 {{ graph.edges.length }}</span>
        <span v-if="form.label" class="knowledge-graph__meta-pill knowledge-graph__meta-pill--active">当前 {{ form.label }}</span>
        <el-button :loading="isLoading" @click="loadLabels">刷新标签</el-button>
        <el-button :loading="isSearching" type="primary" @click="fetchGraph()">更新图谱</el-button>
      </div>
    </header>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <div class="knowledge-graph__workspace">
      <aside class="knowledge-graph__rail">
        <section class="knowledge-graph__pane knowledge-graph__pane--compact">
          <div class="knowledge-graph__pane-head">
            <div>
              <p class="knowledge-graph__pane-kicker">标签总览</p>
              <h3>直接切换标签</h3>
            </div>
            <span class="knowledge-graph__pane-count">{{ filteredLabels.length }} / {{ labels.length }}</span>
          </div>

          <el-input
            v-model="form.labelQuery"
            clearable
            placeholder="筛选标签"
          />

          <div v-if="filteredLabels.length" class="knowledge-graph__label-list">
            <button
              v-for="label in filteredLabels"
              :key="label"
              type="button"
              :class="['knowledge-graph__label-item', { 'knowledge-graph__label-item--active': form.label === label }]"
              @click="selectLabel(label)"
            >
              <span class="knowledge-graph__label-dot" />
              <span>{{ label }}</span>
            </button>
          </div>
          <p v-else class="knowledge-graph__muted-copy">没有匹配标签，换个关键词试试。</p>
        </section>

        <section class="knowledge-graph__pane">
          <div class="knowledge-graph__pane-head">
            <div>
              <p class="knowledge-graph__pane-kicker">视图控制</p>
              <h3>范围与筛选</h3>
            </div>
          </div>

          <div class="knowledge-graph__control-grid">
            <label class="knowledge-graph__control-field">
              <span>最大深度</span>
              <el-input-number v-model="form.maxDepth" :min="1" :max="6" size="small" />
            </label>
            <label class="knowledge-graph__control-field">
              <span>最大节点</span>
              <el-input-number v-model="form.maxNodes" :min="40" :max="300" :step="20" size="small" />
            </label>
          </div>

          <div class="knowledge-graph__control-actions">
            <el-button :loading="isSearching" @click="fetchGraph()">应用范围</el-button>
            <el-button @click="resetView">重置视图</el-button>
          </div>

          <div class="knowledge-graph__facet-group">
            <div class="knowledge-graph__facet-head">
              <span>实体类型</span>
              <span>{{ activeFacetSummary.nodeTypeCount }}/{{ graphFacets.nodeTypes.length }}</span>
            </div>
            <div class="knowledge-graph__facet-list">
              <button
                v-for="item in graphFacets.nodeTypes"
                :key="item.label"
                type="button"
                :class="['knowledge-graph__facet-chip', { 'knowledge-graph__facet-chip--active': activeNodeTypes.includes(item.label) }]"
                @click="toggleFilter(activeNodeTypes, item.label)"
              >
                {{ item.label }} · {{ item.count }}
              </button>
            </div>
          </div>

          <div class="knowledge-graph__facet-group">
            <div class="knowledge-graph__facet-head">
              <span>关系类型</span>
              <span>{{ activeFacetSummary.relationLabelCount }}/{{ graphFacets.relationLabels.length }}</span>
            </div>
            <div class="knowledge-graph__facet-list">
              <button
                v-for="item in graphFacets.relationLabels"
                :key="item.label"
                type="button"
                :class="['knowledge-graph__facet-chip', { 'knowledge-graph__facet-chip--active': activeRelationLabels.includes(item.label) }]"
                @click="toggleFilter(activeRelationLabels, item.label)"
              >
                {{ item.label }} · {{ item.count }}
              </button>
            </div>
          </div>
        </section>
      </aside>

      <section class="knowledge-graph__stage">
        <div class="knowledge-graph__stage-top">
          <div class="knowledge-graph__search-block">
            <el-input
              v-model="form.nodeSearch"
              clearable
              placeholder="搜索当前图谱中的节点、类型或描述"
              @keyup.enter="handleNodeSearch"
            >
              <template #append>
                <el-button @click="handleNodeSearch">定位</el-button>
              </template>
            </el-input>
            <p class="knowledge-graph__search-hint">{{ searchSummary }}</p>
          </div>

          <div class="knowledge-graph__stage-actions">
            <el-button v-if="form.nodeSearch" @click="clearSearch">清空搜索</el-button>
            <span class="knowledge-graph__stage-stat">可见 {{ filteredGraph.nodes.length }} / {{ graph.nodes.length }} 节点</span>
            <span class="knowledge-graph__stage-stat">可见 {{ filteredGraph.edges.length }} / {{ graph.edges.length }} 关系</span>
            <span v-if="graph.isTruncated" class="knowledge-graph__stage-stat knowledge-graph__stage-stat--warning">结果已截断</span>
          </div>
        </div>

        <div v-if="hasVisibleGraph" class="knowledge-graph__canvas-shell">
          <LightragGraphCanvas
            :nodes="filteredGraph.nodes"
            :edges="filteredGraph.edges"
            :selected-node-id="selectedNodeId"
            :selected-edge-id="selectedEdgeId"
            :highlight-node-ids="visibleMatchedNodeIds"
            height="calc(100vh - 360px)"
            @select-node="selectNode"
            @select-edge="selectEdge"
          />
        </div>

        <div v-else-if="hasGraphData" class="knowledge-graph__empty">
          <p>当前筛选把节点都隐藏了。你可以重置视图，或者在左侧重新打开实体与关系类型。</p>
          <el-button @click="resetView">恢复全部节点</el-button>
        </div>

        <div v-else class="knowledge-graph__empty">
          <p v-if="labels.length">当前标签暂时没有返回图谱节点。你可以切换左侧标签，或者提高节点上限后重试。</p>
          <p v-else>图谱标签还在准备中。文档处理完成后，这里会直接显示可探索的标签列表。</p>
        </div>
      </section>

      <aside class="knowledge-graph__inspector">
        <section class="knowledge-graph__pane">
          <div class="knowledge-graph__pane-head">
            <div>
              <p class="knowledge-graph__pane-kicker">焦点对象</p>
              <h3 v-if="selectedNode">节点详情</h3>
              <h3 v-else-if="selectedEdge">关系详情</h3>
              <h3 v-else>查看详情</h3>
            </div>
          </div>

          <div v-if="selectedNode" class="knowledge-graph__detail-block">
            <div class="knowledge-graph__detail-title-row">
              <strong>{{ selectedNode.label }}</strong>
              <span class="knowledge-graph__detail-badge">{{ selectedNode.type }}</span>
            </div>

            <dl class="knowledge-graph__detail-grid">
              <div>
                <dt>节点 ID</dt>
                <dd class="mono-text">{{ selectedNode.id }}</dd>
              </div>
              <div>
                <dt>关联对象</dt>
                <dd>{{ selectedNodeNeighbors.length }}</dd>
              </div>
            </dl>

            <p v-if="selectedNode.description" class="knowledge-graph__detail-copy">{{ selectedNode.description }}</p>
            <p v-else class="knowledge-graph__muted-copy">该节点暂无补充描述。</p>

            <dl v-if="selectedNodeMetaRows.length" class="knowledge-graph__detail-grid">
              <div v-for="item in selectedNodeMetaRows" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd :class="{ 'mono-text': item.label !== '创建时间' }">{{ item.value }}</dd>
              </div>
            </dl>

            <div v-if="selectedNodeNeighbors.length" class="knowledge-graph__neighbor-list">
              <button
                v-for="neighbor in selectedNodeNeighbors"
                :key="`${neighbor.edgeId}-${neighbor.id}`"
                type="button"
                class="knowledge-graph__neighbor-item"
                @click="focusNode(neighbor.id, { resetFilters: true })"
              >
                <strong>{{ neighbor.label }}</strong>
                <span>{{ neighbor.edgeLabel }} · {{ neighbor.type }}</span>
              </button>
            </div>
          </div>

          <div v-else-if="selectedEdge" class="knowledge-graph__detail-block">
            <div class="knowledge-graph__detail-title-row">
              <strong>{{ selectedEdge.label }}</strong>
              <span class="knowledge-graph__detail-badge">关系</span>
            </div>

            <dl class="knowledge-graph__detail-grid">
              <div>
                <dt>起点</dt>
                <dd class="mono-text">{{ selectedEdge.source }}</dd>
              </div>
              <div>
                <dt>终点</dt>
                <dd class="mono-text">{{ selectedEdge.target }}</dd>
              </div>
            </dl>

            <p v-if="selectedEdge.description" class="knowledge-graph__detail-copy">{{ selectedEdge.description }}</p>
            <p v-else class="knowledge-graph__muted-copy">该关系暂无补充描述。</p>

            <dl v-if="selectedEdgeMetaRows.length" class="knowledge-graph__detail-grid">
              <div v-for="item in selectedEdgeMetaRows" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd :class="{ 'mono-text': item.label !== '创建时间' }">{{ item.value }}</dd>
              </div>
            </dl>
          </div>

          <div v-else class="knowledge-graph__detail-placeholder">
            <p>在画布中点击节点或关系，右侧就会显示结构化详情。</p>
          </div>
        </section>

        <section class="knowledge-graph__pane knowledge-graph__pane--compact">
          <div class="knowledge-graph__pane-head">
            <div>
              <p class="knowledge-graph__pane-kicker">搜索结果</p>
              <h3>定位节点</h3>
            </div>
            <span class="knowledge-graph__pane-count">{{ matchedNodes.length }}</span>
          </div>

          <div v-if="form.nodeSearch.trim()" class="knowledge-graph__result-list">
            <button
              v-for="node in matchedNodes"
              :key="node.id"
              type="button"
              :class="['knowledge-graph__result-item', { 'knowledge-graph__result-item--active': selectedNodeId === node.id }]"
              @click="focusNode(node.id, { resetFilters: true })"
            >
              <strong>{{ node.label }}</strong>
              <span>{{ node.type || '未分类' }}</span>
              <p v-if="node.description">{{ node.description }}</p>
            </button>
          </div>
          <p v-else class="knowledge-graph__muted-copy">输入关键词后，搜索结果会直接列在这里，不再只给一个看不见的高亮。</p>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.knowledge-graph {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.knowledge-graph__hero,
.knowledge-graph__pane,
.knowledge-graph__stage {
  border: 1px solid var(--line-soft);
  border-radius: 24px;
  background: var(--surface-2);
  box-shadow: 0 8px 24px -18px rgba(11, 15, 24, 0.42);
}

.knowledge-graph__hero {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 22px 24px;
}

.knowledge-graph__hero-copy {
  display: grid;
  gap: 8px;
  max-width: 72ch;
}

.knowledge-graph__hero-copy h2 {
  margin: 0;
  font-size: 1.4rem;
  line-height: 1.2;
  color: var(--text-primary);
}

.knowledge-graph__hero-copy p,
.knowledge-graph__muted-copy,
.knowledge-graph__detail-copy,
.knowledge-graph__search-hint {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.knowledge-graph__eyebrow,
.knowledge-graph__pane-kicker {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.knowledge-graph__hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.knowledge-graph__meta-pill,
.knowledge-graph__detail-badge,
.knowledge-graph__pane-count,
.knowledge-graph__stage-stat {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(141, 208, 208, 0.08);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}

.knowledge-graph__meta-pill--active {
  background: rgba(36, 87, 197, 0.14);
  color: var(--brand);
}

.knowledge-graph__stage-stat--warning {
  background: rgba(183, 121, 31, 0.14);
  color: var(--warning);
}

.knowledge-graph__workspace {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr) minmax(280px, 340px);
  gap: 18px;
  min-width: 0;
  align-items: start;
}

.knowledge-graph__rail,
.knowledge-graph__inspector {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.knowledge-graph__pane,
.knowledge-graph__stage {
  display: grid;
  gap: 16px;
  min-width: 0;
  padding: 20px;
}

.knowledge-graph__pane--compact {
  gap: 14px;
}

.knowledge-graph__pane-head,
.knowledge-graph__facet-head,
.knowledge-graph__detail-title-row,
.knowledge-graph__stage-top,
.knowledge-graph__control-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.knowledge-graph__pane-head h3 {
  margin: 4px 0 0;
  color: var(--text-primary);
  font-size: 1rem;
  line-height: 1.2;
}

.knowledge-graph__label-list,
.knowledge-graph__facet-list,
.knowledge-graph__neighbor-list,
.knowledge-graph__result-list {
  display: grid;
  gap: 8px;
}

.knowledge-graph__label-list {
  max-height: 380px;
  overflow-y: auto;
}

.knowledge-graph__label-item,
.knowledge-graph__neighbor-item,
.knowledge-graph__result-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;
}

.knowledge-graph__label-item {
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
}

.knowledge-graph__label-item:hover,
.knowledge-graph__neighbor-item:hover,
.knowledge-graph__result-item:hover,
.knowledge-graph__label-item--active,
.knowledge-graph__result-item--active {
  border-color: rgba(36, 87, 197, 0.32);
  background: rgba(36, 87, 197, 0.1);
  transform: translateY(-1px);
}

.knowledge-graph__label-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(141, 208, 208, 0.7);
}

.knowledge-graph__control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.knowledge-graph__control-field {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}

.knowledge-graph__facet-group {
  display: grid;
  gap: 10px;
}

.knowledge-graph__facet-head {
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}

.knowledge-graph__facet-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, color 0.18s ease;
}

.knowledge-graph__facet-chip--active,
.knowledge-graph__facet-chip:hover {
  border-color: rgba(36, 87, 197, 0.28);
  background: rgba(36, 87, 197, 0.1);
  color: var(--brand);
}

.knowledge-graph__stage {
  background:
    radial-gradient(circle at top, rgba(36, 87, 197, 0.08), transparent 42%),
    #111822;
}

.knowledge-graph__stage-top {
  flex-wrap: wrap;
  align-items: flex-start;
}

.knowledge-graph__search-block {
  display: grid;
  gap: 8px;
  min-width: min(100%, 420px);
  flex: 1;
}

.knowledge-graph__stage-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.knowledge-graph__canvas-shell {
  position: relative;
  min-width: 0;
  border: 1px solid rgba(159, 176, 198, 0.12);
  border-radius: 20px;
  overflow: hidden;
}

.knowledge-graph__empty,
.knowledge-graph__detail-placeholder {
  display: grid;
  gap: 12px;
  align-content: center;
  justify-items: start;
  min-height: 420px;
  padding: 20px;
  border: 1px dashed rgba(159, 176, 198, 0.18);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.03);
}

.knowledge-graph__empty p,
.knowledge-graph__detail-placeholder p {
  margin: 0;
  color: rgba(223, 229, 239, 0.8);
  line-height: 1.6;
}

.knowledge-graph__detail-block {
  display: grid;
  gap: 14px;
}

.knowledge-graph__detail-title-row strong,
.knowledge-graph__neighbor-item strong,
.knowledge-graph__result-item strong {
  color: var(--text-primary);
}

.knowledge-graph__detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.knowledge-graph__detail-grid div {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.knowledge-graph__detail-grid dt,
.knowledge-graph__neighbor-item span,
.knowledge-graph__result-item span {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.knowledge-graph__detail-grid dd,
.knowledge-graph__result-item p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

@media (max-width: 1480px) {
  .knowledge-graph__workspace {
    grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  }

  .knowledge-graph__inspector {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .knowledge-graph__workspace,
  .knowledge-graph__inspector,
  .knowledge-graph__control-grid,
  .knowledge-graph__detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .knowledge-graph__hero,
  .knowledge-graph__pane-head,
  .knowledge-graph__stage-top,
  .knowledge-graph__detail-title-row {
    align-items: flex-start;
  }
}
</style>
