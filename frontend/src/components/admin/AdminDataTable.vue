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
  gap: 8px;
}

.admin-data-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
}

.admin-data-table__toolbar-left,
.admin-data-table__toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-data-table__search {
  width: 200px;
}

.admin-data-table__col-toggle {
  padding: 2px 0;
}

.admin-data-table__error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px 16px;
  color: var(--risk);
  font-size: 0.8125rem;
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
  padding-top: 4px;
}
</style>
