<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import LightragGraphCanvas from '../../components/lightrag/LightragGraphCanvas.vue';
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
const graph = ref({ nodes: [], edges: [], isTruncated: false });
const activeNodeTypes = ref([]);
const activeRelationLabels = ref([]);
const selectedNodeId = ref('');
const selectedEdgeId = ref('');

const form = reactive({
  label: '',
  nodeSearch: '',
  maxDepth: 3,
  maxNodes: 120,
});

const graphFacets = computed(() => buildLightragGraphFacets(graph.value.nodes, graph.value.edges));
const filteredGraph = computed(() => filterLightragGraph(graph.value, {
  activeNodeTypes: activeNodeTypes.value,
  activeRelationLabels: activeRelationLabels.value,
}));
const matchedNodeIds = computed(() => searchLightragGraphNodes(filteredGraph.value.nodes, form.nodeSearch));
const selectedNode = computed(() => filteredGraph.value.nodes.find((node) => node.id === selectedNodeId.value) || null);
const selectedEdge = computed(() => filteredGraph.value.edges.find((edge) => edge.id === selectedEdgeId.value) || null);

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
    labels.value = await lightragApi.getLabelList();
  } catch (error) {
    errorMsg.value = error.message || '加载标签失败。';
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
  } catch (error) {
    errorMsg.value = error.message || '加载图谱失败。';
  } finally {
    isSearching.value = false;
  }
};

const handleRefresh = () => {
  loadLabels();
  if (form.label) {
    fetchGraph();
  }
};

const focusFirstMatch = () => {
  if (!matchedNodeIds.value.length) {
    flash.warning('当前画布里没有匹配的节点。');
    return;
  }
  selectedNodeId.value = matchedNodeIds.value[0];
  selectedEdgeId.value = '';
};

const selectNode = (nodeId) => {
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = '';
};

const selectEdge = (edgeId) => {
  selectedEdgeId.value = edgeId;
  selectedNodeId.value = '';
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

onMounted(loadLabels);
</script>

<template>
  <div class="knowledge-graph">
    <div class="knowledge-graph__toolbar">
      <div class="knowledge-graph__toolbar-left">
        <el-select
          v-model="form.label"
          filterable
          placeholder="选择标签"
          :loading="isLoading"
          style="width: 200px;"
        >
          <el-option
            v-for="label in labels"
            :key="label"
            :label="label"
            :value="label"
          />
        </el-select>
        <el-input
          v-model="form.nodeSearch"
          placeholder="搜索节点"
          style="width: 200px;"
          @keyup.enter="focusFirstMatch"
        >
          <template #append>
            <el-button @click="focusFirstMatch">
              <el-icon><component is="search" /></el-icon>
            </el-button>
          </template>
        </el-input>
        <el-button type="primary" :loading="isSearching" @click="fetchGraph()">加载图谱</el-button>
      </div>
      <div class="knowledge-graph__toolbar-right">
        <el-button :loading="isLoading" @click="handleRefresh">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <div class="knowledge-graph__body">
      <div v-if="graphFacets.nodeTypes.length" class="knowledge-graph__facets">
        <span class="knowledge-graph__facet-label">实体类型</span>
        <button
          v-for="item in graphFacets.nodeTypes"
          :key="item.label"
          type="button"
          :class="['knowledge-graph__facet-chip', { 'knowledge-graph__facet-chip--active': activeNodeTypes.includes(item.label) }]"
          @click="toggleFilter(activeNodeTypes, item.label)"
        >
          {{ item.label }} · {{ item.count }}
        </button>
        <span class="knowledge-graph__facet-divider" />
        <span class="knowledge-graph__facet-label">关系类型</span>
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

      <div v-if="filteredGraph.nodes.length" class="knowledge-graph__canvas">
        <LightragGraphCanvas
          :nodes="filteredGraph.nodes"
          :edges="filteredGraph.edges"
          :selected-node-id="selectedNodeId"
          :selected-edge-id="selectedEdgeId"
          :highlight-node-ids="matchedNodeIds"
          height="calc(100vh - 280px)"
          @select-node="selectNode"
          @select-edge="selectEdge"
        />
        <div class="knowledge-graph__canvas-stats">
          <span>{{ filteredGraph.nodes.length }} 节点</span>
          <span>{{ filteredGraph.edges.length }} 关系</span>
          <span v-if="graph.isTruncated">已截断</span>
          <span v-if="matchedNodeIds.length">匹配 {{ matchedNodeIds.length }}</span>
        </div>
      </div>
      <div v-else class="knowledge-graph__empty">
        <p>选择一个标签并加载图谱，实体关系将在画布中呈现。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-graph {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.knowledge-graph__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.knowledge-graph__toolbar-left,
.knowledge-graph__toolbar-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.knowledge-graph__body {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.knowledge-graph__facets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.knowledge-graph__facet-label {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-right: 4px;
}

.knowledge-graph__facet-divider {
  width: 1px;
  height: 18px;
  background: var(--line-soft);
  margin: 0 6px;
}

.knowledge-graph__facet-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: 0.6875rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.knowledge-graph__facet-chip:hover,
.knowledge-graph__facet-chip--active {
  border-color: rgba(36, 87, 197, 0.24);
  background: var(--brand-soft);
  color: var(--brand);
}

.knowledge-graph__canvas {
  position: relative;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  overflow: hidden;
  background:
    radial-gradient(circle at top, rgba(36, 87, 197, 0.06), transparent 40%),
    #111822;
}

.knowledge-graph__canvas-stats {
  position: absolute;
  bottom: 12px;
  left: 14px;
  display: flex;
  gap: 10px;
  color: rgba(203, 211, 223, 0.6);
  font-size: 0.6875rem;
  font-weight: 500;
}

.knowledge-graph__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
}

.knowledge-graph__empty p {
  margin: 0;
  color: var(--text-muted);
}
</style>
