<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import LightragPanel from '../../components/lightrag/LightragPanel.vue';

const flash = useFlash();
const isLoading = ref(false);
const isSubmitting = ref(false);
const errorMsg = ref('');
const overview = ref({
  health: {},
  auth_status: {},
  status_counts: { status_counts: {} },
  popular_labels: [],
});
const result = ref(null);

const queryForm = reactive({
  query: '',
  mode: 'hybrid',
  response_type: 'Bullet Points',
  top_k: 8,
  chunk_top_k: 6,
  include_references: true,
  include_chunk_content: true,
});

const referenceRows = computed(() => Array.isArray(result.value?.references) ? result.value.references : []);
const statusItems = computed(() => ([
  { label: '服务状态', value: overview.value.health?.status || '未知' },
  { label: '鉴权模式', value: overview.value.auth_status?.auth_mode || '未知' },
  { label: '文档总量', value: overview.value.status_counts?.status_counts?.all ?? 0 },
  { label: '热门标签', value: overview.value.popular_labels?.length ?? 0 },
]));

const loadOverview = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    overview.value = await lightragApi.getOverview();
  } catch (error) {
    errorMsg.value = error.message || '加载图谱检索概览失败。';
  } finally {
    isLoading.value = false;
  }
};

const handleSubmit = async () => {
  if ((queryForm.query || '').trim().length < 3) {
    flash.warning('查询内容至少需要 3 个字符。');
    return;
  }

  isSubmitting.value = true;
  errorMsg.value = '';
  try {
    result.value = await lightragApi.query({
      query: queryForm.query.trim(),
      mode: queryForm.mode,
      response_type: queryForm.response_type,
      top_k: queryForm.top_k,
      chunk_top_k: queryForm.chunk_top_k,
      include_references: queryForm.include_references,
      include_chunk_content: queryForm.include_chunk_content,
    });
  } catch (error) {
    errorMsg.value = error.message || '图谱检索失败，请稍后重试。';
  } finally {
    isSubmitting.value = false;
  }
};

const applyLabel = (label) => {
  queryForm.query = queryForm.query
    ? `${queryForm.query}\n聚焦标签：${label}`
    : `请围绕“${label}”做一次图增强检索。`;
};

const fillExample = () => {
  queryForm.query = '请总结最近文档中与流动性风险相关的实体、关键关系和可追溯依据。';
};

