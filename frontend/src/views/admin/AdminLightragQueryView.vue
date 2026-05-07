<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import LightragWorkspaceShell from '../../components/lightrag/LightragWorkspaceShell.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
const isLoading = ref(false);
const isSubmitting = ref(false);
const errorMsg = ref('');
const refreshedAt = ref('');
const advancedSections = ref([]);
const overview = ref({
  health: {},
  auth_status: {},
  status_counts: { status_counts: {} },
  popular_labels: [],
});
const result = ref(null);

const queryExamples = [
  '请总结最近文档中与流动性风险相关的实体、关键关系和可追溯依据。',
  '围绕某家银行最近披露材料，梳理债务压力、关联主体和证据来源。',
  '请只保留和信用风险直接相关的图谱实体，并按证据强弱排序说明。',
];

const queryForm = reactive({
  query: '',
  mode: 'hybrid',
  response_type: 'Bullet Points',
  top_k: 8,
  chunk_top_k: 6,
  include_references: true,
  include_chunk_content: true,
});

const referenceRows = computed(() => (Array.isArray(result.value?.references) ? result.value.references : []));
const responseBlocks = computed(() => {
  const text = String(result.value?.response || '').trim();
  if (!text) {
    return [];
  }
  return text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
});
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
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载图谱工作台状态失败。';
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
    : `请围绕“${label}”做一次图增强检索，并给出可追溯证据。`;
};

const useExample = (example) => {
  queryForm.query = example;
};

const setMode = (mode) => {
  queryForm.mode = mode;
};

onMounted(loadOverview);
</script>

<template>
  <LightragWorkspaceShell :status-items="statusItems">
    <template #aside>
      <span>最近刷新：{{ refreshedAt || '尚未刷新' }}</span>
      <a href="/admin/lightrag/legacy" target="_blank" rel="noopener">打开 Legacy WebUI</a>
    </template>
    <template #actions>
      <el-button :loading="isLoading" @click="loadOverview">刷新状态</el-button>
    </template>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <div class="lightrag-query">
      <div class="lightrag-query__primary">
        <AppSectionCard
          title="发起问题"
          desc="先写清楚你要验证的风险、对象或时间范围，再决定检索模式。"
          admin
        >
          <div class="lightrag-query__composer">
            <el-input
              v-model="queryForm.query"
              type="textarea"
              :rows="8"
              maxlength="640"
              show-word-limit
              placeholder="例如：请梳理最近披露材料里与流动性风险相关的实体、关键关系，以及每条结论对应的证据来源。"
            />

            <div class="lightrag-query__mode-row">
              <div class="lightrag-query__mode-group">
                <button
                  v-for="mode in ['hybrid', 'local', 'global']"
                  :key="mode"
                  type="button"
                  :class="['lightrag-query__mode-chip', { 'lightrag-query__mode-chip--active': queryForm.mode === mode }]"
                  @click="setMode(mode)"
                >
                  {{ mode }}
                </button>
              </div>

              <div class="lightrag-query__actions">
                <el-button type="primary" :loading="isSubmitting" @click="handleSubmit">运行检索</el-button>
                <el-button @click="useExample(queryExamples[0])">填入示例</el-button>
              </div>
            </div>

            <el-collapse v-model="advancedSections">
              <el-collapse-item name="advanced" title="高级检索设置">
                <div class="lightrag-query__advanced-grid">
                  <label class="lightrag-query__field">
                    <span>回答格式</span>
                    <el-select v-model="queryForm.response_type">
                      <el-option label="Bullet Points" value="Bullet Points" />
                      <el-option label="Multiple Paragraphs" value="Multiple Paragraphs" />
                      <el-option label="Single Paragraph" value="Single Paragraph" />
                    </el-select>
                  </label>
                  <label class="lightrag-query__field">
                    <span>Top K</span>
                    <el-input-number v-model="queryForm.top_k" :min="1" :max="20" />
                  </label>
                  <label class="lightrag-query__field">
                    <span>Chunk Top K</span>
                    <el-input-number v-model="queryForm.chunk_top_k" :min="1" :max="20" />
                  </label>
                </div>

                <div class="lightrag-query__advanced-switches">
                  <el-switch v-model="queryForm.include_references" inline-prompt active-text="引用" inactive-text="引用" />
                  <el-switch v-model="queryForm.include_chunk_content" inline-prompt active-text="Chunk" inactive-text="Chunk" />
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </AppSectionCard>

        <AppSectionCard title="检索回答" desc="回答占主工作区，证据和 chunk 回看固定在右侧。" admin>
          <template #header>
            <span class="lightrag-query__summary-chip">引用 {{ referenceRows.length }}</span>
          </template>

          <div v-if="responseBlocks.length" class="lightrag-query__response">
            <article
              v-for="(block, index) in responseBlocks"
              :key="index"
              class="lightrag-query__response-block"
            >
              <span class="lightrag-query__response-index">{{ index + 1 }}</span>
              <p>{{ block }}</p>
            </article>
          </div>
          <div v-else class="admin-empty-state">
            还没有执行检索。先明确一个问题，再决定是否需要标签补充。
          </div>
        </AppSectionCard>
      </div>

      <div class="lightrag-query__secondary">
        <AppSectionCard title="补充上下文" desc="用标签把问题范围收窄，不必先展开所有高级参数。" admin>
          <div class="lightrag-query__context-stack">
            <div class="lightrag-query__tip">
              <strong>推荐顺序</strong>
              <p>先点一个标签，再补机构名、时间段或问题目标，最后运行检索。</p>
            </div>

            <div class="lightrag-query__chip-list">
              <button
                v-for="label in overview.popular_labels"
                :key="label"
                type="button"
                class="lightrag-query__chip"
                @click="applyLabel(label)"
              >
                {{ label }}
              </button>
              <p v-if="!overview.popular_labels.length" class="lightrag-query__empty-note">
                当前还没有热门标签，适合先去文档管线页检查入库状态。
              </p>
            </div>
          </div>
        </AppSectionCard>

        <AppSectionCard title="推荐问题" desc="直接套用一个结构，再替换机构、时间或风险主题。" admin>
          <div class="lightrag-query__examples">
            <button
              v-for="example in queryExamples"
              :key="example"
              type="button"
              class="lightrag-query__example"
              @click="useExample(example)"
            >
              {{ example }}
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard title="证据栈" desc="检索后第一时间核对引用，避免只看结论。" admin>
          <div v-if="referenceRows.length" class="lightrag-query__reference-list">
            <article
              v-for="(item, index) in referenceRows"
              :key="index"
              class="lightrag-query__reference"
            >
              <div class="lightrag-query__reference-head">
                <strong>{{ item.title || item.doc_id || `引用 ${index + 1}` }}</strong>
                <span>{{ item.chunk_id || item.id || '未返回 chunk id' }}</span>
              </div>
              <p>{{ item.content || item.chunk_content || item.text || '当前引用未返回正文内容。' }}</p>
            </article>
          </div>
          <div v-else class="admin-empty-state">运行一次检索后，这里会展示引用和 chunk 证据。</div>
        </AppSectionCard>
      </div>
    </div>
  </LightragWorkspaceShell>
