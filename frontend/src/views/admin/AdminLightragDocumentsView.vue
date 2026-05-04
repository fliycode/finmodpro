<script setup>
import { onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';

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

    <AppSectionCard title="上传与管线动作" desc="保留上传、扫描、失败重试、缓存清理与取消管线的管理动作。" admin>
      <div class="lightrag-actions">
        <div class="lightrag-upload">
          <input type="file" @change="handleFileChange" />
          <el-button type="primary" :loading="isUploading" @click="handleUpload">上传到 LightRAG</el-button>
        </div>

        <div class="lightrag-actions__buttons">
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.scanDocuments(), '已触发目录扫描。')">扫描新文档</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.reprocessFailedDocuments(), '已重新触发失败任务。')">重跑失败任务</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.clearCache(), '已清理 LightRAG 缓存。')">清理缓存</el-button>
          <el-button :loading="isRunningAction" @click="runAction(() => lightragApi.cancelPipeline(), '已发出取消管线请求。')">取消当前管线</el-button>
        </div>
      </div>
    </AppSectionCard>

    <AppSectionCard title="文档分页" desc="直接查看 LightRAG 文档状态与 track id，必要时可就地删除无效入库。" admin>
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
    </AppSectionCard>

    <AppSectionCard title="Track status" desc="按 track id 追踪一次上传或扫描任务的最终状态与文档结果。" admin>
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
    </AppSectionCard>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-actions,
.lightrag-actions__buttons,
.lightrag-document-list,
.lightrag-track,
.lightrag-track__documents {
  display: grid;
  gap: 16px;
}

.lightrag-document-card,
.lightrag-track__document {
  border: 1px solid var(--line-soft);
  border-radius: 24px;
  background: rgba(24, 34, 49, 0.92);
  box-shadow: var(--shadow-md);
}

.lightrag-upload,
.lightrag-track__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-document-card,
.lightrag-track__document {
  padding: 18px;
}

.lightrag-document-card__head,
.lightrag-document-card__meta,
.lightrag-document-card__actions,
.lightrag-track__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.lightrag-document-card__head {
  justify-content: space-between;
  align-items: flex-start;
}

.lightrag-document-card__head p,
.lightrag-track__document p,
.lightrag-track__document pre {
  margin: 6px 0 0;
  color: var(--text-secondary);
}

.lightrag-status-pill {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.16);
  color: var(--brand);
}

.lightrag-track__document pre {
  white-space: pre-wrap;
}

</style>
