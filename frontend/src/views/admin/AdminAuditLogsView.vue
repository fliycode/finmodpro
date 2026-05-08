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
const pageSize = ref(10);
const total = ref(0);
const searchQuery = ref('');

const columns = [
  { prop: 'id', label: 'ID', width: '64' },
  { prop: 'actor_name', label: '操作人', width: '120' },
  { key: 'action', label: '操作', width: '140', slot: 'action' },
  { prop: 'target_type', label: '目标类型', width: '112' },
  { key: 'status', label: '状态', width: '72', slot: 'status' },
  { key: 'created_at', label: '时间', width: '176', slot: 'created_at', prop: 'created_at' },
];

const actionLabels = {
  'knowledgebase.ingest': '知识入库',
  'risk.extract': '风险提取',
  'risk.extract.retry': '重试风险提取',
  'risk.batch_extract': '批量风险提取',
  'risk.batch_extract.retry': '重试批量提取',
  'risk.sentiment': '舆情分析',
};
const formatAction = (action) => actionLabels[action] || action || '--';

const statusLabels = { succeeded: '成功', failed: '失败', pending: '待处理' };
const statusTypes = { succeeded: 'success', failed: 'danger', pending: 'info' };

const statusItems = computed(() => [
  {
    key: 'total',
    label: '操作记录',
    value: total.value || audits.value.length,
  },
  {
    key: 'failed',
    label: '失败记录',
    value: audits.value.filter((item) => item.status === 'failed').length,
  },
  {
    key: 'actors',
    label: '操作人员',
    value: new Set(audits.value.map((item) => item.actor_name).filter(Boolean)).size,
  },
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
    errorMsg.value = err.message || '加载操作日志失败';
  } finally {
    isLoading.value = false;
  }
};

const pad = (n) => String(n).padStart(2, '0');
const formatTime = (iso) => {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
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
    title="操作日志"
    summary=""
  >
    <template #status-band>
      <OpsStatusBand :items="statusItems" :style="{ '--band-columns': '3' }" />
    </template>

    <AppSectionCard title="审计流水" admin>
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
          <span>{{ formatAction(row.action) }}</span>
        </template>

        <template #status="{ row }">
          <el-tag :type="statusTypes[row.status] || 'info'" size="small" effect="plain">
            {{ statusLabels[row.status] || row.status }}
          </el-tag>
        </template>

        <template #created_at="{ row }">
          <span>{{ formatTime(row.created_at) }}</span>
        </template>
      </AdminDataTable>
    </AppSectionCard>
  </OpsSectionFrame>
</template>
