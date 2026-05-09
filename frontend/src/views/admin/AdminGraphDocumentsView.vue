<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { knowledgeGraphApi } from '../../api/knowledge-graph.js';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import { getKnowledgeGraphStatusTone } from '../../lib/knowledge-graph-workspace.js';
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
const isLoading = ref(false);
const isUploading = ref(false);
const isRunningAction = ref(false);
const errorMsg = ref('');
const documents = ref([]);
const selectedFile = ref(null);
const fileInputRef = ref(null);
const statusCounts = ref({});
const sortField = ref('updated_at');
const sortDirection = ref('desc');

const pager = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
});

const pageSummary = computed(() => {
  const totalPages = Math.max(1, Math.ceil((pager.total || 0) / pager.pageSize));
  return `${pager.page} / ${totalPages}`;
});

const loadDocuments = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
      const [counts, page] = await Promise.all([
      knowledgeGraphApi.getStatusCounts(),
      knowledgeGraphApi.listDocuments({
        page: pager.page,
        pageSize: pager.pageSize,
        sortField: sortField.value,
        sortDirection: sortDirection.value,
      }),
    ]);
    statusCounts.value = counts.status_counts || {};
    documents.value = page.documents;
    pager.total = page.pagination.total_count || 0;
  } catch (error) {
    errorMsg.value = error.message || '加载图谱文档失败。';
  } finally {
    isLoading.value = false;
  }
};

const handleSortChange = ({ prop, order }) => {
  const fieldMap = {
    title: 'title',
    status: 'status',
    updatedAt: 'updated_at',
  };
  sortField.value = fieldMap[prop] || 'updated_at';
  sortDirection.value = order === 'ascending' ? 'asc' : 'desc';
  pager.page = 1;
  loadDocuments();
};

const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] || null;
  if (selectedFile.value) {
    uploadFile();
  }
};

const handleUploadClick = () => {
  if (!selectedFile.value) {
    fileInputRef.value?.click();
    return;
  }
  uploadFile();
};

const uploadFile = async () => {
  if (!selectedFile.value) {
    return;
  }
  isUploading.value = true;
  errorMsg.value = '';
  try {
    await knowledgeGraphApi.uploadDocument(selectedFile.value);
    flash.success('文档已提交到知识图谱管线。');
    selectedFile.value = null;
    await loadDocuments();
  } catch (error) {
    errorMsg.value = error.message || '上传文档失败。';
  } finally {
    isUploading.value = false;
  }
};

const runAction = async (action, successMessage) => {
  isRunningAction.value = true;
  errorMsg.value = '';
  try {
    await action();
    flash.success(successMessage);
    await loadDocuments();
  } catch (error) {
    errorMsg.value = error.message || '操作失败。';
  } finally {
    isRunningAction.value = false;
  }
};

const deleteDocument = async (row) => {
  const docId = row.docId || row.raw?.doc_id;
  if (!docId) {
    flash.warning('该文档没有可删除的 doc_id。');
    return;
  }
  await runAction(
    () => knowledgeGraphApi.deleteDocument([docId]),
    '文档删除请求已提交。',
  );
};

const handlePageChange = (page) => {
  pager.page = page;
  loadDocuments();
};

onMounted(loadDocuments);
</script>

<template>
  <div class="graph-documents">
    <AppSectionCard title="已上传文档" admin>
      <template #header>
        <div class="graph-documents__toolbar">
          <div class="graph-documents__status-chips">
            <span
              v-for="(count, status) in statusCounts"
              :key="status"
              :class="['graph-documents__status-chip', `graph-documents__status-chip--${getKnowledgeGraphStatusTone(status)}`]"
            >
              {{ status }}: {{ count }}
            </span>
          </div>
          <div class="graph-documents__actions">
            <el-button :loading="isRunningAction" @click="runAction(() => knowledgeGraphApi.scanDocuments(), '已触发目录扫描。')">扫描</el-button>
            <el-button :loading="isRunningAction" @click="runAction(() => knowledgeGraphApi.reprocessFailedDocuments(), '已重新触发失败任务。')">重试</el-button>
            <el-button @click="runAction(() => knowledgeGraphApi.clearCache(), '已清理缓存。')">清空</el-button>
            <input ref="fileInputRef" type="file" style="display: none;" @change="handleFileChange" />
            <el-button type="primary" :loading="isUploading" @click="handleUploadClick">
              {{ selectedFile ? '上传' : '选择文件' }}
            </el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" style="margin-bottom: 12px;" />

      <el-table
        v-loading="isLoading"
        :data="documents"
        row-key="id"
        highlight-current-row
        @sort-change="handleSortChange"
      >
        <el-table-column label="文档" min-width="280" sortable="custom" prop="title">
          <template #default="{ row }">
            <div class="graph-documents__title-cell">
              <strong>{{ row.title }}</strong>
              <p v-if="row.summary">{{ row.summary }}</p>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" sortable="custom" prop="status">
          <template #default="{ row }">
              <span :class="['graph-documents__status-pill', `graph-documents__status-pill--${getKnowledgeGraphStatusTone(row.status)}`]">
              {{ row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Track ID" min-width="160">
          <template #default="{ row }">
            <span class="mono-text">{{ row.trackId || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="160" sortable="custom" prop="updatedAt">
          <template #default="{ row }">
            <span>{{ row.updatedAt || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="right">
          <template #default="{ row }">
            <el-button text @click="deleteDocument(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="graph-documents__footer">
        <span class="graph-documents__page-info">共 {{ pager.total }} 条，{{ pageSummary }}</span>
        <el-pagination
          layout="prev, pager, next"
          :current-page="pager.page"
          :page-size="pager.pageSize"
          :total="pager.total"
          @current-change="handlePageChange"
        />
      </div>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.graph-documents {
  display: grid;
  gap: 18px;
}

.graph-documents__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.graph-documents__status-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.graph-documents__status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.graph-documents__status-chip--success {
  background: var(--success-50);
  color: var(--success);
}

.graph-documents__status-chip--brand {
  background: var(--brand-soft);
  color: var(--brand);
}

.graph-documents__status-chip--warning {
  background: var(--warning-50);
  color: var(--warning);
}

.graph-documents__status-chip--risk {
  background: var(--risk-50);
  color: var(--risk);
}

.graph-documents__status-chip--muted {
  background: var(--surface-3);
  color: var(--text-muted);
}

.graph-documents__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.graph-documents__title-cell {
  display: grid;
  gap: 2px;
}

.graph-documents__title-cell strong {
  color: var(--text-primary);
}

.graph-documents__title-cell p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.graph-documents__status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 600;
}

.graph-documents__status-pill--success {
  background: var(--success-50);
  color: var(--success);
}

.graph-documents__status-pill--brand {
  background: var(--brand-soft);
  color: var(--brand);
}

.graph-documents__status-pill--warning {
  background: var(--warning-50);
  color: var(--warning);
}

.graph-documents__status-pill--risk {
  background: var(--risk-50);
  color: var(--risk);
}

.graph-documents__status-pill--muted {
  background: var(--surface-3);
  color: var(--text-muted);
}

.graph-documents__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
}

.graph-documents__page-info {
  color: var(--text-muted);
  font-size: 0.8125rem;
}
</style>
