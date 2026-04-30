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
  datasets: {
    type: Array,
    default: () => [],
  },
  selectedDatasetId: {
    type: [String, Number],
    default: 'all',
  },
  isUploading: {
    type: Boolean,
    default: false,
  },
});

defineEmits([
  'update:searchKeyword',
  'update:statusFilter',
  'update:timeRange',
  'update:selectedDatasetId',
  'upload',
  'create-dataset',
]);
</script>

<template>
  <section class="kb-toolbar ui-card">
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

    <select
      class="kb-select"
      :value="selectedDatasetId"
      @change="$emit('update:selectedDatasetId', $event.target.value)"
    >
      <option value="all">全部数据集</option>
      <option
        v-for="dataset in datasets"
        :key="dataset.id"
        :value="dataset.id"
      >
        {{ dataset.name }}
      </option>
    </select>

    <input
      :value="searchKeyword"
      class="kb-search"
      type="text"
      placeholder="搜索知识库、文档、上传者..."
      @input="$emit('update:searchKeyword', $event.target.value)"
    />

    <button class="kb-secondary-btn" @click="$emit('create-dataset')">
      新建数据集
    </button>

    <button class="kb-primary-btn" :disabled="isUploading" @click="$emit('upload')">
      {{ isUploading ? '上传中...' : '上传文档' }}
    </button>
  </section>
</template>

<style scoped>
.kb-toolbar {
  display: grid;
  grid-template-columns: 150px 150px 170px minmax(220px, 1fr) auto auto;
  gap: 12px;
  padding: 18px;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}

.kb-search,
.kb-select {
  height: 40px;
  min-width: 0;
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  padding: 0 14px;
  background: var(--surface-3);
  color: var(--text-primary);
  outline: none;
}

.kb-search:focus,
.kb-select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}

.kb-primary-btn,
.kb-secondary-btn {
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  font-weight: 700;
  cursor: pointer;
}

.kb-primary-btn {
  border: none;
  background: var(--brand);
  color: #fff;
}

.kb-secondary-btn {
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  color: var(--text-primary);
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
