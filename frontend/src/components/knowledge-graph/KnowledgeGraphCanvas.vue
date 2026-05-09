<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  nodes: {
    type: Array,
    default: () => [],
  },
  edges: {
    type: Array,
    default: () => [],
  },
  selectedNodeId: {
    type: String,
    default: '',
  },
  selectedEdgeId: {
    type: String,
    default: '',
  },
  highlightNodeIds: {
    type: Array,
    default: () => [],
  },
  height: {
    type: String,
    default: '600px',
  },
});

const emit = defineEmits(['select-node', 'select-edge']);

const palette = ['#2457c5', '#21815c', '#b7791f', '#c4493d', '#5d4db8', '#2d8a94', '#7b8798'];
const containerRef = ref(null);
let chartInstance = null;
let echartsModulePromise = null;
let renderVersion = 0;

const loadEcharts = async () => {
  if (!echartsModulePromise) {
    echartsModulePromise = import('echarts');
  }
  return echartsModulePromise;
};

const buildColorMap = () => {
  const typeMap = new Map();
  props.nodes.forEach((node) => {
    if (!typeMap.has(node.type)) {
      typeMap.set(node.type, palette[typeMap.size % palette.length]);
    }
  });
  return typeMap;
};

const renderChart = async () => {
  const currentRenderVersion = ++renderVersion;
  if (!containerRef.value) {
    return;
  }

  const echarts = await loadEcharts();
  if (currentRenderVersion !== renderVersion || !containerRef.value) {
    return;
  }

  if (!chartInstance) {
    chartInstance = echarts.init(containerRef.value);
    chartInstance.on('click', (params) => {
      if (params.dataType === 'node') {
        emit('select-node', params.data.id);
        return;
      }
      if (params.dataType === 'edge') {
        emit('select-edge', params.data.id);
      }
    });
  }

  const colorMap = buildColorMap();
  const highlightSet = new Set(props.highlightNodeIds);
  const selectedNodeId = props.selectedNodeId;
  const selectedEdgeId = props.selectedEdgeId;
  const showLabels = props.nodes.length <= 18;

  const data = props.nodes.map((node) => {
    const isSelected = node.id === selectedNodeId;
    const isHighlighted = highlightSet.has(node.id);
    return {
      ...node,
      name: node.label,
      displayLabel: node.label,
      symbolSize: isSelected ? 28 : isHighlighted ? 22 : 18,
      itemStyle: {
        color: colorMap.get(node.type) || palette[palette.length - 1],
        borderColor: isSelected ? '#dbe7ff' : isHighlighted ? '#2457c5' : 'rgba(255,255,255,0.18)',
        borderWidth: isSelected ? 3 : isHighlighted ? 2 : 1,
        shadowBlur: isSelected ? 14 : 0,
        shadowColor: isSelected ? 'rgba(36, 87, 197, 0.32)' : 'transparent',
      },
      label: {
        show: showLabels || isSelected || isHighlighted,
        color: '#cbd3df',
        fontWeight: isSelected ? 700 : 500,
      },
    };
  });

  const links = props.edges.map((edge) => {
    const isSelected = edge.id === selectedEdgeId;
    const isConnectedToSelectedNode = selectedNodeId
      && (edge.source === selectedNodeId || edge.target === selectedNodeId);
    return {
      ...edge,
      lineStyle: {
        color: isSelected ? '#8fb0ff' : '#6e7f96',
        width: isSelected ? 3 : isConnectedToSelectedNode ? 2.2 : 1.4,
        opacity: isSelected ? 0.92 : isConnectedToSelectedNode ? 0.68 : 0.28,
        curveness: 0.14,
      },
      label: {
        show: isSelected,
        formatter: edge.label,
        color: '#9fb0c6',
      },
    };
  });

  chartInstance.setOption(
    {
      animationDuration: 280,
      backgroundColor: 'transparent',
      tooltip: {
        confine: true,
        backgroundColor: '#111822',
        borderColor: 'rgba(203, 211, 223, 0.1)',
        textStyle: {
          color: '#dfe5ef',
        },
        formatter: (params) => {
          if (params.dataType === 'edge') {
            return [
              `<strong>${params.data.label}</strong>`,
              `${params.data.source} → ${params.data.target}`,
              params.data.description ? `<br/>${params.data.description}` : '',
            ].join('');
          }
          return [
            `<strong>${params.data.displayLabel || params.data.name || params.data.id}</strong>`,
            params.data.type ? `<br/>${params.data.type}` : '',
            params.data.description ? `<br/>${params.data.description}` : '',
          ].join('');
        },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          data,
          links,
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 6,
          lineStyle: {
            opacity: 0.32,
          },
          label: {
            show: showLabels,
            position: 'right',
            distance: 6,
            fontSize: 11,
          },
          emphasis: {
            focus: 'adjacency',
            scale: 1.1,
            label: {
              show: true,
            },
          },
          force: {
            repulsion: props.nodes.length > 45 ? 320 : 380,
            edgeLength: props.nodes.length > 45 ? [90, 160] : [110, 180],
            gravity: 0.06,
            friction: 0.12,
          },
        },
      ],
    },
    true,
  );

  chartInstance.resize();
};

const handleResize = () => {
  chartInstance?.resize();
};

watch(
  () => [
    props.nodes,
    props.edges,
    props.selectedNodeId,
    props.selectedEdgeId,
    props.highlightNodeIds,
  ],
  () => {
    void renderChart();
  },
  { deep: true },
);

onMounted(() => {
  void renderChart();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  renderVersion += 1;
  window.removeEventListener('resize', handleResize);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<template>
  <div ref="containerRef" class="knowledge-graph-canvas" :style="{ height }" />
</template>

<style scoped>
.knowledge-graph-canvas {
  width: 100%;
  min-height: 340px;
}
</style>
