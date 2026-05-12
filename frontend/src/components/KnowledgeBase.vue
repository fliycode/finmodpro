<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { kbApi } from '../api/knowledgebase.js';
import { ElMessageBox } from 'element-plus';
import KnowledgeBaseTable from './knowledgebase/KnowledgeBaseTable.vue';
import KnowledgeBaseToolbar from './knowledgebase/KnowledgeBaseToolbar.vue';
import KnowledgeBaseMetricsRail from './knowledgebase/KnowledgeBaseMetricsRail.vue';
import AppIcon from './ui/AppIcon.vue';
import AppSectionCard from './ui/AppSectionCard.vue';
import { useFlash } from '../lib/flash.js';
import { isIngestionInFlight } from '../lib/knowledgebase-actions.js';
import {
  buildNextSelection,
  buildSelectionAfterBatchDelete,
  summarizeBatchResult,
} from '../lib/knowledgebase-workspace.js';

const props = defineProps({
  showAdminMetrics: {
    type: Boolean,
    default: false,
  },
});

const router = useRouter();

const detailRoutePrefix = computed(() =>
  props.showAdminMetrics ? '/admin/knowledge' : '/workspace/knowledge',
);

const items = ref([]);
const isLoading = ref(false);
const isUploading = ref(false);
const isSubmittingTask = ref(false);
const isLoadingDatasets = ref(false);
const isCreatingDataset = ref(false);
const isDatasetComposerOpen = ref(false);
const isUploadDialogOpen = ref(false);
const uploadSelectedDatasetId = ref('');
const selectedDatasetId = ref('all');
const searchKeyword = ref('');
const statusFilter = ref('all');
const timeRange = ref('all');
const checkedDocumentIds = ref([]);
const fileInput = ref(null);
const currentPage = ref(1);
const pagination = ref({ total: 0, page: 1, pageSize: 10, totalPages: 0 });
const datasets = ref([]);
const stats = ref({
  total_datasets: 0,
  total_documents: 0,
  total_vectors: 0,
  total_storage_bytes: 0,
  total_storage_formatted: '0 B',
  indexed_count: 0,
  failed_count: 0,
  processing_count: 0,
  ready_rate: '0%',
});
const isLoadingStats = ref(false);
const datasetForm = ref({
  name: '',
  description: '',
});
const flash = useFlash();

let pollInterval = null;

const statusTone = {
  uploaded: 'neutral',
  queued: 'neutral',
  parsing: 'accent',
  chunking: 'accent',
  indexing: 'accent',
  indexed: 'success',
  failed: 'danger',
};

const decoratedItems = computed(() =>
  items.value.map((item) => ({
    ...item,
    statusTone: statusTone[item.processStep?.code] || 'neutral',
  })),
);

const activeProcessingCount = computed(() =>
  items.value.filter((item) => isIngestionInFlight(item)).length,
);

const activeDataset = computed(() =>
  datasets.value.find((dataset) => String(dataset.id) === String(selectedDatasetId.value)) || null,
);

const selectedDatasetLabel = computed(() => activeDataset.value?.name || '全部数据集');

