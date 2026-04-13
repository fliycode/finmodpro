<script setup>
defineProps({
  chunks: {
    type: Array,
    default: () => [],
  },
  expandedChunkIds: {
    type: Array,
    default: () => [],
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
});

defineEmits(['toggle-chunk']);
</script>

<template>
  <div v-if="isLoading" class="kb-empty-state">正在加载切块数据...</div>
  <div v-else-if="chunks.length === 0" class="kb-empty-state">当前文档暂无切块数据。</div>
  <div v-else class="kb-chunks">
    <article v-for="chunk in chunks" :key="chunk.id" class="kb-chunk">
      <div class="kb-chunk__meta">
        <div>
          <strong>{{ chunk.pageLabel }}</strong>
          <span>Chunk #{{ chunk.chunkIndex + 1 }}</span>
        </div>
        <span class="kb-chunk__vector">{{ chunk.vectorId || '未写入向量' }}</span>
      </div>

      <p>
        {{
          expandedChunkIds.includes(chunk.id)
            ? chunk.content
            : `${chunk.content.slice(0, 180)}${chunk.content.length > 180 ? '…' : ''}`
        }}
      </p>

      <button type="button" class="kb-link-btn" @click="$emit('toggle-chunk', chunk.id)">
        {{ expandedChunkIds.includes(chunk.id) ? '收起' : '展开' }}
      </button>
    </article>
  </div>
</template>

<style scoped>
.kb-empty-state {
  padding: 20px 0;
  color: #5a677d;
}

.kb-chunks {
  display: grid;
  gap: 12px;
}

.kb-chunk {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 16px;
  padding: 14px 16px;
  background: #f9fbfd;
}

.kb-chunk__meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.kb-chunk__meta div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kb-chunk__meta strong {
  color: #142033;
}

.kb-chunk__meta span,
.kb-chunk p {
  color: #5a677d;
}

.kb-chunk__vector {
  font-size: 12px;
  color: #6b7b93;
}

.kb-link-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  border-radius: 12px;
  padding: 6px 10px;
  background: #fff;
  color: #142033;
  cursor: pointer;
}
</style>
