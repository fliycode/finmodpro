<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import LightragWorkspaceShell from '../../components/lightrag/LightragWorkspaceShell.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import { getLightragStatusTone } from '../../lib/lightrag-workspace.js';
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
const errorMsg = ref('');
const isLoading = ref(false);
const isUploading = ref(false);
const isRunningAction = ref(false);
const selectedFile = ref(null);
const selectedDocumentId = ref('');
const lastLoadedAt = ref('');
const documents = ref([]);
const statusCounts = ref({});
const trackStatus = ref(null);

const pager = reactive({
  page: 1,
  pageSize: 12,
  total: 0,
});

const trackId = ref('');

const statusItems = computed(() => ([
  { label: '总文档', value: statusCounts.value.all ?? 0 },
  { label: '处理中', value: statusCounts.value.processing ?? 0 },
  { label: '失败', value: statusCounts.value.failed ?? 0 },
  { label: '已完成', value: statusCounts.value.processed ?? 0 },
]));
const selectedDocument = computed(() => documents.value.find((row) => row.id === selectedDocumentId.value) || null);
const pageSummary = computed(() => {
  const totalPages = Math.max(1, Math.ceil((pager.total || 0) / pager.pageSize));
  return `${pager.page} / ${totalPages}`;
});
const trackDocuments = computed(() => (Array.isArray(trackStatus.value?.documents) ? trackStatus.value.documents : []));

watch(documents, (rows) => {
  if (!rows.length) {
    selectedDocumentId.value = '';
    return;
  }
  if (!rows.some((row) => row.id === selectedDocumentId.value)) {
    selectedDocumentId.value = rows[0].id;
  }
}, { immediate: true });

const loadDocuments = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const [counts, page] = await Promise.all([
      lightragApi.getStatusCounts(),
      lightragApi.listDocuments({ page: pager.page, pageSize: pager.pageSize }),
    ]);
    statusCounts.value = counts.status_counts || {};
    documents.value = page.documents;
    pager.total = page.pagination.total_count || 0;
    lastLoadedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载图谱文档管线失败。';
  } finally {
    isLoading.value = false;
  }
};

const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] || null;
};

const handleUpload = async () => {
  if (!selectedFile.value) {
    flash.warning('请先选择要上传的文件。');
    return;
  }
  isUploading.value = true;
  errorMsg.value = '';
  try {
    const payload = await lightragApi.uploadDocument(selectedFile.value);
    flash.success(payload.message || '文档已提交到 LightRAG。');
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
    errorMsg.value = error.message || '执行文档动作失败。';
  } finally {
    isRunningAction.value = false;
  }
};

const handleTrackStatus = async () => {
  if (!trackId.value.trim()) {
    flash.warning('请输入 track id。');
    return;
  }
  isRunningAction.value = true;
  errorMsg.value = '';
  try {
    trackStatus.value = await lightragApi.getTrackStatus(trackId.value.trim());
  } catch (error) {
    errorMsg.value = error.message || '查询 track status 失败。';
  } finally {
    isRunningAction.value = false;
  }
};

const inspectSelectedTrack = async () => {
  if (!selectedDocument.value?.trackId) {
    flash.warning('当前文档没有可追踪的 track id。');
    return;
  }
  trackId.value = selectedDocument.value.trackId;
  await handleTrackStatus();
};

const deleteDocument = async (row) => {
  const docId = row.docId || row.raw?.doc_id;
  if (!docId) {
    flash.warning('该文档没有可删除的 doc_id。');
    return;
  }
  await runAction(
    () => lightragApi.deleteDocument([docId]),
    '文档删除请求已提交。',
  );
};

const selectDocument = (row) => {
  selectedDocumentId.value = row.id;
};

const handlePageChange = async (page) => {
  pager.page = page;
  await loadDocuments();
};

