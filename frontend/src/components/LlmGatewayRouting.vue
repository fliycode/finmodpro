<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import { useFlash } from '../lib/flash.js';
import {
  buildRoutePayload,
  cloneRouteOptions,
  getRouteDeleteBlockReason,
} from '../lib/llm-gateway.js';
import OpsCommandDeck from './admin/ops/OpsCommandDeck.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const flash = useFlash();
const configs = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);
const isMigrating = ref(false);
const errorMsg = ref('');
const drawerVisible = ref(false);
const editingId = ref(null);
const originalOptions = ref({});

const defaultFormState = () => ({
  name: '',
  capability: 'chat',
  alias: 'chat-default',
  endpoint: 'http://localhost:4000',
  upstream_provider: 'openai',
  upstream_model: '',
  fallback_aliases_text: '',
  weight: 1,
  input_price_per_million: 0,
  output_price_per_million: 0,
  api_key: '',
  has_api_key: false,
  api_key_masked: '',
  is_active: false,
});

const form = reactive(defaultFormState());

const litellmConfigs = computed(() => configs.value.filter((config) => config.provider === 'litellm'));
const legacyConfigs = computed(() => configs.value.filter((config) => config.provider !== 'litellm'));

const defaultsByCapability = computed(() => ({
  chat: litellmConfigs.value.find((config) => config.capability === 'chat' && config.is_active)
    || configs.value.find((config) => config.capability === 'chat' && config.is_active)
    || null,
  embedding: litellmConfigs.value.find((config) => config.capability === 'embedding' && config.is_active)
    || configs.value.find((config) => config.capability === 'embedding' && config.is_active)
    || null,
  rerank: litellmConfigs.value.find((config) => config.capability === 'rerank' && config.is_active)
    || configs.value.find((config) => config.capability === 'rerank' && config.is_active)
    || null,
}));

const routeMetrics = computed(() => ([
  {
    key: 'litellm-routes',
    label: 'LiteLLM routes',
    value: litellmConfigs.value.length,
    note: '当前纳入统一网关管理的路由数量。',
  },
  {
    key: 'active-defaults',
    label: '默认链路',
    value: Object.values(defaultsByCapability.value).filter(Boolean).length,
    note: 'chat / embedding / rerank 中已有默认激活的数量。',
  },
  {
    key: 'key-covered',
    label: '已配置 key',
    value: litellmConfigs.value.filter((config) => config.has_api_key).length,
    note: '用于判断哪些路由已经具备可调用凭据。',
  },
  {
    key: 'legacy',
    label: 'Legacy configs',
    value: legacyConfigs.value.length,
    note: '仍保留的兼容 provider，不作为主治理入口。',
  },
]));

const drawerTitle = computed(() => (editingId.value ? '编辑 LiteLLM 路由' : '新增 LiteLLM 路由'));
const frameMeta = computed(() => [
  `LiteLLM 路由：${litellmConfigs.value.length}`,
  `默认链路：${Object.values(defaultsByCapability.value).filter(Boolean).length}`,
  `Legacy：${legacyConfigs.value.length}`,
]);

const fetchConfigs = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const data = await llmApi.getModelConfigs();
    configs.value = normalizeModelConfigPayload(data);
  } catch (error) {
    errorMsg.value = error.message || '加载模型配置失败';
    configs.value = [];
  } finally {
    isLoading.value = false;
  }
};

const resetForm = () => {
  Object.assign(form, defaultFormState());
  editingId.value = null;
  originalOptions.value = {};
};

const setDefaultAliasForCapability = (capability) => {
  if (capability === 'embedding') {
    form.alias = 'embed-default';
    form.upstream_model = 'text-embedding-3-small';
    return;
  }
  if (capability === 'rerank') {
    form.alias = 'rerank-default';
    form.upstream_model = 'rerank-default';
    return;
  }
  form.alias = 'chat-default';
  form.upstream_model = 'gpt-4o';
};

