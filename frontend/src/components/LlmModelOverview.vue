<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { llmApi, normalizeModelConfigOverviewSummary, normalizeModelConfigPayload } from '../api/llm.js';
import { useFlash } from '../lib/flash.js';
import AdminDataTable from './admin/AdminDataTable.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import AppIcon from './ui/AppIcon.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const flash = useFlash();

const providerOptions = [
  { label: 'LiteLLM', value: 'litellm' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'DashScope', value: 'dashscope' },
  { label: 'Ollama', value: 'ollama' },
];

const capabilityOptions = [
  { label: '对话模型', value: 'chat' },
  { label: '向量模型', value: 'embedding' },
  { label: '重排模型', value: 'rerank' },
];

const tableColumns = [
  { key: 'name', label: '模型名称', prop: 'name', minWidth: 220, sortable: true, slot: 'name' },
  { key: 'capability', label: '模型类型', prop: 'capability', minWidth: 150, sortable: true, slot: 'capability' },
  { key: 'parameter_scale', label: '参数规模', prop: 'parameter_scale', minWidth: 120, sortable: true, slot: 'parameter_scale' },
  { key: 'status', label: '状态', prop: 'is_active', minWidth: 120, sortable: true, slot: 'status' },
  { key: 'invocation_count', label: '调用次数', prop: 'invocation_count', minWidth: 130, sortable: true, slot: 'invocation_count' },
  { key: 'updated_at', label: '更新时间', prop: 'updated_at', minWidth: 180, sortable: true, slot: 'updated_at' },
  { key: 'description', label: '模型描述', prop: 'description', minWidth: 220, slot: 'description' },
  { key: 'actions', label: '操作', prop: 'actions', width: 156, slot: 'actions', tooltip: false, fixed: 'right' },
];

const isLoading = ref(false);
const isSaving = ref(false);
const drawerVisible = ref(false);
const editingId = ref(null);
const errorMsg = ref('');
const configs = ref([]);
const summary = ref(normalizeModelConfigOverviewSummary());
const sortField = ref('updated_at');
const sortOrder = ref('descending');
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = ref(10);
const originalOptions = ref({});

const defaultFormState = () => ({
  name: '',
  model_name: '',
  capability: 'chat',
  provider: 'litellm',
  parameter_scale: '',
  endpoint: 'http://localhost:4000',
  description: '',
  api_key: '',
  temperature: 0.2,
  max_tokens: 1024,
  is_active: false,
  has_api_key: false,
  api_key_masked: '',
});

const form = reactive(defaultFormState());

const drawerTitle = computed(() => (editingId.value ? '编辑模型' : '新增模型'));
const supportsTokenOptions = computed(() => ['deepseek', 'litellm', 'dashscope'].includes(form.provider));
const capabilityCounts = computed(() => capabilityOptions.map((item) => ({
  ...item,
  count: configs.value.filter((config) => config.capability === item.value).length,
})));

const summaryCards = computed(() => {
  const enabledRatio = summary.value.total_models > 0
    ? `${((summary.value.enabled_models / summary.value.total_models) * 100).toFixed(0)}%`
    : '0%';
  const capabilityCoverage = `${((capabilityCounts.value.filter((item) => item.count > 0).length / capabilityOptions.length) * 100).toFixed(0)}%`;
  const invocationChangePct = summary.value.invocation_change_pct === null
    ? '0.0%'
    : `${summary.value.invocation_change_pct > 0 ? '+' : ''}${summary.value.invocation_change_pct.toFixed(1)}%`;

  return [
    {
      key: 'total-models',
      label: '模型总数',
      value: formatCount(summary.value.total_models),
      badge: `${capabilityCoverage} 覆盖`,
      icon: 'layers',
      tone: 'brand',
    },
    {
      key: 'enabled-models',
      label: '启用模型',
      value: formatCount(summary.value.enabled_models),
      badge: enabledRatio,
      icon: 'check',
      tone: 'success',
    },
    {
      key: 'invocations',
      label: '总调用次数',
      value: formatCount(summary.value.total_invocation_count),
      badge: invocationChangePct,
      icon: 'bar-chart',
      tone: summary.value.invocation_change_pct !== null && summary.value.invocation_change_pct < 0 ? 'warning' : 'accent',
    },
  ];
});

const filteredConfigs = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) {
    return configs.value;
  }

  return configs.value.filter((item) => ([
    item.name,
    item.model_name,
    item.description,
    item.parameter_scale,
    item.capability,
    item.provider,
  ].join(' ').toLowerCase().includes(query)));
});

