<script setup>
import { onBeforeUnmount, ref } from 'vue';

const iframeSrc = '/admin/lightrag/webui/';
const loaded = ref(false);
const errored = ref(false);
const retrying = ref(false);
let timeoutId = null;

const startTimeout = () => {
  clearTimeout(timeoutId);
  timeoutId = setTimeout(() => {
    if (!loaded.value) {
      errored.value = true;
    }
  }, 10000);
};

const retry = () => {
  errored.value = false;
  loaded.value = false;
  retrying.value = true;
  startTimeout();
  setTimeout(() => {
    retrying.value = false;
  }, 500);
};

startTimeout();

onBeforeUnmount(() => {
  clearTimeout(timeoutId);
});
</script>

<template>
  <div class="lightrag-embed">
    <iframe
      v-if="!errored"
      :key="retrying"
      :src="iframeSrc"
      class="lightrag-embed__frame"
      title="LightRAG 图谱检索"
      @load="loaded = true"
    />
    <div v-else class="lightrag-embed__fallback">
      <p>Legacy LightRAG WebUI 加载超时，请确认服务已启动。</p>
      <div class="lightrag-embed__fallback-actions">
        <el-button size="small" @click="retry">重新加载</el-button>
        <a :href="iframeSrc" target="_blank" rel="noopener">在新窗口中打开</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lightrag-embed {
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 120px);
}

.lightrag-embed__frame {
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 120px);
  border: none;
}

.lightrag-embed__fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 40vh;
  gap: 12px;
  color: var(--text-muted);
}

.lightrag-embed__fallback-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lightrag-embed__fallback a {
  color: var(--brand);
  font-size: 0.8125rem;
}
</style>
