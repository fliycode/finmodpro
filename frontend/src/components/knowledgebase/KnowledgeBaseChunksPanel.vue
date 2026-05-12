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
    <article
      v-for="chunk in chunks"
      :key="chunk.id"
      :class="['kb-chunk', { 'is-expanded': expandedChunkIds.includes(chunk.id) }]"
    >
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
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-secondary);
}

.kb-chunks {
  display: grid;
  gap: 12px;
}

.kb-chunk {
  border: 1px solid color-mix(in oklab, var(--kb-accent, var(--brand)) 14%, var(--line-soft));
  border-radius: 16px;
  padding: 14px 16px;
  background: color-mix(in oklab, var(--kb-accent, var(--brand)) 4%, var(--surface-3));
  transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.kb-chunk.is-expanded {
  border-color: color-mix(in oklab, var(--kb-accent, var(--brand)) 24%, var(--line-soft));
  background: color-mix(in oklab, var(--kb-accent, var(--brand)) 8%, var(--surface-2));
  transform: translateY(-1px);
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
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
  font-size: 13px;
  color: var(--text-primary);
}

.kb-chunk__meta span {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: var(--text-secondary);
}

.kb-chunk p {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-secondary);
  line-height: 1.6;
}

.kb-chunk__vector {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--kb-accent, var(--brand)) 7%, var(--surface-2));
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace;
  font-size: 12px;
  color: var(--text-muted);
}

.kb-link-btn {
  border: 1px solid color-mix(in oklab, var(--kb-accent, var(--brand)) 16%, var(--line-strong));
  border-radius: 12px;
  padding: 6px 10px;
  background: color-mix(in oklab, var(--kb-accent, var(--brand)) 4%, var(--surface-2));
  color: color-mix(in oklab, var(--kb-accent, var(--brand)) 42%, var(--text-primary));
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease, color 0.12s ease;
}

.kb-link-btn:hover {
  background: color-mix(in oklab, var(--kb-accent, var(--brand)) 10%, var(--surface-2));
}

.kb-link-btn:focus-visible {
  outline: 2px solid color-mix(in oklab, var(--kb-accent, var(--brand)) 50%, transparent);
  outline-offset: 2px;
}
</style>
