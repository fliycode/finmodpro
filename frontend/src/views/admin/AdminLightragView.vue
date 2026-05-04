<script setup>
import { onMounted, ref } from 'vue';

const iframeSrc = '/admin/lightrag/webui/';
const loaded = ref(false);
const errored = ref(false);

onMounted(() => {
  setTimeout(() => {
    if (!loaded.value) {
      errored.value = true;
    }
  }, 10000);
});
</script>

<template>
  <div class="lightrag-embed">
    <iframe
      v-if="!errored"
      :src="iframeSrc"
      class="lightrag-embed__frame"
      title="LightRAG 图谱检索"
      @load="loaded = true"
    />
    <div v-else class="lightrag-embed__fallback">
      <p>Legacy LightRAG WebUI 加载失败，请确认服务已启动。</p>
      <a :href="iframeSrc" target="_blank" rel="noopener">在新窗口中打开</a>
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
  color: #666;
}

.lightrag-embed__fallback a {
  color: #2457c5;
  text-decoration: underline;
}
</style>