const openCreate = (capability = 'chat') => {
  resetForm();
  form.capability = capability;
  setDefaultAliasForCapability(capability);
  drawerVisible.value = true;
};

const openEdit = (config) => {
  resetForm();
  editingId.value = config.id;
  originalOptions.value = cloneRouteOptions(config.options || {});
  form.name = config.name;
  form.capability = config.capability;
  form.alias = config.alias || config.model_name;
  form.endpoint = config.endpoint;
  form.upstream_provider = config.upstream_provider || 'openai';
  form.upstream_model = config.upstream_model || '';
  form.fallback_aliases_text = Array.isArray(config.fallback_aliases)
    ? config.fallback_aliases.join(', ')
    : '';
  form.weight = Number(config.weight ?? 1);
  form.input_price_per_million = Number(config.input_price_per_million ?? 0);
  form.output_price_per_million = Number(config.output_price_per_million ?? 0);
  form.has_api_key = Boolean(config.has_api_key);
  form.api_key_masked = config.api_key_masked || '';
  form.is_active = Boolean(config.is_active);
  drawerVisible.value = true;
};

const buildPayload = () => {
  return buildRoutePayload({
    originalOptions: originalOptions.value,
    editingId: editingId.value,
    form,
  });
};

const saveRoute = async () => {
  isSaving.value = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      await llmApi.updateModelConfig(editingId.value, payload);
      flash.success('路由已更新');
    } else {
      await llmApi.createModelConfig(payload);
      flash.success('路由已创建');
    }
    drawerVisible.value = false;
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '保存 LiteLLM 路由失败');
  } finally {
    isSaving.value = false;
  }
};

const activateRoute = async (config) => {
  try {
    await llmApi.activateModelConfig(config.id, true);
    flash.success(`已切换默认链路：${config.alias || config.model_name}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '切换默认链路失败');
  }
};

const syncRoute = async (config) => {
  try {
    await llmApi.syncModelConfigToLiteLLM(config.id);
    flash.success(`已同步路由：${config.alias || config.model_name}`);
  } catch (error) {
    flash.error(error.message || '同步路由失败');
  }
};

const migrateRoutes = async () => {
  isMigrating.value = true;
  try {
    await llmApi.migrateToLiteLLM();
    flash.success('已执行 LiteLLM 迁移');
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '迁移到 LiteLLM 失败');
  } finally {
    isMigrating.value = false;
  }
};

const testConnection = async () => {
  isTesting.value = true;
  try {
    const payload = buildPayload();
    await llmApi.testModelConfigConnection({
      capability: payload.capability,
      provider: payload.provider,
      model_name: payload.model_name,
      endpoint: payload.endpoint,
      options: payload.options,
    });
    flash.success('连通性测试通过');
  } catch (error) {
    flash.error(error.message || '连通性测试失败');
  } finally {
    isTesting.value = false;
  }
};

const deleteRoute = async (config) => {
  const deleteBlockReason = getRouteDeleteBlockReason(config);
  if (deleteBlockReason) {
    flash.error(deleteBlockReason);
    return;
  }
  const alias = config.alias || config.model_name || config.name || '未命名路由';
  if (!window.confirm(`确定删除路由“${alias}”吗？删除后需要重新同步或重新创建才能恢复。`)) {
    return;
  }
  try {
    await llmApi.deleteModelConfig(config.id);
    flash.success(`已删除路由：${alias}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || '删除 LiteLLM 路由失败');
  }
};

const formatCapability = (value) => {
  if (value === 'embedding') {
    return '向量';
  }
  if (value === 'rerank') {
    return '重排';
  }
  return '对话';
};