</template>

<style scoped>
.lightrag-query,
.lightrag-query__composer,
.lightrag-query__context-stack,
.lightrag-query__examples,
.lightrag-query__reference-list,
.lightrag-query__response {
  display: grid;
  gap: 16px;
}

.lightrag-query {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.72fr);
  gap: 18px;
}

.lightrag-query__primary,
.lightrag-query__secondary {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.lightrag-query__mode-row,
.lightrag-query__actions,
.lightrag-query__advanced-switches,
.lightrag-query__reference-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-query__mode-row {
  justify-content: space-between;
}

.lightrag-query__mode-group,
.lightrag-query__chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-query__mode-chip,
.lightrag-query__chip,
.lightrag-query__example {
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.lightrag-query__mode-chip,
.lightrag-query__chip {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
}

.lightrag-query__mode-chip:hover,
.lightrag-query__mode-chip--active,
.lightrag-query__chip:hover,
.lightrag-query__example:hover {
  border-color: rgba(36, 87, 197, 0.24);
  background: var(--brand-soft);
  color: var(--brand);
}

.lightrag-query__advanced-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.lightrag-query__field {
  display: grid;
  gap: 8px;
}

.lightrag-query__field span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-query__tip,
.lightrag-query__reference,
.lightrag-query__response-block,
.lightrag-query__summary-chip {
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.lightrag-query__tip,
.lightrag-query__reference,
.lightrag-query__example {
  padding: 14px 16px;
}

.lightrag-query__tip {
  background: var(--surface-3);
}

.lightrag-query__tip strong,
.lightrag-query__reference-head strong {
  color: var(--text-primary);
}

.lightrag-query__tip p,
.lightrag-query__reference p,
.lightrag-query__response-block p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.lightrag-query__response-block {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  padding: 16px 18px;
}

.lightrag-query__response-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.75rem;
  font-weight: 700;
}

.lightrag-query__example {
  width: 100%;
  border-radius: 16px;
  text-align: left;
  line-height: 1.7;
}

.lightrag-query__reference-head {
  justify-content: space-between;
  align-items: flex-start;
}

.lightrag-query__reference-head span {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.lightrag-query__summary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  color: var(--brand);
  font-size: 0.75rem;
  font-weight: 700;
}

.lightrag-query__empty-note {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.6;
}

@media (max-width: 1240px) {
  .lightrag-query {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .lightrag-query__advanced-grid {
    grid-template-columns: 1fr;
  }

  .lightrag-query__mode-row {
    align-items: stretch;
  }
}
</style>
