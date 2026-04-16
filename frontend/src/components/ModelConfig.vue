<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { llmApi, normalizeModelConfigPayload } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";
import AppSectionCard from "./ui/AppSectionCard.vue";

const flash = useFlash();
const configs = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);
const errorMsg = ref("");
const drawerVisible = ref(false);
const editingId = ref(null);
const fineTuneRuns = ref([]);
const fineTuneLoading = ref(false);
const fineTuneSaving = ref(false);
const fineTuneError = ref("");
const fineTuneDrawerVisible = ref(false);
const editingFineTuneId = ref(null);
const fineTuneFilterModelId = ref("");

const defaultFormState = () => ({
  name: "",
  capability: "chat",
  provider: "litellm",
  model_name: "chat-default",
  endpoint: "http://localhost:4000",
  api_key: "",
  temperature: 0.2,
  max_tokens: 1024,
  is_active: false,
  has_api_key: false,
  api_key_masked: "",
});

const defaultFineTuneFormState = () => ({
  base_model_id: "",
  dataset_name: "",
  dataset_version: "",
  strategy: "lora",
  runner_name: "",
  training_config_json: "{\n  \"epochs\": 3\n}",
  status: "pending",
  artifact_path: "",
  metrics_json: "{\n  \"f1_score\": 0.9\n}",
  notes: "",
});

const form = reactive(defaultFormState());
const fineTuneForm = reactive(defaultFineTuneFormState());

const chatConfigs = computed(() =>
  configs.value.filter((c) => ["chat", "llm", "generation"].includes(String(c.capability).toLowerCase())),
);
const embeddingConfigs = computed(() =>
  configs.value.filter((c) => ["embedding", "embed", "vector"].includes(String(c.capability).toLowerCase())),
);
const fineTuneModelOptions = computed(() => configs.value.map((config) => ({
  value: config.id,
  label: `${config.name} · ${config.model_name}`,
})));
const supportsTokenOptions = computed(() => ["deepseek", "litellm"].includes(form.provider));
const drawerTitle = computed(() => (editingId.value ? "编辑模型配置" : "新增模型配置"));
const fineTuneDrawerTitle = computed(() => (editingFineTuneId.value ? "编辑微调登记" : "新增微调登记"));

const resetForm = () => {
  Object.assign(form, defaultFormState());
  editingId.value = null;
};

const openCreate = (capability = "chat") => {
  resetForm();
  form.capability = capability;
  form.provider = "litellm";
  form.model_name = capability === "embedding" ? "embed-default" : "chat-default";
  form.endpoint = "http://localhost:4000";
  drawerVisible.value = true;
};

const openEdit = (config) => {
  resetForm();
  editingId.value = config.id;
  form.name = config.name;
  form.capability = config.capability;
  form.provider = config.provider;
  form.model_name = config.model_name;
  form.endpoint = config.endpoint;
  form.is_active = config.is_active;
  form.temperature = Number(config.options?.temperature ?? 0.2);
  form.max_tokens = Number(config.options?.max_tokens ?? 1024);
  form.has_api_key = Boolean(config.has_api_key);
  form.api_key_masked = config.api_key_masked || "";
  drawerVisible.value = true;
};

const buildPayload = () => {
  const options = {};
  if (supportsTokenOptions.value) {
    if (form.api_key.trim()) {
      options.api_key = form.api_key.trim();
    }
    options.temperature = Number(form.temperature);
    options.max_tokens = Number(form.max_tokens);
  }
  return {
    name: form.name.trim(),
    capability: form.capability,
    provider: form.provider,
    model_name: form.model_name.trim(),
    endpoint: form.endpoint.trim(),
    is_active: Boolean(form.is_active),
    options,
  };
};

const resetFineTuneForm = () => {
  Object.assign(fineTuneForm, defaultFineTuneFormState());
  editingFineTuneId.value = null;
};

const openCreateFineTune = (baseModelId = "") => {
  resetFineTuneForm();
  fineTuneForm.base_model_id = baseModelId || fineTuneFilterModelId.value || chatConfigs.value[0]?.id || configs.value[0]?.id || "";
  fineTuneDrawerVisible.value = true;
};