const summaryCards = computed(() => (
  props.showAdminMetrics
    ? [
      {
        id: 'datasets',
        label: '数据集总数',
        value: stats.value.total_datasets,
        tone: 'violet',
        icon: 'layers',
      },
      {
        id: 'documents',
        label: '文档总数',
        value: stats.value.total_documents,
        tone: 'blue',
        icon: 'file-text',
      },
      {
        id: 'processing',
        label: '处理中任务',
        value: stats.value.processing_count,
        delta: activeProcessingCount.value > 0 ? `当前筛选内 ${activeProcessingCount.value} 个活动任务` : '当前筛选内无活动任务',
        tone: 'amber',
        icon: 'activity',
      },
      {
        id: 'failed',
        label: '失败文档',
        value: stats.value.failed_count,
        delta: stats.value.failed_count > 0 ? '建议优先回到明细排查失败步骤' : '当前没有失败文档',
        tone: 'red',
        icon: 'alert-triangle',
      },
      {
        id: 'vectors',
        label: '向量总数',
        value: Number(stats.value.total_vectors || 0).toLocaleString('zh-CN'),
        tone: 'green',
        icon: 'zap',
      },
      {
        id: 'ready',
        label: '可检索率',
        value: stats.value.ready_rate,
        delta: `${stats.value.indexed_count} 个已入库`,
        tone: 'purple',
        icon: 'check',
      },
    ]
    : [
      {
        id: 'datasets',
        label: '数据集总数',
        value: stats.value.total_datasets,
        tone: 'violet',
        icon: 'layers',
      },
      {
        id: 'documents',
        label: '文档总数',
        value: stats.value.total_documents,
        tone: 'blue',
        icon: 'file-text',
      },
      {
        id: 'storage',
        label: '数据总量',
        value: stats.value.total_storage_formatted,
        tone: 'green',
        icon: 'database',
      },
      {
        id: 'vectors',
        label: '向量总数',
        value: Number(stats.value.total_vectors || 0).toLocaleString('zh-CN'),
        tone: 'amber',
        icon: 'zap',
      },
      {
        id: 'ready',
        label: '可检索率',
        value: stats.value.ready_rate,
        delta: `${stats.value.failed_count} 个失败`,
        tone: 'purple',
        icon: 'check',
      },
    ]
));

const adminSummaryMeta = computed(() => [
  `当前范围：${selectedDatasetLabel.value}`,
  `失败文档：${stats.value.failed_count}`,
]);

const adminLedgerMeta = computed(() => [
  `筛选结果：${pagination.value.total || 0} 条`,
  checkedDocumentIds.value.length > 0 ? `已选：${checkedDocumentIds.value.length} 个文档` : '已选：0 个文档',
  activeProcessingCount.value > 0 ? '当前筛选范围已启用轮询' : '当前筛选范围无活动任务',
]);

const shouldPoll = computed(() => (
  props.showAdminMetrics
    ? Number(stats.value.processing_count || 0) > 0 || activeProcessingCount.value > 0
    : activeProcessingCount.value > 0
));

const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    const result = await kbApi.listDatasets();
    datasets.value = result.datasets || [];
    if (
      selectedDatasetId.value !== 'all'
      && !datasets.value.some((dataset) => String(dataset.id) === String(selectedDatasetId.value))
    ) {
      selectedDatasetId.value = 'all';
    }
  } catch (error) {
    console.error('加载数据集失败:', error);
    flash.error(`加载数据集失败：${error.message || '未知错误'}`);
  } finally {
    isLoadingDatasets.value = false;
  }
};

const fetchStats = async () => {
  isLoadingStats.value = true;
  try {
    stats.value = await kbApi.getStats();
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    isLoadingStats.value = false;
  }
};

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    const result = await kbApi.listDocuments({
      searchKeyword: searchKeyword.value,
      statusFilter: statusFilter.value,
      timeRange: timeRange.value,
      datasetId: selectedDatasetId.value,
      page: currentPage.value,
      pageSize: pagination.value.pageSize,
    });

    items.value = result.documents || [];
    pagination.value = {
      total: result.total || 0,
      page: result.page || currentPage.value,
      pageSize: result.pageSize || pagination.value.pageSize,
      totalPages: result.totalPages || 0,
    };
    currentPage.value = pagination.value.page;
    checkedDocumentIds.value = checkedDocumentIds.value.filter((id) => items.value.some((item) => item.id === id));
  } catch (error) {
    console.error('加载知识库失败:', error);
    flash.error(`加载知识库失败：${error.message || '未知错误'}`);
  } finally {
    isLoading.value = false;
  }
};

const navigateToDetail = (item) => {
  router.push(`${detailRoutePrefix.value}/documents/${item.id}`);
};

