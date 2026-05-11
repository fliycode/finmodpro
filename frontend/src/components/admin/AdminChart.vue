<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { init, use } from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

const props = defineProps({
  option: {
    type: Object,
    required: true,
  },
  height: {
    type: String,
    default: '280px',
  },
});

const containerRef = ref(null);
let chartInstance = null;

const renderChart = () => {
  if (!containerRef.value) {
    return;
  }

  if (!chartInstance) {
    chartInstance = init(containerRef.value);
  }

  chartInstance.setOption(props.option, true);
  chartInstance.resize();
};

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

watch(
  () => props.option,
  () => {
    renderChart();
  },
  { deep: true },
);

onMounted(() => {
  renderChart();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<template>
  <div ref="containerRef" class="admin-chart" :style="{ height: props.height }" />
</template>

<style scoped>
.admin-chart {
  width: 100%;
  min-height: 220px;
}
</style>
