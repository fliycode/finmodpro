<script setup>
import { computed, onMounted, ref } from 'vue';
import { dashboardApi } from '../../api/dashboard.js';
import AdminDataTable from '../../components/admin/AdminDataTable.vue';

const audits = ref([]);
const isLoading = ref(false);
const errorMsg = ref('');
const currentPage = ref(1);
const pageSize = ref(25);
const total = ref(0);
const searchQuery = ref('');

const columns = [
  { prop: 'id', label: 'ID', width: '70' },
  { prop: 'actor_name', label: '操作人', minWidth: '100' },
  { key: 'action', label: '操作', minWidth: '140', slot: 'action' },
  { prop: 'target_type', label: '目标类型', minWidth: '100' },
  { key: 'status', label: '状态', width: '80', slot: 'status' },
  { prop: 'created_at', label: '时间', minWidth: '150' },
];

const statusLabels = { succeeded: '成功', failed: '失败', pending: '待处理' };
const statusTypes = { succeeded: 'success', failed: 'danger', pending: 'info' };

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    };
    if (searchQuery.value) params.search = searchQuery.value;

    const data = await dashboardApi.getAudits(params);
    audits.value = data.results || data.audits || [];
    total.value = data.total || 0;
  } catch (err) {
    errorMsg.value = err.message || '加载审计日志失败';
  } finally {
    isLoading.value = false;
  }
};

const formatTime = (iso) => {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
};

const onSearch = (value) => {
  searchQuery.value = value;
  currentPage.value = 1;
  fetchData();
};

onMounted(fetchData);
</script>

<template>
  <div class="audit-log-page">
    <AdminDataTable
      :data="audits"
      :columns="columns"
      :loading="isLoading"
      :error="errorMsg"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      :show-search="true"
      search-placeholder="搜索操作人或操作..."
      @update:current-page="currentPage = $event; fetchData()"
      @update:page-size="pageSize = $event; currentPage = 1; fetchData()"
      @search="onSearch"
      @retry="fetchData"
    >
      <template #action="{ row }">
        <span>{{ row.action }}</span>
      </template>

      <template #status="{ row }">
        <el-tag :type="statusTypes[row.status] || 'info'" size="small" effect="plain">
          {{ statusLabels[row.status] || row.status }}
        </el-tag>
      </template>
    </AdminDataTable>
  </div>
</template>

<style scoped>
.audit-log-page {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