const triggerUpload = () => {
  if (selectedDatasetId.value !== 'all') {
    uploadSelectedDatasetId.value = selectedDatasetId.value;
  } else if (datasets.value.length > 0) {
    uploadSelectedDatasetId.value = String(datasets.value[0].id);
  } else {
    uploadSelectedDatasetId.value = '';
  }
  isUploadDialogOpen.value = true;
};

const confirmUploadDataset = () => {
  isUploadDialogOpen.value = false;
  fileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  const datasetId = uploadSelectedDatasetId.value || undefined;
  isUploading.value = true;
  try {
    const uploadResult = await kbApi.uploadDocument(file, { datasetId });
    const datasetName = datasetId
      ? datasets.value.find((dataset) => String(dataset.id) === String(datasetId))?.name
      : null;
    flash.success(
      datasetName
        ? `文件已上传到"${datasetName}"。请启动入库任务。`
        : '文件已上传。请启动入库任务，后台会异步完成解析、切块和向量化。',
    );
    if (uploadResult.document?.id) {
      router.push(`${detailRoutePrefix.value}/documents/${uploadResult.document.id}`);
      return;
    }
    await fetchDatasets();
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    if (error.code === 'DUPLICATE' && error.existingDocument) {
      try {
        await ElMessageBox.confirm(
          `文件已存在（《${error.existingDocument.title}》），是否作为新版本上传？`,
          '文件重复',
          { confirmButtonText: '上传新版本', cancelButtonText: '取消', type: 'info' },
        );
      } catch {
        return;
      }
      try {
        const versionResult = await kbApi.uploadNewVersion(error.existingDocument.id, file, {
          title: file.name,
          sourceLabel: file.name,
        });
        flash.success('新版本已上传。');
        if (versionResult.document?.id) {
          router.push(`${detailRoutePrefix.value}/documents/${versionResult.document.id}`);
          return;
        }
        await fetchDatasets();
        await fetchDocuments();
        await fetchStats();
      } catch (versionError) {
        flash.error(`上传新版本失败：${versionError.message || '未知错误'}`);
      }
      return;
    }
    console.error('上传文档失败:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const createDataset = async () => {
  if (!datasetForm.value.name.trim()) {
    flash.error('请输入数据集名称。');
    return;
  }

  isCreatingDataset.value = true;
  try {
    const dataset = await kbApi.createDataset(datasetForm.value);
    flash.success(`数据集"${dataset.name}"已创建。`);
    datasetForm.value = { name: '', description: '' };
    isDatasetComposerOpen.value = false;
    await fetchDatasets();
    selectedDatasetId.value = String(dataset.id);
    currentPage.value = 1;
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    console.error('创建数据集失败:', error);
    flash.error(`创建数据集失败：${error.message || '未知错误'}`);
  } finally {
    isCreatingDataset.value = false;
  }
};

const startIngestionForDocument = async (documentId) => {
  if (!documentId || isSubmittingTask.value) return;

  isSubmittingTask.value = true;
  try {
    const ingestResult = await kbApi.ingestDocument(documentId);
    flash.success(ingestResult.message || '入库任务已提交。');
    await fetchDocuments();
  } catch (error) {
    console.error('启动入库任务失败:', error);
    flash.error(`启动入库失败：${error.message || '未知错误'}`);
  } finally {
    isSubmittingTask.value = false;
  }
};

const handleRowAction = async ({ item, action }) => {
  if (action === 'view-detail') {
    navigateToDetail(item);
    return;
  }
  if (action === 'reingest') {
    await startIngestionForDocument(item.id);
    return;
  }
  if (action === 'delete') {
    try {
      await ElMessageBox.confirm(
        `确认删除文档"${item.title}"吗？删除后不可恢复。`,
        '删除文档',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
      );
    } catch {
      return;
    }
    try {
      await kbApi.deleteDocument(item.id);
      flash.success(`文档"${item.title}"已删除。`);
      await fetchDocuments();
      await fetchStats();
    } catch (error) {
      flash.error(`删除失败：${error.message || '未知错误'}`);
    }
  }
};

const toggleRow = (documentId) => {
  checkedDocumentIds.value = buildNextSelection({
    selectedIds: checkedDocumentIds.value,
    toggledId: documentId,
  });
};

const toggleAll = () => {
  if (decoratedItems.value.length === 0) {
    checkedDocumentIds.value = [];
    return;
  }

  const allIds = decoratedItems.value.map((item) => item.id);
  const allChecked = allIds.every((id) => checkedDocumentIds.value.includes(id));
  checkedDocumentIds.value = allChecked ? [] : allIds;
};

const changePage = async (page) => {
  currentPage.value = page;
  await fetchDocuments();
};

const handleBatchIngest = async () => {
  if (checkedDocumentIds.value.length === 0) return;

  try {
    const payload = await kbApi.batchIngestDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量重新入库'));
    await fetchDocuments();
  } catch (error) {
    console.error('批量入库失败:', error);
    flash.error(`批量入库失败：${error.message || '未知错误'}`);
  }
};

const handleBatchDelete = async () => {
  if (checkedDocumentIds.value.length === 0) return;
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${checkedDocumentIds.value.length} 个文档吗？删除后不可恢复。`,
      '批量删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    const payload = await kbApi.batchDeleteDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量删除'));
    const deletedIds = (payload.results || [])
      .filter((item) => item.status === 'deleted')
      .map((item) => item.document_id);
    checkedDocumentIds.value = buildSelectionAfterBatchDelete(checkedDocumentIds.value, deletedIds);
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    console.error('批量删除失败:', error);
    flash.error(`批量删除失败：${error.message || '未知错误'}`);
  }
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    if (!shouldPoll.value) return;
    try {
      await fetchDocuments();
      await fetchStats();
    } catch (error) {
      console.error('轮询知识库失败:', error);
    }
  }, 3000);
};

watch([searchKeyword, statusFilter, timeRange, selectedDatasetId], async () => {
  currentPage.value = 1;
  await fetchDocuments();
});

onMounted(async () => {
  await fetchDatasets();
  await fetchDocuments();
  await fetchStats();
  startPolling();
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<template>
  <div :class="['kb-page', { 'kb-page--admin': showAdminMetrics }]">
    <input ref="fileInput" type="file" hidden @change="handleFileChange" />

    <Teleport to="body">
      <div v-if="isUploadDialogOpen" class="kb-dialog-overlay" @click.self="isUploadDialogOpen = false">
        <div class="kb-dialog">
          <h3>选择目标数据集</h3>
          <p class="kb-dialog__desc">上传的文档将归入所选数据集，也可稍后在文档详情中修改。</p>
          <div class="kb-dialog__datasets">
            <button
              v-for="ds in datasets"
              :key="ds.id"
              type="button"
              :class="['kb-dataset-option', { active: String(uploadSelectedDatasetId) === String(ds.id) }]"
              @click="uploadSelectedDatasetId = String(ds.id)"
            >
              <span class="kb-dataset-option__name">{{ ds.name }}</span>
              <span class="kb-dataset-option__hint">{{ ds.documentCount ?? 0 }} 个文档</span>
            </button>
            <button
              type="button"
              :class="['kb-dataset-option', { active: !uploadSelectedDatasetId }]"
              @click="uploadSelectedDatasetId = ''"
            >
              <span class="kb-dataset-option__name">不指定数据集</span>
              <span class="kb-dataset-option__hint">文档将归入“未分组”</span>
            </button>
          </div>
          <div class="kb-dialog__actions">
            <button class="kb-secondary-btn" @click="isUploadDialogOpen = false">取消</button>
            <button class="kb-primary-btn" @click="confirmUploadDataset">选择文件上传</button>
          </div>
        </div>
      </div>
    </Teleport>

    <template v-if="showAdminMetrics">
      <AppSectionCard
        admin
        title="知识资产治理摘要"
        desc="保留最关键的六个判断：规模、健康度、处理中任务、失败文档、向量量级和检索就绪率。"
      >
        <template #header>
          <div class="kb-admin-pillbar">
            <span v-for="item in adminSummaryMeta" :key="item" class="kb-admin-pill">{{ item }}</span>
          </div>
        </template>

        <div class="kb-overview__stats kb-overview__stats--admin">
          <article
            v-for="card in summaryCards"
            :key="card.id"
            :class="['stat-card', `stat-card--${card.tone}`]"
          >
            <span class="stat-card__icon" aria-hidden="true">
              <AppIcon :name="card.icon" :width="20" :height="20" />
            </span>
            <div class="stat-card__body">
              <span class="stat-label">{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <small v-if="card.delta">{{ card.delta }}</small>
            </div>
          </article>
        </div>
      </AppSectionCard>

      <section class="kb-admin-layout">
        <AppSectionCard
          admin
          title="知识资产台账"
          desc="按数据集、状态和时间筛选文档，并在同一处完成上传、批量入库和批量删除。"
          class="kb-admin-main"
        >
          <template #header>
            <div class="kb-admin-pillbar kb-admin-pillbar--muted">
              <span v-for="item in adminLedgerMeta" :key="item" class="kb-admin-pill">{{ item }}</span>
            </div>
          </template>

          <KnowledgeBaseToolbar
            :search-keyword="searchKeyword"
            :status-filter="statusFilter"
            :time-range="timeRange"
            :datasets="datasets"
            :selected-dataset-id="selectedDatasetId"
            :is-uploading="isUploading"
            @update:search-keyword="searchKeyword = $event"
            @update:status-filter="statusFilter = $event"
            @update:time-range="timeRange = $event"
            @update:selected-dataset-id="selectedDatasetId = $event"
            @create-dataset="isDatasetComposerOpen = !isDatasetComposerOpen"
            @upload="triggerUpload"
          />

          <section v-if="isDatasetComposerOpen" class="kb-dataset-composer kb-dataset-composer--admin">
            <div class="kb-dataset-composer__copy">
              <p class="eyebrow">Dataset composer</p>
              <h3>创建一个新的知识数据集</h3>
              <p>
                用于组织上传文档、限定检索范围，并为后续问答与风险抽取提供稳定的数据边界。
              </p>
            </div>
            <div class="kb-dataset-composer__form">
              <input
                v-model="datasetForm.name"
                class="kb-search"
                type="text"
                placeholder="例如：2025 年报数据集"
              />
              <textarea
                v-model="datasetForm.description"
                class="kb-textarea"
                rows="3"
                placeholder="补充该数据集的用途、来源或适用场景"
              />
              <div class="kb-dataset-composer__actions">
                <button
                  class="kb-secondary-btn"
                  :disabled="isCreatingDataset"
                  @click="isDatasetComposerOpen = false"
                >
                  取消
                </button>
                <button
                  class="kb-primary-btn"
                  :disabled="isCreatingDataset"
                  @click="createDataset"
                >
                  {{ isCreatingDataset ? '创建中...' : '创建数据集' }}
                </button>
              </div>
            </div>
          </section>

          <div v-if="checkedDocumentIds.length > 0" class="kb-batchbar kb-batchbar--admin">
            <span>已选择 {{ checkedDocumentIds.length }} 个文档</span>
            <div class="kb-batchbar__actions">
              <button class="kb-secondary-btn" @click="handleBatchIngest">批量重新入库</button>
              <button class="kb-danger-btn" @click="handleBatchDelete">批量删除</button>
            </div>
          </div>

          <KnowledgeBaseTable
            :items="decoratedItems"
            :checked-ids="checkedDocumentIds"
            :is-loading="isLoading"
            :page="pagination.page"
            :total-pages="pagination.totalPages"
            :total="pagination.total"
            @navigate="navigateToDetail"
            @toggle-row="toggleRow"
            @toggle-all="toggleAll"
            @row-action="handleRowAction"
            @change-page="changePage"
          />
        </AppSectionCard>

        <AppSectionCard
          admin
          title="治理巡检"
          desc="把存储、向量、数据集分布和最近活动固定在侧边，减少在主台账中来回跳转。"
          class="kb-admin-side"
        >
          <KnowledgeBaseMetricsRail
            :documents="decoratedItems"
            :datasets="datasets"
            :stats="stats"
            :total-documents="stats.total_documents"
            :active-count="stats.processing_count"
            :indexed-count="stats.indexed_count"
            :failed-count="stats.failed_count"
          />
        </AppSectionCard>
      </section>
    </template>

    <template v-else>
      <section class="kb-overview">
        <div class="kb-overview__stats">
          <article
            v-for="card in summaryCards"
            :key="card.id"
            :class="['stat-card', `stat-card--${card.tone}`]"
          >
            <span class="stat-card__icon" aria-hidden="true">
              <AppIcon :name="card.icon" :width="20" :height="20" />
            </span>
            <div class="stat-card__body">
              <span class="stat-label">{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <small v-if="card.delta">{{ card.delta }}</small>
            </div>
          </article>
        </div>
      </section>

      <section class="kb-ledger-panel">
        <KnowledgeBaseToolbar
          :search-keyword="searchKeyword"
          :status-filter="statusFilter"
          :time-range="timeRange"
          :datasets="datasets"
          :selected-dataset-id="selectedDatasetId"
          :is-uploading="isUploading"
          @update:search-keyword="searchKeyword = $event"
          @update:status-filter="statusFilter = $event"
          @update:time-range="timeRange = $event"
          @update:selected-dataset-id="selectedDatasetId = $event"
          @create-dataset="isDatasetComposerOpen = !isDatasetComposerOpen"
          @upload="triggerUpload"
        />

        <section v-if="isDatasetComposerOpen" class="kb-dataset-composer">
          <div class="kb-dataset-composer__copy">
            <p class="eyebrow">Dataset composer</p>
            <h3>创建一个新的知识数据集</h3>
            <p>
              用于组织上传文档、限定检索范围，并为后续问答与风险抽取提供稳定的数据边界。
            </p>
          </div>
          <div class="kb-dataset-composer__form">
            <input
              v-model="datasetForm.name"
              class="kb-search"
              type="text"
              placeholder="例如：2025 年报数据集"
            />
            <textarea
              v-model="datasetForm.description"
              class="kb-textarea"
              rows="3"
              placeholder="补充该数据集的用途、来源或适用场景"
            />
            <div class="kb-dataset-composer__actions">
              <button
                class="kb-secondary-btn"
                :disabled="isCreatingDataset"
                @click="isDatasetComposerOpen = false"
              >
                取消
              </button>
              <button
                class="kb-primary-btn"
                :disabled="isCreatingDataset"
                @click="createDataset"
              >
                {{ isCreatingDataset ? '创建中...' : '创建数据集' }}
              </button>
            </div>
          </div>
        </section>

        <div v-if="checkedDocumentIds.length > 0" class="kb-batchbar">
          <span>已选择 {{ checkedDocumentIds.length }} 个文档</span>
          <div class="kb-batchbar__actions">
            <button class="kb-secondary-btn" @click="handleBatchIngest">批量重新入库</button>
            <button class="kb-danger-btn" @click="handleBatchDelete">批量删除</button>
          </div>
        </div>

        <KnowledgeBaseTable
          :items="decoratedItems"
          :checked-ids="checkedDocumentIds"
          :is-loading="isLoading"
          :page="pagination.page"
          :total-pages="pagination.totalPages"
          :total="pagination.total"
          @navigate="navigateToDetail"
          @toggle-row="toggleRow"
          @toggle-all="toggleAll"
          @row-action="handleRowAction"
          @change-page="changePage"
        />
      </section>
    </template>
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  color: var(--text-secondary);
}

.kb-page--admin {
  gap: 20px;
}

.kb-admin-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.8fr);
  gap: 18px;
  align-items: start;
}

.kb-admin-pillbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.kb-admin-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--brand) 6%, var(--surface-3));
  color: var(--text-secondary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.kb-admin-pillbar--muted .kb-admin-pill {
  background: var(--surface-3);
}

.kb-overview {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.eyebrow {
  margin: 0 0 8px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brand);
}

.kb-overview h2,
.kb-dataset-composer h3 {
  margin: 0;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.kb-dataset-composer p {
  margin: 10px 0 0;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-secondary);
  line-height: 1.6;
}

.kb-overview__stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.kb-overview__stats--admin {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 82px;
  padding: 12px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface-2) 88%, var(--brand-soft));
}

.stat-card__icon {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--surface-3);
  color: var(--brand);
}

.stat-card--violet .stat-card__icon {
  background: rgba(68, 49, 141, 0.1);
  color: #44318d;
}

.stat-card--green .stat-card__icon {
  background: rgba(31, 122, 100, 0.1);
  color: #1f7a64;
}

.stat-card--amber .stat-card__icon {
  background: rgba(138, 90, 32, 0.1);
  color: #8a5a20;
}

.stat-card--purple .stat-card__icon {
  background: rgba(75, 53, 126, 0.1);
  color: #4b357e;
}

.stat-card--red .stat-card__icon {
  background: rgba(181, 58, 58, 0.12);
  color: #9b3131;
}

.stat-card__body {
  min-width: 0;
}

.stat-label {
  display: block;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

.stat-card strong {
  display: block;
  color: var(--text-primary);
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: clamp(17px, 1.8vw, 20px);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.stat-card small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  line-height: 1.5;
}

.kb-ledger-panel {
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.kb-dataset-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.95fr);
  gap: 20px;
  margin: 0 18px 18px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
}

.kb-dataset-composer--admin {
  margin: 0;
  padding: 20px;
  background: color-mix(in oklab, var(--brand) 2%, var(--surface-2));
  box-shadow: none;
}

.kb-dataset-composer__form {
  display: grid;
  gap: 12px;
}

.kb-search,
.kb-textarea {
  width: 100%;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  padding: 12px 14px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--surface-3);
}

.kb-textarea {
  resize: vertical;
}

.kb-dataset-composer__actions,
.kb-batchbar__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.kb-dataset-composer__actions {
  justify-content: flex-end;
}

.kb-batchbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  margin: 0 16px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.kb-batchbar--admin {
  margin: 0;
}

.kb-batchbar span {
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-weight: 600;
  font-size: 13px;
}

.kb-primary-btn,
.kb-secondary-btn,
.kb-danger-btn {
  min-height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.kb-primary-btn {
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
}

.kb-secondary-btn {
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  color: var(--text-primary);
}

.kb-danger-btn {
  border: 1px solid rgba(181, 58, 58, 0.18);
  background: rgba(181, 58, 58, 0.08);
  color: #9b3131;
}

.kb-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
}

.kb-dialog {
  width: min(440px, 90vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-lg);
}

.kb-dialog h3 {
  margin: 0;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-dialog__desc {
  margin: 0;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.kb-dialog__datasets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.kb-dataset-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.kb-dataset-option:hover {
  border-color: var(--brand-soft);
  background: var(--surface-3);
}

.kb-dataset-option.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}

.kb-dataset-option__name {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.kb-dataset-option__hint {
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: var(--text-muted);
}

.kb-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1180px) {
  .kb-admin-layout,
  .kb-dataset-composer {
    grid-template-columns: 1fr;
  }

  .kb-overview__stats,
  .kb-overview__stats--admin {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kb-admin-pillbar {
    justify-content: flex-start;
  }

  .kb-overview__stats,
  .kb-overview__stats--admin {
    grid-template-columns: 1fr;
  }

  .kb-batchbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