const openEditFineTune = (run) => {
  resetFineTuneForm();
  editingFineTuneId.value = run.id;
  fineTuneForm.base_model_id = run.base_model_id;
  fineTuneForm.dataset_name = run.dataset_name;
  fineTuneForm.dataset_version = run.dataset_version;
  fineTuneForm.strategy = run.strategy;
  fineTuneForm.runner_name = run.runner_name || "";
  fineTuneForm.training_config_json = JSON.stringify(run.training_config || {}, null, 2);
  fineTuneForm.status = run.status;
  fineTuneForm.artifact_path = run.artifact_path;
  fineTuneForm.metrics_json = JSON.stringify(run.metrics || {}, null, 2);
  fineTuneForm.notes = run.notes || "";
  fineTuneDrawerVisible.value = true;
};

const buildFineTunePayload = () => {
  if (!fineTuneForm.base_model_id) {
    throw new Error("请选择基础模型");
  }

  let trainingConfig = {};
  if (fineTuneForm.training_config_json.trim()) {
    try {
      trainingConfig = JSON.parse(fineTuneForm.training_config_json);
    } catch (error) {
      throw new Error("训练配置 JSON 格式不正确");
    }
  }

  const payload = {
    base_model_id: Number(fineTuneForm.base_model_id),
    dataset_name: fineTuneForm.dataset_name.trim(),
    dataset_version: fineTuneForm.dataset_version.trim(),
    strategy: fineTuneForm.strategy.trim() || "lora",
    runner_name: fineTuneForm.runner_name.trim(),
    training_config: trainingConfig,
    notes: fineTuneForm.notes.trim(),
  };

  if (!editingFineTuneId.value) {
    return payload;
  }

  let metrics = {};
  if (fineTuneForm.metrics_json.trim()) {
    try {
      metrics = JSON.parse(fineTuneForm.metrics_json);
    } catch (error) {
      throw new Error("微调指标 JSON 格式不正确");
    }
  }

  return {
    ...payload,
    status: fineTuneForm.status,
    artifact_path: fineTuneForm.artifact_path.trim(),
    metrics,
  };
};

const fetchConfigs = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getModelConfigs();
    configs.value = normalizeModelConfigPayload(data);
    if (!fineTuneFilterModelId.value && chatConfigs.value[0]?.id) {
      fineTuneFilterModelId.value = chatConfigs.value[0].id;
    }
  } catch (error) {
    console.error("Failed to fetch model configs:", error);
    errorMsg.value = error.message || "加载模型配置失败";
    configs.value = [];
  } finally {
    isLoading.value = false;
  }
};

const fetchFineTunes = async () => {
  fineTuneLoading.value = true;
  fineTuneError.value = "";
  try {
    const data = await llmApi.getFineTuneRuns({
      base_model_id: fineTuneFilterModelId.value || undefined,
    });
    fineTuneRuns.value = Array.isArray(data?.fine_tune_runs) ? data.fine_tune_runs : [];
  } catch (error) {
    console.error("Failed to fetch fine-tune runs:", error);
    fineTuneError.value = error.message || "加载微调记录失败";
    fineTuneRuns.value = [];
  } finally {
    fineTuneLoading.value = false;
  }
};

