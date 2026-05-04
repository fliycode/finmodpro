<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import LightragPanel from '../../components/lightrag/LightragPanel.vue';

const flash = useFlash();
const errorMsg = ref('');
const isLoading = ref(false);
const isUploading = ref(false);
const isRunningAction = ref(false);
const selectedFile = ref(null);
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

onMounted(loadDocuments);
</script>

<template>
  <div class="page-stack lightrag-page">
    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="lightrag-strip">
      <article v-for="item in statusItems" :key="item.label" class="lightrag-stat">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>

    <LightragPanel title="Pipeline actions" desc="上传、扫描、重跑、清缓存与取消管线集中在一条工具区。">
      <div class="lightrag-actions">
        <div class="lightrag-upload">
          <input type="file" @change="handleFileChange" />
          <el-button type="primary" :loading="isUploading" @click="handleUpload">上传到 LightRAG</el-button>
        </div>

        <div class="lightrag-button-row">
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.scanDocuments(), '已触发目录扫描。')">扫描新文档</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.reprocessFailedDocuments(), '已重新触发失败任务。')">重跑失败任务</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.clearCache(), '已清理 LightRAG 缓存。')">清理缓存</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.cancelPipeline(), '已发出取消管线请求。')">取消当前管线</el-button>
        </div>
      </div>
    </LightragPanel>

    <div class="lightrag-layout">
      <LightragPanel title="Documents" :desc="`当前分页已载入 ${documents.length} 条，LightRAG 返回总数 ${pager.total}。`">
        <div v-if="documents.length" class="lightrag-document-list">
          <article v-for="row in documents" :key="row.id" class="lightrag-document-card">
            <div class="lightrag-document-card__head">
              <div>
                <strong>{{ row.title }}</strong>
                <p>{{ row.summary || '当前文档未返回额外摘要。' }}</p>
              </div>
              <span class="lightrag-status-pill">{{ row.status }}</span>
            </div>
            <div class="lightrag-document-card__meta">
              <span>doc_id：{{ row.docId || '未提供' }}</span>
              <span>track_id：{{ row.trackId || '未提供' }}</span>
              <span>更新时间：{{ row.updatedAt || '未提供' }}</span>
            </div>
            <div class="lightrag-document-card__actions">
              <el-button text @click="deleteDocument(row)">删除文档</el-button>
            </div>
          </article>
        </div>
        <div v-else class="admin-empty-state">当前还没有进入 LightRAG 的文档。</div>
      </LightragPanel>

      <LightragPanel title="Track status" desc="按 track id 追踪上传或扫描任务，像原生页那样单独查看处理结果。">
        <div class="lightrag-track">
          <div class="lightrag-track__toolbar">
            <el-input v-model="trackId" placeholder="输入 track id" />
            <el-button :loading="isRunningAction" @click="handleTrackStatus">查询</el-button>
          </div>

          <div v-if="trackStatus" class="lightrag-track__result">
            <div class="lightrag-track__summary">
              <span>关联文档数：{{ trackStatus.total_count }}</span>
              <span>状态摘要：{{ JSON.stringify(trackStatus.status_summary || {}) }}</span>
            </div>
            <div class="lightrag-track__documents">
              <article v-for="(item, index) in trackStatus.documents || []" :key="index" class="lightrag-track__document">
                <strong>{{ item.file_path || item.file_name || item.doc_id || `文档 ${index + 1}` }}</strong>
                <p>{{ item.status || '未知状态' }}</p>
                <pre>{{ JSON.stringify(item, null, 2) }}</pre>
              </article>
            </div>
          </div>
          <div v-else class="admin-empty-state">输入 track id 后即可查看任务明细。</div>
        </div>
      </LightragPanel>
    </div>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-actions,
.lightrag-document-list,
.lightrag-track,
.lightrag-track__documents {
  display: grid;
  gap: 16px;
}

.lightrag-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-stat,
.lightrag-document-card,
.lightrag-track__document {
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.lightrag-stat {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
}

.lightrag-stat span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-stat strong {
  color: var(--text-primary);
  font-size: 1.2rem;
}

.lightrag-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 18px;
}

.lightrag-upload,
.lightrag-button-row,
.lightrag-track__toolbar,
.lightrag-track__summary,
.lightrag-document-card__head,
.lightrag-document-card__meta,
.lightrag-document-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-document-card,
.lightrag-track__document {
  padding: 16px 18px;
}

.lightrag-document-card__head {
  justify-content: space-between;
  align-items: flex-start;
}

.lightrag-document-card__head strong,
.lightrag-track__document strong {
  color: var(--text-primary);
}

.lightrag-document-card__head p,
.lightrag-track__document p,
.lightrag-track__document pre {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-status-pill {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
}

.lightrag-track__document pre {
  white-space: pre-wrap;
}

@media (max-width: 1180px) {
  .lightrag-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .lightrag-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .lightrag-strip {
    grid-template-columns: 1fr;
  }
}
</style>
