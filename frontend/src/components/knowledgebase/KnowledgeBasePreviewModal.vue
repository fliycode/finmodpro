<script setup>
defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  previewState: {
    type: Object,
    default: () => ({ hasContent: false, body: '' }),
  },
});

defineEmits(['update:modelValue']);
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="文档预览"
    width="760px"
    @close="$emit('update:modelValue', false)"
  >
    <div v-if="previewState.hasContent" class="kb-preview-modal__body">
      <pre>{{ previewState.body }}</pre>
    </div>
    <div v-else class="kb-preview-modal__empty">
      <h4>当前暂无可预览文本</h4>
      <p>请先完成解析，或直接查看原文。</p>
    </div>
  </el-dialog>
</template>

<style scoped>
.kb-preview-modal__body pre {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid color-mix(in oklab, var(--brand) 14%, var(--line-soft));
  padding: 14px;
  background: color-mix(in oklab, var(--brand) 4%, var(--surface-3));
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.kb-preview-modal__empty h4 {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-weight: 600;
}

.kb-preview-modal__empty p {
  margin: 0;
  color: var(--text-secondary);
}
</style>
