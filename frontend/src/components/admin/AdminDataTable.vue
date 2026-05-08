<script setup>
import { computed, ref, watch } from 'vue';
import { ElTable, ElTableColumn, ElPagination, ElInput, ElButton, ElPopover, ElCheckboxGroup, ElCheckbox, ElTag, ElSkeleton } from 'element-plus';
import AppIcon from '../ui/AppIcon.vue';

const props = defineProps({
  // Data
  data: { type: Array, default: () => [] },
  columns: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },

  // Pagination
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 25 },
  total: { type: Number, default: 0 },
  pageSizes: { type: Array, default: () => [10, 25, 50, 100] },

  // Sort
  sortField: { type: String, default: '' },
  sortOrder: { type: String, default: '' },

  // Search
  searchPlaceholder: { type: String, default: '搜索...' },
  showSearch: { type: Boolean, default: true },

  // Selection
  showSelection: { type: Boolean, default: false },

  // Misc
  rowKey: { type: String, default: 'id' },
  stripe: { type: Boolean, default: true },
  compact: { type: Boolean, default: true },
});

const emit = defineEmits([
  'update:currentPage', 'update:pageSize',
  'update:sortField', 'update:sortOrder',
  'search', 'refresh', 'retry',
  'selection-change',
]);

// ── Search ──
const searchInput = ref('');
let debounceTimer = null;

const onSearchInput = (value) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    emit('search', value);
  }, 300);
};

watch(() => props.data, () => {
  // Reset search when data reloads externally
}, { flush: 'post' });

// ── Column visibility ──
const visibleColumns = ref(props.columns.map((col) => col.key || col.prop));
const allColumnKeys = computed(() => props.columns.map((col) => col.key || col.prop));

const visibleCols = computed(() =>
  props.columns.filter((col) => visibleColumns.value.includes(col.key || col.prop))
);

// ── Sorting ──
const tableRef = ref(null);

const onSortChange = ({ prop, order }) => {
  emit('update:sortField', prop || '');
  emit('update:sortOrder', order || '');
};

const sortInfo = computed(() => {
  if (!props.sortField) return {};
  return { prop: props.sortField, order: props.sortOrder || 'descending' };
});

// ── Selection ──
const selectedRows = ref([]);

const onSelectionChange = (rows) => {
  selectedRows.value = rows;
  emit('selection-change', rows);
};

const clearSelection = () => {
  tableRef.value?.clearSelection();
  selectedRows.value = [];
};

defineExpose({ clearSelection });

// ── Pagination ──
const onPageChange = (page) => emit('update:currentPage', page);
const onPageSizeChange = (size) => emit('update:pageSize', size);

const paginationLayout = computed(() => {
  if (props.total <= props.pageSizes[0]) return 'total';
  return 'total, sizes, prev, pager, next, jumper';
});
</script>

