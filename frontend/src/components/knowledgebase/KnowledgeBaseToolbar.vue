<script setup>
defineProps({
  searchKeyword: {
    type: String,
    default: '',
  },
  statusFilter: {
    type: String,
    default: 'all',
  },
  timeRange: {
    type: String,
    default: 'all',
  },
  isUploading: {
    type: Boolean,
    default: false,
  },
});

defineEmits(['update:searchKeyword', 'update:statusFilter', 'update:timeRange', 'upload']);
</script>

<template>
  <section class="kb-toolbar ui-card">
    <input
      :value="searchKeyword"
      class="kb-search"
      type="text"
      placeholder="搜索文档名、文件名、上传者"
      @input="$emit('update:searchKeyword', $event.target.value)"
    />

    <select
      class="kb-select"
      :value="statusFilter"
      @change="$emit('update:statusFilter', $event.target.value)"
    >
      <option value="all">全部状态</option>
      <option value="processing">处理中</option>
      <option value="indexed">已入库</option>
      <option value="failed">失败</option>
    </select>

    <select
      class="kb-select"
      :value="timeRange"
      @change="$emit('update:timeRange', $event.target.value)"
    >
      <option value="all">全部时间</option>
      <option value="7d">近 7 天</option>
      <option value="30d">近 30 天</option>
    </select>

    <button class="kb-primary-btn" :disabled="isUploading" @click="$emit('upload')">
      {{ isUploading ? '上传中...' : '上传文档' }}
    </button>
  </section>
</template>

<style scoped>
.kb-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px 160px auto;
  gap: 14px;
  padding: 18px 22px;
}

.kb-search,
.kb-select {
  height: 44px;
  border: 1px solid rgba(20, 32, 51, 0.12);
  border-radius: 14px;
  padding: 0 14px;
  background: #fff;
  color: #142033;
}

.kb-primary-btn {
  height: 44px;
  border: none;
  border-radius: 14px;
  padding: 0 18px;
  background: #2457c5;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.kb-primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 980px) {
  .kb-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
