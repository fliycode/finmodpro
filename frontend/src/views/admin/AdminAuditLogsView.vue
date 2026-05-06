<script setup>
import { computed, onMounted, ref } from 'vue';
import { dashboardApi } from '../../api/dashboard.js';
import AdminDataTable from '../../components/admin/AdminDataTable.vue';
import OpsSectionFrame from '../../components/admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from '../../components/admin/ops/OpsStatusBand.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';

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
const statusItems = computed(() => ([
  {
    key: 'total',
    label: '审计记录',
    value: total.value || audits.value.length,
    note: '当前筛选条件下可回看的审计流水。',
  },
  {
    key: 'failed',
    label: '失败动作',
    value: audits.value.filter((item) => item.status === 'failed').length,
    note: '需要进一步复盘或重试的异常动作。',
  },
  {
    key: 'actors',
    label: '操作主体',
    value: new Set(audits.value.map((item) => item.actor_name).filter(Boolean)).size,
    note: '当前结果中出现过的操作者数量。',
  },
  {
    key: 'page',
    label: '当前分页',
    value: `${currentPage.value} / ${Math.max(1, Math.ceil((total.value || 0) / pageSize.value))}`,
    note: `每页 ${pageSize.value} 条。`,
  },
]));
const frameMeta = computed(() => [
  `搜索：${searchQuery.value || '未启用'}`,
  `分页：${pageSize.value} / 页`,
]);

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
  <OpsSectionFrame
    eyebrow="Governance / Audit"
    title="操作审计"
    summary="审计页只保留一张可检索的流水工作面，让操作主体、动作、目标与结果状态在同一张表内完成核查。"
    :meta="frameMeta"
  >
    <template #status-band>
      <OpsStatusBand :items="statusItems" />
    </template>

    <AppSectionCard title="审计流水" desc="支持按操作人或动作搜索，重点关注失败状态和关键目标类型。" admin>
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
    </AppSectionCard>
  </OpsSectionFrame>
</template>

<style scoped>
.audit-log-page {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
