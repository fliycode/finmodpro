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
  border-radius: 16px;
  padding: 16px;
  background: #f6f8fb;
  color: #263246;
  line-height: 1.7;
  white-space: pre-wrap;
}

.kb-preview-modal__empty h4 {
  margin: 0 0 8px;
  color: #142033;
}

.kb-preview-modal__empty p {
  margin: 0;
  color: #5a677d;
}
</style>