onMounted(loadOverview);
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

    <div class="lightrag-query-layout">
      <LightragPanel title="Query" desc="保留 LightRAG 的 mode、top-k 与 chunk 控制，直接从这里组织一次检索。">
        <div class="lightrag-form-stack">
          <el-input
            v-model="queryForm.query"
            type="textarea"
            :rows="7"
            maxlength="500"
            show-word-limit
            placeholder="输入检索问题，例如：请解释某家银行债务风险在最近披露文件里的实体关系与证据。"
          />

          <div class="lightrag-control-grid">
            <label class="lightrag-field">
              <span>检索模式</span>
              <el-select v-model="queryForm.mode">
                <el-option label="Hybrid" value="hybrid" />
                <el-option label="Local" value="local" />
                <el-option label="Global" value="global" />
                <el-option label="Naive" value="naive" />
              </el-select>
            </label>
            <label class="lightrag-field">
              <span>回答格式</span>
              <el-select v-model="queryForm.response_type">
                <el-option label="Bullet Points" value="Bullet Points" />
                <el-option label="Multiple Paragraphs" value="Multiple Paragraphs" />
                <el-option label="Single Paragraph" value="Single Paragraph" />
              </el-select>
            </label>
            <label class="lightrag-field">
              <span>Top K</span>
              <el-input-number v-model="queryForm.top_k" :min="1" :max="20" />
            </label>
            <label class="lightrag-field">
              <span>Chunk Top K</span>
              <el-input-number v-model="queryForm.chunk_top_k" :min="1" :max="20" />
            </label>
          </div>

          <div class="lightrag-toolbar">
            <div class="lightrag-toolbar__switches">
              <el-switch v-model="queryForm.include_references" inline-prompt active-text="引用" inactive-text="引用" />
              <el-switch v-model="queryForm.include_chunk_content" inline-prompt active-text="Chunk" inactive-text="Chunk" />
            </div>
            <div class="lightrag-toolbar__actions">
              <el-button type="primary" :loading="isSubmitting" @click="handleSubmit">运行检索</el-button>
              <el-button @click="fillExample">填入示例</el-button>
              <el-link href="/admin/lightrag/legacy" target="_blank" rel="noopener">Legacy WebUI</el-link>
            </div>
          </div>
        </div>
      </LightragPanel>

      <LightragPanel title="Labels" desc="像 LightRAG 原生页一样，用热门标签快速补全查询上下文。">
        <template #header>
          <el-button text :loading="isLoading" @click="loadOverview">刷新</el-button>
        </template>

        <div class="lightrag-side-stack">
          <div class="lightrag-help-box">
            <strong>推荐用法</strong>
            <p>先点标签，再补充机构名、时间段或问题目标，最后运行检索。</p>
          </div>

          <div class="lightrag-chip-list">
            <button
              v-for="label in overview.popular_labels"
              :key="label"
              type="button"
              class="lightrag-chip"
              @click="applyLabel(label)"
            >
              {{ label }}
            </button>
            <p v-if="!overview.popular_labels.length" class="lightrag-empty-note">
              当前还没有可用标签，适合先去文档管线页检查入库状态。
            </p>
          </div>
        </div>
      </LightragPanel>
    </div>

    <div class="lightrag-result-layout">
      <LightragPanel title="Response" desc="检索回答优先占主工作区，避免再跳回 iframe 查看。">
        <div v-if="result" class="lightrag-answer">
          <p>{{ result.response || '当前没有返回回答。' }}</p>
        </div>
        <div v-else class="admin-empty-state">
          还没有执行检索。建议先跑一条围绕风险标签或机构名称的问题。
        </div>
      </LightragPanel>

      <LightragPanel title="References" desc="保留引用回看与 chunk 回溯，方便人工核对答案来源。">
        <div class="lightrag-reference-summary">
          <span>引用条数</span>
          <strong>{{ referenceRows.length }}</strong>
        </div>

        <div v-if="referenceRows.length" class="lightrag-reference-list">
          <article v-for="(item, index) in referenceRows" :key="index" class="lightrag-reference-card">
            <div class="lightrag-reference-card__head">
              <strong>{{ item.title || item.doc_id || `引用 ${index + 1}` }}</strong>
              <span>{{ item.chunk_id || item.id || '未返回 chunk id' }}</span>
            </div>
            <p>{{ item.content || item.chunk_content || item.text || '当前引用未返回正文内容。' }}</p>
          </article>
        </div>
        <div v-else class="admin-empty-state">本次检索没有返回引用。</div>
      </LightragPanel>
    </div>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-form-stack,
.lightrag-side-stack,
.lightrag-reference-list {
  display: grid;
  gap: 16px;
}

.lightrag-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-stat,
.lightrag-help-box,
.lightrag-reference-card,
.lightrag-reference-summary,
.lightrag-answer {
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.lightrag-stat {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
}

.lightrag-stat span,
.lightrag-field span,
.lightrag-reference-summary span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-stat strong,
.lightrag-reference-summary strong {
  color: var(--text-primary);
  font-size: 1.2rem;
}

.lightrag-query-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  gap: 18px;
}

.lightrag-result-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 18px;
}

.lightrag-control-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-field {
  display: grid;
  gap: 8px;
}

.lightrag-toolbar,
.lightrag-toolbar__switches,
.lightrag-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-toolbar {
  justify-content: space-between;
}

.lightrag-help-box {
  padding: 14px 16px;
  background: var(--surface-3);
}

.lightrag-help-box strong,
.lightrag-reference-card__head strong {
  color: var(--text-primary);
}

.lightrag-help-box p,
.lightrag-answer p,
.lightrag-reference-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.lightrag-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-chip {
  padding: 8px 12px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-primary);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.lightrag-chip:hover {
  border-color: rgba(36, 87, 197, 0.24);
  color: var(--brand);
  background: var(--brand-soft);
}

.lightrag-empty-note {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-answer,
.lightrag-reference-summary,
.lightrag-reference-card {
  padding: 16px 18px;
}

.lightrag-reference-summary,
.lightrag-reference-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 1180px) {
  .lightrag-query-layout,
  .lightrag-result-layout,
  .lightrag-control-grid {
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