const sortedConfigs = computed(() => {
  const order = sortOrder.value === 'ascending' ? 1 : -1;
  const field = sortField.value;
  const rows = [...filteredConfigs.value];

  if (!field) {
    return rows;
  }

  rows.sort((left, right) => {
    const a = sortValue(left, field);
    const b = sortValue(right, field);

    if (a === b) {
      return 0;
    }
    if (a === null || a === undefined || a === '') {
      return 1;
    }
    if (b === null || b === undefined || b === '') {
      return -1;
    }

    return a > b ? order : -order;
  });

  return rows;
});

const paginatedConfigs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return sortedConfigs.value.slice(start, start + pageSize.value);
});

function formatCount(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value ?? 0));
}

function capabilityLabel(value) {
  const option = capabilityOptions.find((item) => item.value === value);
  return option?.label || '未分类模型';
}

function providerLabel(value) {
  const option = providerOptions.find((item) => item.value === value);
  return option?.label || value || '未登记';
}

function formatUpdatedAt(value) {
  if (!value) {
    return '未记录';
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function sortValue(row, field) {
  if (field === 'is_active') {
    return row.is_active ? 1 : 0;
  }
  if (field === 'updated_at') {
    return new Date(row.updated_at || 0).getTime();
  }
  if (field === 'invocation_count') {
    return Number(row.invocation_count ?? 0);
  }

  return String(row[field] ?? '').toLowerCase();
}

function resetForm() {
  Object.assign(form, defaultFormState());
  editingId.value = null;
  originalOptions.value = {};
}

function openCreate() {
  resetForm();
  drawerVisible.value = true;
}

function openEdit(config) {
  resetForm();
  editingId.value = config.id;
  const safeOptions = { ...(config.options || {}) };
  delete safeOptions.api_key;
  originalOptions.value = safeOptions;
  form.name = config.name;
  form.model_name = config.model_name;
  form.capability = config.capability;
  form.provider = config.provider;
  form.parameter_scale = config.parameter_scale || '';
  form.endpoint = config.endpoint;
  form.description = config.description || '';
  form.is_active = Boolean(config.is_active);
  form.temperature = Number(config.options?.temperature ?? 0.2);
  form.max_tokens = Number(config.options?.max_tokens ?? 1024);
  form.has_api_key = Boolean(config.has_api_key);
  form.api_key_masked = config.api_key_masked || '';
  drawerVisible.value = true;
}

function buildPayload() {
  const options = { ...originalOptions.value };
  const apiKey = String(form.api_key || '').trim();

  if (apiKey) {
    options.api_key = apiKey;
  }
  if (supportsTokenOptions.value) {
    options.temperature = Number(form.temperature);
    options.max_tokens = Number(form.max_tokens);
  } else {
    delete options.temperature;
    delete options.max_tokens;
  }

  return {
    name: String(form.name || '').trim(),
    model_name: String(form.model_name || '').trim(),
    capability: form.capability,
    provider: form.provider,
    parameter_scale: String(form.parameter_scale || '').trim(),
    endpoint: String(form.endpoint || '').trim(),
    description: String(form.description || '').trim(),
    options,
    is_active: Boolean(form.is_active),
  };
}

async function fetchConfigs() {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const payload = await llmApi.getModelConfigs();
    configs.value = normalizeModelConfigPayload(payload);
    summary.value = normalizeModelConfigOverviewSummary(payload);
    const maxPage = Math.max(1, Math.ceil(filteredConfigs.value.length / pageSize.value));
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage;
    }
  } catch (error) {
    errorMsg.value = error.message || '加载模型总览失败';
    configs.value = [];
    summary.value = normalizeModelConfigOverviewSummary();
  } finally {
    isLoading.value = false;
  }
}

async function saveModel() {
  isSaving.value = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      await llmApi.updateModelConfig(editingId.value, payload);
      flash.success('模型信息已更新');
    } else {
      await llmApi.createModelConfig(payload);
      flash.success('模型已添加');
    }
    drawerVisible.value = false;
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '保存模型失败');
  } finally {
    isSaving.value = false;
  }
}

async function activateModel(config) {
  if (config.is_active) {
    return;
  }

  try {
    await llmApi.activateModelConfig(config.id, true);
    flash.success(`已启动模型：${config.name}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '启动模型失败');
  }
}

async function deleteModel(config) {
  if (config.is_active) {
    flash.error('启用中的模型不能直接删除，请先启动同类型的其他模型。');
    return;
  }

  if (!window.confirm(`确定删除模型“${config.name}”吗？`)) {
    return;
  }

  try {
    await llmApi.deleteModelConfig(config.id);
    flash.success(`已删除模型：${config.name}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '删除模型失败');
  }
}

function handleSearch(value) {
  searchQuery.value = value || '';
  currentPage.value = 1;
}

watch([filteredConfigs, pageSize], () => {
  const maxPage = Math.max(1, Math.ceil(filteredConfigs.value.length / pageSize.value));
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage;
  }
});