const handleMaintenanceCommand = async (command) => {
  if (command === 'reprocess') {
    await runAction(() => lightragApi.reprocessFailedDocuments(), '已重新触发失败任务。');
    return;
  }
  if (command === 'clear-cache') {
    await runAction(() => lightragApi.clearCache(), '已清理 LightRAG 缓存。');
    return;
  }
  if (command === 'cancel') {
    await runAction(() => lightragApi.cancelPipeline(), '已发出取消管线请求。');
  }
};

onMounted(loadDocuments);
</script>

<template>
  <LightragWorkspaceShell :status-items="statusItems">
    <template #aside>
      <span>最近刷新：{{ lastLoadedAt || '尚未刷新' }}</span>
      <span>当前分页：{{ pageSummary }}</span>
    </template>
    <template #actions>
      <el-button :loading="isLoading" @click="loadDocuments">刷新队列</el-button>
    </template>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard title="入库动作" desc="上传和扫描保留在前台，维护动作收进二级入口，避免工具区变成按钮墙。" admin>
      <div class="lightrag-documents__toolbar">
        <label class="lightrag-documents__file-picker">
          <input type="file" @change="handleFileChange" />
          <span>{{ selectedFile?.name || '选择待入库文件' }}</span>
        </label>

        <div class="lightrag-documents__toolbar-actions">
          <el-button type="primary" :loading="isUploading" @click="handleUpload">上传文档</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.scanDocuments(), '已触发目录扫描。')">扫描目录</el-button>
          <el-dropdown @command="handleMaintenanceCommand">
            <el-button>维护操作</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="reprocess">重跑失败任务</el-dropdown-item>
                <el-dropdown-item command="clear-cache">清理缓存</el-dropdown-item>
                <el-dropdown-item command="cancel">取消当前管线</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </AppSectionCard>

    <div class="lightrag-documents">
      <AppSectionCard title="文档队列" :desc="`当前分页已载入 ${documents.length} 条，LightRAG 返回总数 ${pager.total}。`" admin>
        <el-table
          v-if="documents.length"
          :data="documents"
          row-key="id"
          highlight-current-row
          :current-row-key="selectedDocumentId"
          @row-click="selectDocument"
        >
          <el-table-column label="文档" min-width="260">
            <template #default="{ row }">
              <div class="lightrag-documents__title-cell">
                <strong>{{ row.title }}</strong>
                <p>{{ row.summary || '当前文档未返回额外摘要。' }}</p>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <span :class="['lightrag-documents__status-pill', `lightrag-documents__status-pill--${getLightragStatusTone(row.status)}`]">
                {{ row.status }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="Track ID" min-width="140">
            <template #default="{ row }">
              <span class="mono-text">{{ row.trackId || '未提供' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="160">
            <template #default="{ row }">
              <span>{{ row.updatedAt || '未提供' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="right">
            <template #default="{ row }">
              <el-button text @click.stop="deleteDocument(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="admin-empty-state">当前还没有进入 LightRAG 的文档。</div>

        <div class="lightrag-documents__pagination">
          <el-pagination
            layout="prev, pager, next"
            :current-page="pager.page"
            :page-size="pager.pageSize"
            :total="pager.total"
            @current-change="handlePageChange"
          />
        </div>
      </AppSectionCard>

      <AppSectionCard title="任务检查器" desc="先选一条文档，再按 track id 看它卡在哪一步。" admin>
        <div class="lightrag-documents__inspector">
          <div class="lightrag-documents__track-search">
            <el-input v-model="trackId" placeholder="输入 track id" />
            <el-button :loading="isRunningAction" @click="handleTrackStatus">查询轨迹</el-button>
          </div>

          <div v-if="selectedDocument" class="lightrag-documents__document-summary">
            <div class="lightrag-documents__document-head">
              <strong>{{ selectedDocument.title }}</strong>
              <span :class="['lightrag-documents__status-pill', `lightrag-documents__status-pill--${getLightragStatusTone(selectedDocument.status)}`]">
                {{ selectedDocument.status }}
              </span>
            </div>
            <p>{{ selectedDocument.summary || '当前文档没有返回额外摘要。' }}</p>
            <dl class="lightrag-documents__facts">
              <div>
                <dt>doc_id</dt>
                <dd>{{ selectedDocument.docId || '未提供' }}</dd>
              </div>
              <div>
                <dt>track_id</dt>
                <dd>{{ selectedDocument.trackId || '未提供' }}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{{ selectedDocument.updatedAt || '未提供' }}</dd>
              </div>
            </dl>
            <div class="lightrag-documents__document-actions">
              <el-button @click="inspectSelectedTrack">查看处理轨迹</el-button>
            </div>
          </div>

          <div v-if="trackStatus" class="lightrag-documents__track-result">
            <div class="lightrag-documents__track-summary">
              <span>关联文档：{{ trackStatus.total_count || 0 }}</span>
              <span>状态摘要：{{ JSON.stringify(trackStatus.status_summary || {}) }}</span>
            </div>

            <div class="lightrag-documents__track-documents">
              <article
                v-for="(item, index) in trackDocuments"
                :key="index"
                class="lightrag-documents__track-card"
              >
                <div class="lightrag-documents__track-card-head">
                  <strong>{{ item.file_path || item.file_name || item.doc_id || `文档 ${index + 1}` }}</strong>
                  <span>{{ item.status || '未知状态' }}</span>
                </div>
                <p>{{ item.message || item.error_msg || item.summary || '当前任务没有返回额外说明。' }}</p>
              </article>
            </div>
          </div>
        </div>
      </AppSectionCard>
    </div>
  </LightragWorkspaceShell>
</template>

<style scoped>
.lightrag-documents,
.lightrag-documents__inspector,
.lightrag-documents__document-summary,
.lightrag-documents__track-documents {
  display: grid;
  gap: 16px;
}

.lightrag-documents {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.85fr);
  gap: 18px;
}

.lightrag-documents__toolbar,
.lightrag-documents__toolbar-actions,
.lightrag-documents__track-search,
.lightrag-documents__track-summary,
.lightrag-documents__document-head,
.lightrag-documents__document-actions,
.lightrag-documents__track-card-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-documents__toolbar {
  justify-content: space-between;
}

.lightrag-documents__file-picker {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0 14px;
  border: 1px dashed var(--line-strong);
  border-radius: 12px;
  background: var(--surface-3);
  color: var(--text-secondary);
  cursor: pointer;
}

.lightrag-documents__file-picker input {
  display: none;
}

.lightrag-documents__title-cell {
  display: grid;
  gap: 4px;
}

.lightrag-documents__title-cell strong,
.lightrag-documents__document-head strong,
.lightrag-documents__track-card-head strong {
  color: var(--text-primary);
}

.lightrag-documents__title-cell p,
.lightrag-documents__document-summary p,
.lightrag-documents__track-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.lightrag-documents__pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}

.lightrag-documents__status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.lightrag-documents__status-pill--success {
  background: var(--success-50);
  color: var(--success);
}

.lightrag-documents__status-pill--brand {
  background: var(--brand-soft);
  color: var(--brand);
}

.lightrag-documents__status-pill--warning {
  background: var(--warning-50);
  color: var(--warning);
}

.lightrag-documents__status-pill--risk {
  background: var(--risk-50);
  color: var(--risk);
}

.lightrag-documents__status-pill--muted {
  background: var(--surface-3);
  color: var(--text-muted);
}

.lightrag-documents__facts {
  display: grid;
  gap: 10px;
  margin: 0;
}

.lightrag-documents__facts div {
  display: grid;
  gap: 2px;
}

.lightrag-documents__facts dt {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-documents__facts dd {
  margin: 0;
  color: var(--text-primary);
}

.lightrag-documents__track-result,
.lightrag-documents__track-card {
  display: grid;
  gap: 12px;
}

.lightrag-documents__track-card {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.lightrag-documents__track-summary {
  color: var(--text-secondary);
  font-size: 0.8125rem;
}

@media (max-width: 1200px) {
  .lightrag-documents {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .lightrag-documents__toolbar {
    align-items: stretch;
  }
}
</style>
