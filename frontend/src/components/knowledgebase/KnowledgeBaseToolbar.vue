<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import AppIcon from '../ui/AppIcon.vue';

const props = defineProps({
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

const emit = defineEmits([
  'update:searchKeyword',
  'update:statusFilter',
  'update:timeRange',
  'update:selectedDatasetId',
  'upload',
  'create-dataset',
]);

const toolbarRef = ref(null);

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'processing', label: '处理中' },
  { value: 'indexed', label: '已入库' },
  { value: 'failed', label: '失败' },
];

const timeOptions = [
  { value: 'all', label: '全部时间' },
  { value: '7d', label: '近 7 天' },
  { value: '30d', label: '近 30 天' },
];

const datasetOptions = computed(() => [
  { value: 'all', label: '全部数据集' },
  ...props.datasets.map((ds) => ({ value: ds.id, label: ds.name })),
]);

const controls = reactive([
  {
    id: 'status',
    options: statusOptions,
    emitName: 'update:statusFilter',
    open: false,
  },
  {
    id: 'time',
    options: timeOptions,
    emitName: 'update:timeRange',
    open: false,
  },
  {
    id: 'dataset',
    options: datasetOptions,
    emitName: 'update:selectedDatasetId',
    open: false,
  },
]);

const selectedLabels = computed(() => ({
  status: statusOptions.find((o) => o.value === props.statusFilter)?.label || '全部状态',
  time: timeOptions.find((o) => o.value === props.timeRange)?.label || '全部时间',
  dataset: datasetOptions.value.find((o) => String(o.value) === String(props.selectedDatasetId))?.label || '全部数据集',
}));

const toggleDropdown = (control) => {
  controls.forEach((c) => {
    if (c.id !== control.id) c.open = false;
  });
  control.open = !control.open;
};

const selectOption = (control, value) => {
  emit(control.emitName, value);
  control.open = false;
};

const handleClickOutside = (event) => {
  if (toolbarRef.value && !toolbarRef.value.contains(event.target)) {
    controls.forEach((c) => { c.open = false; });
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <section ref="toolbarRef" class="kb-toolbar ui-card">
    <div
      v-for="control in controls"
      :key="control.id"
      class="kb-custom-select"
      :class="{ 'is-open': control.open }"
    >
      <button
        type="button"
        class="kb-custom-select__trigger"
        @click.stop="toggleDropdown(control)"
      >
        <span>{{ selectedLabels[control.id] }}</span>
        <AppIcon name="chevron-down" :width="12" :height="12" />
      </button>
      <div v-if="control.open" class="kb-custom-select__dropdown">
        <button
          v-for="option in control.options"
          :key="option.value"
          type="button"
          :class="['kb-custom-select__option', { active: String(option.value) === String(control.id === 'dataset' ? selectedDatasetId : control.id === 'status' ? statusFilter : timeRange) }]"
          @click.stop="selectOption(control, option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <input
      :value="searchKeyword"
      class="kb-search"
      type="text"
      placeholder="搜索知识库、文档、上传者..."
      @input="emit('update:searchKeyword', $event.target.value)"
    />

    <button class="kb-secondary-btn" @click="emit('create-dataset')">
      新建数据集
    </button>

    <button class="kb-primary-btn" :disabled="isUploading" @click="emit('upload')">
      {{ isUploading ? '上传中...' : '上传文档' }}
    </button>
  </section>
</template>

<style scoped>
.kb-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  align-items: center;
}

.kb-custom-select {
  position: relative;
  min-width: 130px;
  flex: 0 0 auto;
}

.kb-custom-select__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: var(--surface-3);
  color: var(--text-primary);
  cursor: pointer;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.kb-custom-select__trigger:focus,
.kb-custom-select.is-open .kb-custom-select__trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
  outline: none;
}

.kb-custom-select__dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 50;
  min-width: 200px;
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  padding: 4px;
}

.kb-custom-select__option {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  transition: background 0.12s ease;
}

.kb-custom-select__option:hover,
.kb-custom-select__option.active {
  background: var(--brand-soft);
  color: var(--brand);
}

.kb-search {
  flex: 1 1 200px;
  min-width: 0;
  height: 40px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  padding: 0 14px;
  background: var(--surface-3);
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.kb-search:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}

.kb-primary-btn,
.kb-secondary-btn {
  height: 40px;
  border-radius: 12px;
  padding: 0 18px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  flex: 0 0 auto;
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

@media (max-width: 600px) {
  .kb-toolbar {
    flex-direction: column;
  }

  .kb-search,
  .kb-custom-select {
    width: 100%;
    flex: none;
  }
}
</style>
