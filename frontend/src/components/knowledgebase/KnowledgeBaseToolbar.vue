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
  grid-template-columns: minmax(0, 1fr) 160px 160px 180px auto auto;
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

.kb-primary-btn,
.kb-secondary-btn {
  height: 44px;
  border-radius: 14px;
  padding: 0 18px;
  font-weight: 700;
  cursor: pointer;
}

.kb-primary-btn {
  border: none;
  background: #2457c5;
  color: #fff;
}

.kb-secondary-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  color: #142033;
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