const toggleActivation = async (config) => {
  if (!config) return;
  try {
    const newStatus = !config.is_active;
    await llmApi.activateModelConfig(config.id, newStatus);
    flash.success(`${config.name}已${newStatus ? "启用" : "停用"}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || "操作失败");
  }
};

const submitForm = async () => {
  if (!form.name.trim() || !form.model_name.trim() || !form.endpoint.trim()) {
    flash.error("请完整填写配置名称、模型名和接口地址");
    return;
  }
  isSaving.value = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      await llmApi.updateModelConfig(editingId.value, payload);
      flash.success("模型配置已更新");
    } else {
      await llmApi.createModelConfig(payload);
      flash.success("模型配置已创建");
    }
    drawerVisible.value = false;
    resetForm();
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || "保存失败");
  } finally {
    isSaving.value = false;
  }
};

const runConnectionTest = async () => {
  if (!form.model_name.trim() || !form.endpoint.trim()) {
    flash.error("请先填写模型名和接口地址");
    return;
  }
  isTesting.value = true;
  try {
    await llmApi.testModelConfigConnection({
      capability: form.capability,
      provider: form.provider,
      model_name: form.model_name.trim(),
      endpoint: form.endpoint.trim(),
      options: buildPayload().options,
    });
    flash.success("连接测试通过");
  } catch (error) {
    flash.error(error.message || "连接测试失败");
  } finally {
    isTesting.value = false;
  }
};

const submitFineTune = async () => {
  fineTuneSaving.value = true;
  try {
    const payload = buildFineTunePayload();
    if (editingFineTuneId.value) {
      await llmApi.updateFineTuneRun(editingFineTuneId.value, payload);
      flash.success("微调登记已更新");
    } else {
      const result = await llmApi.createFineTuneRun(payload);
      flash.success(result?.fine_tune_run?.callback_token ? "微调任务已创建，回调令牌已生成" : "微调任务已创建");
    }
    fineTuneDrawerVisible.value = false;
    resetFineTuneForm();
    await fetchFineTunes();
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || "保存微调登记失败");
  } finally {
    fineTuneSaving.value = false;
  }
};

const formatFineTuneMetrics = (metrics) => {
  if (!metrics || Object.keys(metrics).length === 0) {
    return "暂无指标";
  }
  return Object.entries(metrics)
    .map(([key, value]) => `${key}: ${value}`)
    .join(" / ");
};

const formatFineTuneLineage = (config) => {
  const count = Number(config.fine_tune_run_count || 0);
  if (!count) {
    return "暂无登记";
  }
  const dataset = config.latest_fine_tune_dataset || "未命名数据集";
  const status = config.latest_fine_tune_status || "unknown";
  return `${count} 次 / ${dataset} / ${status}`;
};

const formatFineTuneControlPlane = (run) => {
  const exportStatus = run.dataset_manifest?.export_status || "pending";
  const callbackState = run.callback_token ? "callback 已签发" : "callback 已隐藏";
  const registration = run.registered_model_config_id ? `候选模型 #${run.registered_model_config_id}` : "未注册候选模型";
  return `${run.run_key || "未分配 run_key"} / export:${exportStatus} / ${callbackState} / ${registration}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
};

onMounted(fetchConfigs);
onMounted(fetchFineTunes);

watch(fineTuneFilterModelId, () => {
  fetchFineTunes();
});
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Models</div>
        <h1 class="page-hero__title">模型配置管理</h1>
        <p class="page-hero__subtitle">
          管理平台级对话和向量模型。第一阶段支持 LiteLLM、Ollama 与 DeepSeek，智能问答会自动读取当前启用的 chat 模型。
        </p>
      </div>
      <div class="model-page__actions">
        <el-button @click="fetchConfigs" :loading="isLoading">刷新配置</el-button>
        <el-button type="primary" @click="openCreate('chat')">新增对话模型</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard title="对话模型" desc="支持 LiteLLM、Ollama 与 DeepSeek。启用新模型后，智能问答和其它 chat 能力会自动切换。" admin>
      <div v-if="isLoading && chatConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="chatConfigs.length === 0" class="admin-empty-state">暂无对话模型配置</div>
      <el-table v-else :data="chatConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名称" min-width="160" />
        <el-table-column prop="provider" label="Provider" width="120" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="接口地址" min-width="220">
          <template #default="{ row }">
            <span class="mono-text">{{ row.endpoint || "默认" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="密钥状态" width="130">
          <template #default="{ row }">
            <span class="muted-text">{{ row.has_api_key ? row.api_key_masked : "未配置" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "已启用" : "未启用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="微调线索" min-width="220">
          <template #default="{ row }">
            <div class="muted-text lineage-text">
              {{ formatFineTuneLineage(row) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
              <el-button size="small" :type="row.is_active ? 'danger' : 'primary'" plain @click="toggleActivation(row)">
                {{ row.is_active ? "停用" : "启用" }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <AppSectionCard title="向量模型" desc="支持 LiteLLM 与 Ollama embedding 配置。" admin>
      <template #header>
        <el-button type="primary" @click="openCreate('embedding')">新增向量模型</el-button>
      </template>
      <div v-if="isLoading && embeddingConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="embeddingConfigs.length === 0" class="admin-empty-state">暂无向量模型配置</div>
      <el-table v-else :data="embeddingConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名称" min-width="160" />
        <el-table-column prop="provider" label="Provider" width="120" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="接口地址" min-width="220">
          <template #default="{ row }">
            <span class="mono-text">{{ row.endpoint || "默认" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "已启用" : "未启用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="微调线索" min-width="220">
          <template #default="{ row }">
            <div class="muted-text lineage-text">
              {{ formatFineTuneLineage(row) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
              <el-button size="small" :type="row.is_active ? 'danger' : 'primary'" plain @click="toggleActivation(row)">
                {{ row.is_active ? "停用" : "启用" }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <AppSectionCard title="微调控制面" desc="训练执行仍保持外部运行，这里登记数据集、导出、回调与候选模型回流状态。" admin>
      <div class="registry-toolbar">
        <el-select
          v-model="fineTuneFilterModelId"
          filterable
          clearable
          placeholder="按基础模型筛选"
          style="min-width: 280px"
        >
          <el-option
            v-for="option in fineTuneModelOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div class="registry-toolbar__actions">
          <el-button @click="fetchFineTunes" :loading="fineTuneLoading">刷新微调记录</el-button>
          <el-button type="primary" @click="openCreateFineTune()">登记微调</el-button>
        </div>
      </div>
      <el-alert
        v-if="fineTuneError"
        :title="fineTuneError"
        type="error"
        show-icon
        :closable="false"
        class="registry-alert"
      />
      <div v-if="fineTuneLoading && fineTuneRuns.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="fineTuneRuns.length === 0" class="admin-empty-state">暂无微调登记</div>
      <el-table v-else :data="fineTuneRuns" stripe style="width: 100%">
        <el-table-column label="基础模型" min-width="180">
          <template #default="{ row }">
            <div>{{ row.base_model_name }}</div>
            <div class="muted-text">{{ row.base_model_provider }} / {{ row.base_model_capability }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="dataset_name" label="数据集" min-width="160" />
        <el-table-column prop="dataset_version" label="版本" width="120" />
        <el-table-column prop="strategy" label="策略" width="100" />
        <el-table-column label="运行标识" min-width="220">
          <template #default="{ row }">
            <div class="mono-text">{{ row.run_key || '待生成' }}</div>
            <div class="muted-text">{{ row.runner_name || 'runner 未指定' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'succeeded' ? 'success' : row.status === 'running' ? 'warning' : row.status === 'failed' ? 'danger' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="控制面状态" min-width="260">
          <template #default="{ row }">
            <span class="muted-text">{{ formatFineTuneControlPlane(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="产物路径" min-width="220">
          <template #default="{ row }">
            <span class="mono-text">{{ row.artifact_path || '外部训练回写后登记' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="指标" min-width="220">
          <template #default="{ row }">
            <span class="muted-text">{{ formatFineTuneMetrics(row.metrics) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" plain @click="openEditFineTune(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="520px" destroy-on-close>
      <div class="model-form">
        <el-form label-position="top">
          <el-form-item label="配置名称">
            <el-input v-model="form.name" placeholder="例如：DeepSeek 生产模型" />
          </el-form-item>
          <el-form-item label="能力类型">
            <el-select v-model="form.capability" style="width: 100%">
              <el-option label="对话模型" value="chat" />
              <el-option label="向量模型" value="embedding" />
            </el-select>
          </el-form-item>
          <el-form-item label="Provider">
            <el-select v-model="form.provider" style="width: 100%">
              <el-option label="LiteLLM" value="litellm" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="Ollama" value="ollama" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="form.model_name" placeholder="例如：chat-default / embed-default / deepseek-chat" />
          </el-form-item>
          <el-form-item label="接口地址">
            <el-input v-model="form.endpoint" placeholder="例如：http://localhost:4000 或 https://api.deepseek.com" />
          </el-form-item>

          <template v-if="supportsTokenOptions">
            <el-form-item label="API Key">
              <el-input v-model="form.api_key" type="password" show-password placeholder="新建时必填，编辑时留空表示保留原 key" />
              <div v-if="form.has_api_key" class="form-footnote">已保存密钥：{{ form.api_key_masked || "已配置" }}</div>
            </el-form-item>
            <div class="form-grid">
              <el-form-item label="温度">
                <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" style="width: 100%" />
              </el-form-item>
              <el-form-item label="最大输出">
                <el-input-number v-model="form.max_tokens" :min="1" :max="8192" :step="128" style="width: 100%" />
              </el-form-item>
            </div>
          </template>

          <el-form-item>
            <el-switch v-model="form.is_active" active-text="保存后设为当前启用模型" />
          </el-form-item>
        </el-form>

        <div class="drawer-actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button @click="runConnectionTest" :loading="isTesting">测试连接</el-button>
          <el-button type="primary" @click="submitForm" :loading="isSaving">保存配置</el-button>
        </div>
      </div>
    </el-drawer>

    <el-drawer v-model="fineTuneDrawerVisible" :title="fineTuneDrawerTitle" size="560px" destroy-on-close>
      <div class="model-form">
        <el-form label-position="top">
          <el-form-item label="基础模型">
            <el-select v-model="fineTuneForm.base_model_id" filterable style="width: 100%" placeholder="选择基础模型">
              <el-option
                v-for="option in fineTuneModelOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="数据集名称">
              <el-input v-model="fineTuneForm.dataset_name" placeholder="例如：财报基准集" />
            </el-form-item>
            <el-form-item label="数据集版本">
              <el-input v-model="fineTuneForm.dataset_version" placeholder="例如：2026Q1" />
            </el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="策略">
              <el-input v-model="fineTuneForm.strategy" placeholder="例如：lora" />
            </el-form-item>
            <el-form-item label="Runner">
              <el-input v-model="fineTuneForm.runner_name" placeholder="例如：llamafactory-runner-a" />
            </el-form-item>
          </div>
          <el-form-item label="训练配置 JSON">
            <el-input
              v-model="fineTuneForm.training_config_json"
              type="textarea"
              :rows="5"
              placeholder='{"epochs": 3, "learning_rate": 0.0001}'
            />
          </el-form-item>
          <div class="form-grid" v-if="editingFineTuneId">
            <el-form-item label="状态">
              <el-select v-model="fineTuneForm.status" style="width: 100%">
                <el-option label="待处理" value="pending" />
                <el-option label="执行中" value="running" />
                <el-option label="已完成" value="succeeded" />
                <el-option label="失败" value="failed" />
              </el-select>
            </el-form-item>
            <el-form-item label="产物路径">
              <el-input v-model="fineTuneForm.artifact_path" placeholder="例如：/artifacts/runs/ft-20260413" />
            </el-form-item>
          </div>
          <el-form-item v-if="editingFineTuneId" label="指标 JSON">
            <el-input
              v-model="fineTuneForm.metrics_json"
              type="textarea"
              :rows="6"
              placeholder='{"loss": 0.12, "f1_score": 0.92}'
            />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="fineTuneForm.notes" type="textarea" :rows="4" placeholder="记录训练来源、回写状态或人工说明。" />
          </el-form-item>
        </el-form>

        <div class="drawer-actions">
          <el-button @click="fineTuneDrawerVisible = false">取消</el-button>
          <el-button type="primary" @click="submitFineTune" :loading="fineTuneSaving">保存登记</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.model-page__actions {
  display: flex;
  gap: 12px;
}

.table-actions {
  display: flex;
  gap: 8px;
}

.model-form {
  display: grid;
  gap: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-footnote {
  margin-top: 8px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.mono-text {
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}

.muted-text {
  color: var(--app-text-muted);
}

.lineage-text {
  line-height: 1.4;
}

.registry-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}

.registry-toolbar__actions {
  display: flex;
  gap: 12px;
}

.registry-alert {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .model-page__actions,
  .form-grid,
  .drawer-actions,
  .registry-toolbar,
  .registry-toolbar__actions,
  .table-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
