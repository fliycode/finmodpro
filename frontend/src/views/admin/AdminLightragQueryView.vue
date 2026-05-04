<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import AppIcon from '../../components/ui/AppIcon.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';

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

const statusCards = computed(() => ([
  {
    label: '服务状态',
    value: overview.value.health?.status || '未知',
  },
  {
    label: '鉴权模式',
    value: overview.value.auth_status?.auth_mode || '未知',
  },
  {
    label: '文档总量',
    value: overview.value.status_counts?.status_counts?.all ?? 0,
  },
  {
    label: '热门标签',
    value: Array.isArray(overview.value.popular_labels) ? overview.value.popular_labels.length : 0,
  },
]));

const referenceRows = computed(() => Array.isArray(result.value?.references) ? result.value.references : []);

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
    <section class="lightrag-hero">
      <div class="lightrag-hero__copy">
        <span class="lightrag-hero__eyebrow">Graph retrieval workbench</span>
        <h2 class="lightrag-hero__title">图谱检索工作台</h2>
        <p class="lightrag-hero__subtitle">
          把 LightRAG 的核心问答能力收进管理端主壳，保留图增强检索与引用回看，不再把查询体验交给 iframe。
        </p>
      </div>
      <div class="lightrag-hero__metrics">
        <article v-for="item in statusCards" :key="item.label" class="lightrag-hero__metric">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard
      title="查询编排"
      desc="保留 LightRAG 的 mode / top-k / chunk 取数控制，把高频查询操作收口到 FinModPro 原生页面。"
      admin
    >
      <div class="lightrag-query-grid">
        <div class="lightrag-query-form">
          <el-input
            v-model="queryForm.query"
            type="textarea"
            :rows="6"
            maxlength="500"
            show-word-limit
            placeholder="输入图谱检索问题，例如：请解释某家银行债务风险在最近披露文件里的实体关系与证据。"
          />

          <div class="lightrag-query-controls">
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

          <div class="lightrag-query-switches">
            <el-switch v-model="queryForm.include_references" inline-prompt active-text="引用" inactive-text="引用" />
            <el-switch v-model="queryForm.include_chunk_content" inline-prompt active-text="Chunk" inactive-text="Chunk" />
          </div>

          <div class="lightrag-query-actions">
            <el-button type="primary" :loading="isSubmitting" @click="handleSubmit">运行检索</el-button>
            <el-button @click="fillExample">填入示例</el-button>
            <el-link href="/admin/lightrag/legacy" target="_blank" rel="noopener">Legacy WebUI</el-link>
          </div>
        </div>

        <aside class="lightrag-query-aside">
          <div class="lightrag-query-aside__head">
            <strong>热门标签</strong>
            <button type="button" class="lightrag-link-button" :disabled="isLoading" @click="loadOverview">刷新</button>
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
            <p v-if="!overview.popular_labels.length" class="muted-text">当前还没有可用标签，适合先去文档管线页检查入库状态。</p>
          </div>
        </aside>
      </div>
    </AppSectionCard>

    <AppSectionCard
      title="答案与引用"
      desc="先给出检索回答，再把引用与 chunk 回溯放在同一屏，减少在外部 WebUI 来回跳转。"
      admin
    >
      <div v-if="result" class="lightrag-answer-stack">
        <article class="lightrag-answer">
          <div class="lightrag-answer__head">
            <AppIcon name="spark" />
            <strong>检索回答</strong>
          </div>
          <p>{{ result.response || '当前没有返回回答。' }}</p>
        </article>

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
      </div>
      <div v-else class="admin-empty-state">
        还没有执行检索。建议先跑一条围绕风险标签或机构名称的问题。
      </div>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.lightrag-page {
  gap: 20px;
}

.lightrag-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.9fr);
  gap: 18px;
  padding: 24px 28px;
  border: 1px solid rgba(141, 208, 208, 0.14);
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(141, 208, 208, 0.06), rgba(15, 23, 34, 0)),
    linear-gradient(135deg, rgba(36, 87, 197, 0.14), rgba(24, 34, 49, 0.92));
}

.lightrag-hero__eyebrow {
  display: inline-flex;
  margin-bottom: 10px;
  color: rgba(141, 208, 208, 0.92);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.lightrag-hero__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 32px;
  line-height: 1.1;
}

.lightrag-hero__subtitle {
  margin: 12px 0 0;
  max-width: 68ch;
  color: var(--text-secondary);
  line-height: 1.7;
}

.lightrag-hero__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-hero__metric,
.lightrag-answer,
.lightrag-reference-summary,
.lightrag-reference-card,
.lightrag-query-aside {
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: rgba(24, 34, 49, 0.9);
  box-shadow: var(--shadow-md);
}

.lightrag-hero__metric {
  padding: 16px 18px;
  display: grid;
  gap: 6px;
}

.lightrag-hero__metric span {
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-hero__metric strong {
  color: var(--text-primary);
  font-size: 24px;
}

.lightrag-query-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(260px, 0.7fr);
  gap: 18px;
}

.lightrag-query-form,
.lightrag-answer-stack {
  display: grid;
  gap: 16px;
}

.lightrag-query-controls {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-field {
  display: grid;
  gap: 8px;
}

.lightrag-field span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-query-switches,
.lightrag-query-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-query-aside {
  padding: 18px;
  display: grid;
  align-content: start;
  gap: 14px;
}

.lightrag-query-aside__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.lightrag-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-chip,
.lightrag-link-button {
  border: 1px solid rgba(141, 208, 208, 0.16);
  background: rgba(15, 23, 34, 0.86);
  color: var(--text-primary);
  cursor: pointer;
}

.lightrag-chip {
  padding: 8px 12px;
  border-radius: 999px;
}

.lightrag-link-button {
  padding: 0;
  border: none;
  color: var(--brand);
}

.lightrag-answer {
  padding: 18px 20px;
}

.lightrag-answer__head,
.lightrag-reference-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.lightrag-answer p,
.lightrag-reference-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.lightrag-reference-summary {
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.lightrag-reference-list {
  display: grid;
  gap: 12px;
}

.lightrag-reference-card {
  padding: 16px 18px;
}

@media (max-width: 1180px) {
  .lightrag-hero,
  .lightrag-query-grid {
    grid-template-columns: 1fr;
  }

  .lightrag-query-controls {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .lightrag-query-controls,
  .lightrag-hero__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