<template>
  <div class="admin-data-table">
    <!-- Toolbar -->
    <div v-if="showSearch || $slots.toolbar" class="admin-data-table__toolbar">
      <div class="admin-data-table__toolbar-left">
        <slot name="toolbar" />
        <el-tag
          v-if="selectedRows.length > 0"
          type="info"
          size="small"
          closable
          @close="clearSelection"
        >
          已选 {{ selectedRows.length }} 项
        </el-tag>
      </div>

      <div class="admin-data-table__toolbar-right">
        <el-input
          v-if="showSearch"
          v-model="searchInput"
          :placeholder="searchPlaceholder"
          size="small"
          clearable
          class="admin-data-table__search"
          @input="onSearchInput"
        >
          <template #prefix>
            <AppIcon name="search" />
          </template>
        </el-input>

        <el-popover
          v-if="columns.length > 2"
          placement="bottom-end"
          :width="180"
          trigger="click"
        >
          <template #reference>
            <el-button size="small" text>
              <AppIcon name="settings" />
              列设置
            </el-button>
          </template>
          <el-checkbox-group v-model="visibleColumns" size="small">
            <div v-for="col in columns" :key="col.key || col.prop" class="admin-data-table__col-toggle">
              <el-checkbox :label="col.key || col.prop" :value="col.key || col.prop">
                {{ col.label }}
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </el-popover>
      </div>
    </div>

    <!-- Error state -->
    <div v-if="error" class="admin-data-table__error">
      <span>{{ error }}</span>
      <el-button size="small" @click="emit('retry')">重试</el-button>
    </div>

    <!-- Table -->
    <el-table
      v-else
      ref="tableRef"
      :data="data"
      :row-key="rowKey"
      :stripe="stripe"
      :size="compact ? 'small' : 'default'"
      :default-sort="sortInfo"
      v-loading="loading"
      element-loading-text="加载中..."
      @sort-change="onSortChange"
      @selection-change="onSelectionChange"
    >
      <!-- Selection column -->
      <el-table-column
        v-if="showSelection"
        type="selection"
        width="36"
        :reserve-selection="true"
      />

      <!-- Data columns -->
      <el-table-column
        v-for="col in visibleCols"
        :key="col.key || col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
        :sortable="col.sortable ? 'custom' : false"
        :fixed="col.fixed"
        :show-overflow-tooltip="col.tooltip !== false"
      >
        <template v-if="col.slot" #default="scope">
          <slot :name="col.slot" :row="scope.row" :$index="scope.$index" />
        </template>
      </el-table-column>

      <!-- Empty state -->
      <template #empty>
        <div class="admin-data-table__empty">
          <AppIcon name="inbox" />
          <span>暂无数据</span>
        </div>
      </template>
    </el-table>

    <!-- Pagination -->
    <div v-if="total > 0" class="admin-data-table__pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="pageSizes"
        :total="total"
        :layout="paginationLayout"
        small
        background
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
.admin-data-table {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.admin-data-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 36px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line-soft);
}

.admin-data-table__toolbar-left,
.admin-data-table__toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-data-table__search {
  width: clamp(240px, 28vw, 340px);
}

.admin-data-table__search :deep(.el-input__wrapper) {
  border-radius: 999px;
  background: var(--surface-2);
  border-color: var(--line-soft);
  box-shadow: none;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}

.admin-data-table__search :deep(.el-input__wrapper:hover) {
  border-color: var(--line-strong);
}

.admin-data-table__search :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-accent);
  background: var(--surface-1);
  box-shadow: 0 0 0 1px var(--color-accent);
}

.admin-data-table__col-toggle {
  padding: 2px 0;
}

.admin-data-table__error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 16px;
  color: var(--risk);
  font-size: 0.8125rem;
  border: 1px dashed var(--line-strong);
  border-radius: 18px;
}

.admin-data-table__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  color: var(--text-muted);
}

.admin-data-table__empty .app-icon {
  width: 32px;
  height: 32px;
  opacity: 0.4;
}

.admin-data-table__pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
  border-top: 1px solid var(--line-soft);
}

.admin-data-table :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  overflow: hidden;
}

.admin-data-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.admin-data-table :deep(.el-table th.el-table__cell) {
  height: 44px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  background: transparent;
}

.admin-data-table :deep(.el-table td.el-table__cell) {
  padding-block: 10px;
}

.admin-data-table :deep(.el-table tr) {
  background: transparent;
}

.admin-data-table :deep(.el-table th.el-table__cell .cell),
.admin-data-table :deep(.el-table td.el-table__cell .cell) {
  padding-inline: 14px;
}

@media (max-width: 860px) {
  .admin-data-table__toolbar {
    flex-wrap: wrap;
    align-items: stretch;
  }

  .admin-data-table__toolbar-left,
  .admin-data-table__toolbar-right,
  .admin-data-table__search {
    width: 100%;
  }

  .admin-data-table__toolbar-right {
    justify-content: space-between;
  }
}
</style>