onMounted(fetchConfigs);
</script>

<template>
  <OpsSectionFrame>
    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <AppSectionCard title="模型列表" desc="统一查看模型状态、调用热度与最近维护动作。" admin>
      <template #header>
        <el-button type="primary" @click="openCreate">
          <AppIcon name="plus" />
          新增模型
        </el-button>
      </template>

      <div class="model-category-strip" aria-label="模型类型分布">
        <article
          v-for="item in capabilityCounts"
          :key="item.value"
          :class="['model-category-strip__item', `is-${item.value}`, { 'is-empty': item.count === 0 }]"
        >
          <span class="model-category-strip__label">{{ item.label }}</span>
          <strong class="model-category-strip__value">{{ formatCount(item.count) }}</strong>
        </article>
      </div>

      <AdminDataTable
        :data="paginatedConfigs"
        :columns="tableColumns"
        :loading="isLoading"
        :error="errorMsg"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="filteredConfigs.length"
        :sort-field="sortField"
        :sort-order="sortOrder"
        column-control-label="列排序"
        :allow-column-reorder="true"
        search-placeholder="搜索模型名称、描述、参数规模"
        @search="handleSearch"
        @retry="fetchConfigs"
        @update:current-page="currentPage = $event"
        @update:page-size="pageSize = $event"
        @update:sort-field="sortField = $event"
        @update:sort-order="sortOrder = $event"
      >
        <template #name="{ row }">
          <div class="model-row__name">
            <strong>{{ row.name }}</strong>
            <span class="muted-text">{{ row.model_name }}</span>
          </div>
        </template>

        <template #capability="{ row }">
          <div class="model-row__type">
            <span :class="['model-pill', `is-${row.capability || 'unknown'}`]">{{ capabilityLabel(row.capability) }}</span>
            <span class="muted-text">{{ providerLabel(row.provider) }}</span>
          </div>
        </template>

        <template #parameter_scale="{ row }">
          <span>{{ row.parameter_scale || '未填写' }}</span>
        </template>

        <template #status="{ row }">
          <span :class="['model-status', row.is_active ? 'is-active' : 'is-idle']">
            {{ row.is_active ? '已启用' : '未启用' }}
          </span>
        </template>

        <template #invocation_count="{ row }">
          <span class="mono-text">{{ formatCount(row.invocation_count) }}</span>
        </template>

        <template #updated_at="{ row }">
          <span>{{ formatUpdatedAt(row.updated_at) }}</span>
        </template>

        <template #description="{ row }">
          <span>{{ row.description || '未填写描述' }}</span>
        </template>

        <template #actions="{ row }">
          <div class="model-row__actions">
            <el-tooltip :content="row.is_active ? '已启动' : '启动'" placement="top">
              <button
                type="button"
                class="model-row__icon-button"
                :disabled="row.is_active"
                :aria-label="row.is_active ? `模型 ${row.name} 已启动` : `启动模型 ${row.name}`"
                @click="activateModel(row)"
              >
                <AppIcon name="play" />
              </button>
            </el-tooltip>

            <el-tooltip content="编辑" placement="top">
              <button
                type="button"
                class="model-row__icon-button"
                :aria-label="`编辑模型 ${row.name}`"
                @click="openEdit(row)"
              >
                <AppIcon name="edit" />
              </button>
            </el-tooltip>

            <el-tooltip content="删除" placement="top">
              <button
                type="button"
                class="model-row__icon-button model-row__icon-button--danger"
                :aria-label="`删除模型 ${row.name}`"
                @click="deleteModel(row)"
              >
                <AppIcon name="trash" />
              </button>
            </el-tooltip>
          </div>
        </template>
      </AdminDataTable>
    </AppSectionCard>

    <el-drawer v-model="drawerVisible" size="560px" :title="drawerTitle" destroy-on-close>
      <el-form label-position="top" class="model-form">
        <div class="model-form__grid">
          <el-form-item label="模型名称">
            <el-input v-model="form.name" placeholder="例如：deepseek-primary" />
          </el-form-item>

          <el-form-item label="模型标识">
            <el-input v-model="form.model_name" placeholder="例如：deepseek-chat" />
          </el-form-item>

          <el-form-item label="模型类型">
            <el-select v-model="form.capability">
              <el-option v-for="item in capabilityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>

          <el-form-item label="Provider">
            <el-select v-model="form.provider">
              <el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>

          <el-form-item label="参数规模">
            <el-input v-model="form.parameter_scale" placeholder="例如：7B / 32B / 671B" />
          </el-form-item>

          <el-form-item label="接入地址">
            <el-input v-model="form.endpoint" placeholder="https://api.example.com/v1" />
          </el-form-item>
        </div>

        <el-form-item label="模型描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="补充模型用途、擅长任务或接入说明。" />
        </el-form-item>

        <div class="model-form__grid">
          <el-form-item :label="form.has_api_key ? `API Key（当前：${form.api_key_masked || '已配置'}）` : 'API Key'">
            <el-input v-model="form.api_key" type="password" show-password placeholder="留空则保留当前值" />
          </el-form-item>

          <el-form-item label="启用状态">
            <el-switch v-model="form.is_active" inline-prompt active-text="启用" inactive-text="停用" />
          </el-form-item>

          <template v-if="supportsTokenOptions">
            <el-form-item label="Temperature">
              <el-input-number v-model="form.temperature" :step="0.1" :min="0" :max="2" controls-position="right" />
            </el-form-item>

            <el-form-item label="Max tokens">
              <el-input-number v-model="form.max_tokens" :step="128" :min="1" :max="65536" controls-position="right" />
            </el-form-item>
          </template>
        </div>
      </el-form>

      <template #footer>
        <div class="model-form__footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="saveModel">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