const formatUpdatedAt = (value) => {
  if (!value) {
    return '未记录';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

onMounted(fetchConfigs);
</script>

<template>
  <OpsSectionFrame
    eyebrow="War room / Models & routing"
    title="Models / Routing"
    summary="把 alias → upstream mapping、默认模型、fallback / 权重、key 状态与同步动作放进同一页，直接回答“当前默认路由是谁、后备链路是谁、有没有凭据、有没有同步”。"
    :meta="frameMeta"
  >
    <template #actions>
      <div class="gateway-page__hero-actions">
        <el-button :loading="isLoading" @click="fetchConfigs">刷新</el-button>
        <el-button type="primary" plain :loading="isMigrating" @click="migrateRoutes">迁移到 LiteLLM</el-button>
        <el-button type="primary" @click="openCreate('chat')">新增路由</el-button>
      </div>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <template #status-band>
      <OpsStatusBand :items="routeMetrics" />
    </template>

    <OpsCommandDeck>
      <AppSectionCard title="默认模型" desc="按 capability 直接展示当前默认链路，避免在大表里来回寻找激活项。" admin>
        <div class="route-default-grid">
          <article v-for="(config, key) in defaultsByCapability" :key="key" class="route-default-card">
            <span class="route-default-card__eyebrow">{{ formatCapability(key) }}</span>
            <strong class="route-default-card__title">{{ config?.alias || '尚未启用' }}</strong>
            <p class="route-default-card__meta">上游：{{ config?.upstream_model || '未登记' }}</p>
            <p class="route-default-card__meta">Provider：{{ config?.upstream_provider || config?.provider || '未配置' }}</p>
            <p class="route-default-card__meta">Key：{{ config?.has_api_key ? '已配置' : '未配置' }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard v-if="legacyConfigs.length" title="兼容保留项" desc="这些配置继续保留用于兼容或回退，但不再作为统一网关主治理入口。" admin>
        <div class="legacy-grid">
          <article v-for="config in legacyConfigs" :key="config.id" class="legacy-card">
            <strong>{{ config.name }}</strong>
            <p>{{ config.provider }} · {{ formatCapability(config.capability) }}</p>
            <p class="mono-text">{{ config.endpoint }}</p>
          </article>
        </div>
      </AppSectionCard>
    </OpsCommandDeck>

    <OpsInspectorDrawer title="Route registry" desc="以高密度表格展示 alias、fallback、权重和 key 覆盖情况。">
      <template #header>
        <div class="inline-actions">
          <el-button size="small" @click="openCreate('chat')">新增对话</el-button>
          <el-button size="small" @click="openCreate('embedding')">新增向量</el-button>
        </div>
      </template>

      <el-table :data="litellmConfigs" row-key="id" stripe>
        <el-table-column prop="alias" label="Alias" min-width="160" />
        <el-table-column label="上游映射" min-width="220">
          <template #default="{ row }">
            <div class="table-stack">
              <strong>{{ row.upstream_model || '未登记' }}</strong>
              <span class="muted-text">{{ row.upstream_provider || 'provider 未登记' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Capability" min-width="90">
          <template #default="{ row }">
            {{ formatCapability(row.capability) }}
          </template>
        </el-table-column>
        <el-table-column label="Fallback" min-width="160">
          <template #default="{ row }">
            <span v-if="row.fallback_aliases.length">{{ row.fallback_aliases.join(', ') }}</span>
            <span v-else class="muted-text">无</span>
          </template>
        </el-table-column>
        <el-table-column prop="weight" label="权重" width="90" />
        <el-table-column label="Key" width="130">
          <template #default="{ row }">
            <span>{{ row.has_api_key ? row.api_key_masked : '未配置' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
              {{ row.is_active ? '当前默认' : '候选' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">
            {{ formatUpdatedAt(row.updated_at) }}
          </template>
        </el-table-column>
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <div class="route-actions">
                <el-button size="small" @click="openEdit(row)">编辑</el-button>
                <el-button size="small" @click="syncRoute(row)">同步</el-button>
                <el-button size="small" type="primary" plain :disabled="row.is_active" @click="activateRoute(row)">
                  设为默认
                </el-button>
                <el-button size="small" type="danger" plain @click="deleteRoute(row)">
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
      </el-table>
    </OpsInspectorDrawer>

    <el-drawer v-model="drawerVisible" size="560px" :title="drawerTitle" destroy-on-close>
      <el-form label-position="top">
        <div class="gateway-form-grid">
          <el-form-item label="名称">
            <el-input v-model="form.name" placeholder="例如：chat-default-route" />
          </el-form-item>
          <el-form-item label="Capability">
            <el-select v-model="form.capability" @change="setDefaultAliasForCapability">
              <el-option label="对话" value="chat" />
              <el-option label="向量" value="embedding" />
              <el-option label="重排" value="rerank" />
            </el-select>
          </el-form-item>
          <el-form-item label="Alias">
            <el-input v-model="form.alias" placeholder="例如：chat-default" />
          </el-form-item>
          <el-form-item label="Endpoint">
            <el-input v-model="form.endpoint" placeholder="http://localhost:4000" />
          </el-form-item>
          <el-form-item label="上游 Provider">
            <el-input v-model="form.upstream_provider" placeholder="openai / anthropic / azure" />
          </el-form-item>
          <el-form-item label="上游模型">
            <el-input v-model="form.upstream_model" placeholder="例如：gpt-4o" />
          </el-form-item>
          <el-form-item label="Fallback alias">
            <el-input
              v-model="form.fallback_aliases_text"
              type="textarea"
              :rows="3"
              placeholder="多个 alias 用逗号分隔"
            />
          </el-form-item>
          <el-form-item label="权重">
            <el-input-number v-model="form.weight" :min="1" :step="1" />
          </el-form-item>
          <el-form-item label="输入定价 / 百万 tokens（USD）">
            <el-input-number v-model="form.input_price_per_million" :min="0" :step="0.01" :precision="4" />
          </el-form-item>
          <el-form-item label="输出定价 / 百万 tokens（USD）">
            <el-input-number v-model="form.output_price_per_million" :min="0" :step="0.01" :precision="4" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="form.api_key" type="password" show-password placeholder="留空表示保留当前 key" />
            <div v-if="form.has_api_key" class="gateway-form-hint">当前已配置：{{ form.api_key_masked }}</div>
          </el-form-item>
          <el-form-item label="设为默认">
            <el-switch v-model="form.is_active" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="gateway-drawer-actions">
          <el-button :loading="isTesting" @click="testConnection">连通性测试</el-button>
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="saveRoute">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
.gateway-page__hero--routing {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 250, 0.94)),
    radial-gradient(circle at top right, rgba(36, 87, 197, 0.09), transparent 34%);
}

.gateway-page__hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.gateway-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.gateway-metric-card,
.route-default-card,
.legacy-card {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-1);
}

.gateway-metric-card__label,
.route-default-card__eyebrow {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.gateway-metric-card__value,
.route-default-card__title {
  display: block;
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 28px;
}

.gateway-metric-card__note,
.route-default-card__meta,
.legacy-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.route-default-grid,
.legacy-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.table-stack {
  display: grid;
  gap: 4px;
}

.route-actions {
  display: grid;
  grid-template-columns: repeat(2, max-content);
  gap: 8px;
  justify-content: start;
}

.gateway-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
}

.gateway-form-grid :deep(.el-form-item:nth-child(7)),
.gateway-form-grid :deep(.el-form-item:nth-child(9)),
.gateway-form-grid :deep(.el-form-item:nth-child(10)) {
  grid-column: 1 / -1;
}

.gateway-form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.gateway-drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
}

@media (max-width: 1120px) {
  .gateway-metric-strip,
  .route-default-grid,
  .legacy-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .gateway-metric-strip,
  .route-default-grid,
  .legacy-grid,
  .gateway-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