.model-overview-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.model-overview-metrics__card {
  display: grid;
  gap: 14px;
  min-height: 112px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--surface-1);
}

.model-overview-metrics__card.is-brand {
  background:
    radial-gradient(circle at top right, rgba(36, 87, 197, 0.28), transparent 38%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--surface-1);
}

.model-overview-metrics__card.is-success {
  background:
    radial-gradient(circle at top right, rgba(33, 129, 92, 0.24), transparent 38%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--surface-1);
}

.model-overview-metrics__card.is-warning {
  background:
    radial-gradient(circle at top right, rgba(183, 121, 31, 0.22), transparent 38%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--surface-1);
}

.model-overview-metrics__card.is-accent {
  background:
    radial-gradient(circle at top right, rgba(141, 208, 208, 0.22), transparent 38%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)),
    var(--surface-1);
}

.model-overview-metrics__head,
.model-overview-metrics__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.model-overview-metrics__label {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.model-overview-metrics__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.model-overview-metrics__value {
  color: var(--text-primary);
  font-size: clamp(1.55rem, 2vw, 2rem);
  line-height: 1.05;
  letter-spacing: -0.05em;
}

.model-overview-metrics__badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}

.model-category-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.model-category-strip__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 56px;
  padding: 0 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.model-category-strip__item.is-chat {
  border-color: rgba(36, 87, 197, 0.32);
  background: rgba(36, 87, 197, 0.12);
}

.model-category-strip__item.is-embedding {
  border-color: rgba(141, 208, 208, 0.34);
  background: rgba(141, 208, 208, 0.12);
}

.model-category-strip__item.is-rerank {
  border-color: rgba(213, 164, 65, 0.34);
  background: rgba(213, 164, 65, 0.12);
}

.model-category-strip__item.is-empty {
  opacity: 0.72;
}

.model-category-strip__label {
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 600;
}

.model-category-strip__value {
  color: var(--text-primary);
  font-size: 1rem;
}

.model-row__type {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.model-row__name {
  display: grid;
  gap: 4px;
}

.model-row__name strong {
  color: var(--text-primary);
}

.model-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(213, 164, 65, 0.32);
  border-radius: 999px;
  color: var(--text-primary);
  background: rgba(213, 164, 65, 0.16);
  font-size: 0.75rem;
  font-weight: 600;
}

.model-pill.is-chat {
  border-color: rgba(36, 87, 197, 0.42);
  background: rgba(36, 87, 197, 0.18);
}

.model-pill.is-embedding {
  border-color: rgba(141, 208, 208, 0.42);
  background: rgba(141, 208, 208, 0.18);
}

.model-pill.is-rerank {
  border-color: rgba(213, 164, 65, 0.42);
  background: rgba(213, 164, 65, 0.2);
}

.model-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 0.75rem;
  font-weight: 700;
}

.model-status.is-active {
  color: #effcf5;
  border-color: rgba(66, 194, 138, 0.42);
  background: rgba(33, 129, 92, 0.38);
}

.model-status.is-idle {
  color: #dbe3ef;
  border-color: rgba(157, 173, 196, 0.34);
  background: rgba(71, 86, 110, 0.42);
}

.model-row__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-row__icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(157, 173, 196, 0.16);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

.model-row__icon-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(213, 164, 65, 0.26);
  transform: translateY(-1px);
}

.model-row__icon-button:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}

.model-row__icon-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.model-row__icon-button--danger:hover:not(:disabled) {
  border-color: rgba(196, 73, 61, 0.3);
  color: #ffd6d2;
}

.model-form,
.model-form__grid {
  display: grid;
  gap: 18px;
}

.model-form__grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.model-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  width: 100%;
}

@media (max-width: 1120px) {
  .model-overview-metrics,
  .model-category-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .model-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
