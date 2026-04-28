<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { llmApi, normalizeModelConfigPayload } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";
import {
  buildLlamaFactoryTrainingConfig,
  createLlamaFactoryTrainingFormState,
  LLAMAFACTORY_EVAL_STRATEGY_OPTIONS,
  LLAMAFACTORY_PRECISION_OPTIONS,
  LLAMAFACTORY_REPORT_TO_OPTIONS,
  LLAMAFACTORY_SCHEDULER_OPTIONS,
  LLAMAFACTORY_STRATEGY_OPTIONS,
  normalizeLlamaFactoryTrainingConfig,
} from "../lib/llamafactory-config.js";
import {
  getConsolePageAlerts,
  getInitialFineTuneFilterId,
  shouldShowConsoleConfigRetry,
} from "../lib/llm-console.js";
import AppSectionCard from "./ui/AppSectionCard.vue";

const props = defineProps({
  mode: {
    type: String,
    default: "models",
  },
});

const flash = useFlash();
const configs = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);
const errorMsg = ref("");
const drawerVisible = ref(false);
const editingId = ref(null);
const fineTuneRuns = ref([]);
const fineTuneRunnerServers = ref([]);
const fineTuneLoading = ref(false);
const runnerServerLoading = ref(false);
const fineTuneSaving = ref(false);
const runnerServerSaving = ref(false);
const fineTuneError = ref("");
const fineTuneDrawerVisible = ref(false);
const runnerServerDrawerVisible = ref(false);
const editingFineTuneId = ref(null);
const editingRunnerServerId = ref(null);
const fineTuneFilterModelId = ref("");
const dispatchingFineTuneId = ref(null);

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
  runner_server_id: "",
  dataset_name: "",
  dataset_version: "",
  runner_name: "",
  training: createLlamaFactoryTrainingFormState(),
  status: "pending",
  external_job_id: "",
  artifact_path: "",
  metrics_json: "{\n  \"f1_score\": 0.9\n}",
  notes: "",
});

const defaultRunnerServerFormState = () => ({
  name: "",
  base_url: "",
  auth_token: "",
  default_work_dir: "",
  is_enabled: true,
  has_auth_token: false,
  auth_token_masked: "",
});

const form = reactive(defaultFormState());
const fineTuneForm = reactive(defaultFineTuneFormState());
const runnerServerForm = reactive(defaultRunnerServerFormState());

const chatConfigs = computed(() =>
  configs.value.filter((c) => ["chat", "llm", "generation"].includes(String(c.capability).toLowerCase())),
);
const embeddingConfigs = computed(() =>
  configs.value.filter((c) => ["embedding", "embed", "vector"].includes(String(c.capability).toLowerCase())),
);
const rerankConfigs = computed(() =>
  configs.value.filter((c) => ["rerank"].includes(String(c.capability).toLowerCase())),
);
const fineTuneModelOptions = computed(() => configs.value.map((config) => ({
  value: config.id,
  label: `${config.name} · ${config.model_name}`,
})));
const runnerServerOptions = computed(() => fineTuneRunnerServers.value.map((server) => ({
  value: server.id,
  label: `${server.name} · ${server.base_url}`,
})));
const supportsTokenOptions = computed(() => ["deepseek", "litellm", "dashscope"].includes(form.provider));
const drawerTitle = computed(() => (editingId.value ? "编辑模型配置" : "新增模型配置"));
const fineTuneDrawerTitle = computed(() => (editingFineTuneId.value ? "编辑微调登记" : "新增微调登记"));
const runnerServerDrawerTitle = computed(() => (editingRunnerServerId.value ? "编辑训练服务器" : "新增训练服务器"));
const isModelsMode = computed(() => props.mode !== "fine-tunes");
const isFineTunesMode = computed(() => props.mode === "fine-tunes");
const pageAlerts = computed(() => getConsolePageAlerts({
  mode: props.mode,
  configError: errorMsg.value,
  fineTuneError: fineTuneError.value,
}));
const showConfigRetry = computed(() => shouldShowConsoleConfigRetry({
  mode: props.mode,
  configError: errorMsg.value,
}));
const pageCopy = computed(() => {
  if (isFineTunesMode.value) {
    return {
      eyebrow: "LLM 中台 / LLaMA-Factory",
      title: "LLaMA-Factory 控制面",
      subtitle: "把微调登记、导出状态、回调令牌和候选模型回流从模型配置页中拆出来，单独观察训练链路的当前阶段。",
    };
  }

  return {
    eyebrow: "LLM 中台 / 模型配置",
    title: "模型配置与路由",
    subtitle: "管理平台级对话和向量模型，并明确当前启用关系、LiteLLM alias 入口以及与微调回流模型的衔接方式。",
  };
});
const isQlorStrategy = computed(() => fineTuneForm.training?.strategy === "qlora");

const resetForm = () => {
  Object.assign(form, defaultFormState());
  editingId.value = null;
};

const openCreate = (capability = "chat") => {
  resetForm();
  form.capability = capability;
  form.provider = "litellm";
  form.model_name = capability === "embedding" ? "embed-default" : capability === "rerank" ? "rerank-default" : "chat-default";
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

const resetRunnerServerForm = () => {
  Object.assign(runnerServerForm, defaultRunnerServerFormState());
  editingRunnerServerId.value = null;
};

const openCreateFineTune = (baseModelId = "") => {
  resetFineTuneForm();
  fineTuneForm.base_model_id = baseModelId || fineTuneFilterModelId.value || chatConfigs.value[0]?.id || configs.value[0]?.id || "";
  fineTuneDrawerVisible.value = true;
};

const openCreateRunnerServer = () => {
  resetRunnerServerForm();
  runnerServerDrawerVisible.value = true;
};

const openEditFineTune = (run) => {
  resetFineTuneForm();
  editingFineTuneId.value = run.id;
  fineTuneForm.base_model_id = run.base_model_id;
  fineTuneForm.runner_server_id = run.runner_server_id || "";
  fineTuneForm.dataset_name = run.dataset_name;
  fineTuneForm.dataset_version = run.dataset_version;
  fineTuneForm.runner_name = run.runner_name || "";
  fineTuneForm.training = normalizeLlamaFactoryTrainingConfig({
    strategy: run.strategy,
    trainingConfig: run.training_config || {},
  });
  fineTuneForm.status = run.status;
  fineTuneForm.external_job_id = run.external_job_id || "";
  fineTuneForm.artifact_path = run.artifact_path;
  fineTuneForm.metrics_json = JSON.stringify(run.metrics || {}, null, 2);
  fineTuneForm.notes = run.notes || "";
  fineTuneDrawerVisible.value = true;
};

const openEditRunnerServer = (server) => {
  resetRunnerServerForm();
  editingRunnerServerId.value = server.id;
  runnerServerForm.name = server.name;
  runnerServerForm.base_url = server.base_url;
  runnerServerForm.default_work_dir = server.default_work_dir || "";
  runnerServerForm.is_enabled = Boolean(server.is_enabled);
  runnerServerForm.has_auth_token = Boolean(server.has_auth_token);
  runnerServerForm.auth_token_masked = server.auth_token_masked || "";
  runnerServerDrawerVisible.value = true;
};

const buildFineTunePayload = () => {
  if (!fineTuneForm.base_model_id) {
    throw new Error("请选择基础模型");
  }

  if (!String(fineTuneForm.training.template || "").trim()) {
    throw new Error("请填写 LLaMA-Factory template");
  }

  let trainingConfig = {};
  try {
    trainingConfig = buildLlamaFactoryTrainingConfig(fineTuneForm.training);
  } catch (error) {
    throw new Error("高级附加参数 JSON 格式不正确");
  }

  const payload = {
    base_model_id: Number(fineTuneForm.base_model_id),
    runner_server_id: fineTuneForm.runner_server_id ? Number(fineTuneForm.runner_server_id) : null,
    dataset_name: fineTuneForm.dataset_name.trim(),
    dataset_version: fineTuneForm.dataset_version.trim(),
    strategy: fineTuneForm.training.strategy || "lora",
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

const buildRunnerServerPayload = () => {
  const payload = {
    name: runnerServerForm.name.trim(),
    base_url: runnerServerForm.base_url.trim(),
    default_work_dir: runnerServerForm.default_work_dir.trim(),
    is_enabled: Boolean(runnerServerForm.is_enabled),
  };
  if (runnerServerForm.auth_token.trim()) {
    payload.auth_token = runnerServerForm.auth_token.trim();
  }
  return payload;
};

const fetchConfigs = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getModelConfigs();
    configs.value = normalizeModelConfigPayload(data);
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

const fetchRunnerServers = async () => {
  runnerServerLoading.value = true;
  try {
    const data = await llmApi.getFineTuneRunnerServers();
    fineTuneRunnerServers.value = Array.isArray(data?.fine_tune_servers) ? data.fine_tune_servers : [];
  } catch (error) {
    console.error("Failed to fetch fine-tune runner servers:", error);
    fineTuneError.value = error.message || "加载训练服务器失败";
    fineTuneRunnerServers.value = [];
  } finally {
    runnerServerLoading.value = false;
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

const submitRunnerServer = async () => {
  if (!runnerServerForm.name.trim() || !runnerServerForm.base_url.trim()) {
    flash.error("请完整填写训练服务器名称和地址");
    return;
  }
  runnerServerSaving.value = true;
  try {
    const payload = buildRunnerServerPayload();
    if (editingRunnerServerId.value) {
      await llmApi.updateFineTuneRunnerServer(editingRunnerServerId.value, payload);
      flash.success("训练服务器已更新");
    } else {
      await llmApi.createFineTuneRunnerServer(payload);
      flash.success("训练服务器已创建");
    }
    runnerServerDrawerVisible.value = false;
    resetRunnerServerForm();
    await fetchRunnerServers();
  } catch (error) {
    flash.error(error.message || "保存训练服务器失败");
  } finally {
    runnerServerSaving.value = false;
  }
};

const removeRunnerServer = async (server) => {
  if (!server || !window.confirm(`确认删除训练服务器「${server.name}」吗？`)) {
    return;
  }
  try {
    await llmApi.deleteFineTuneRunnerServer(server.id);
    flash.success("训练服务器已删除");
    await fetchRunnerServers();
    await fetchFineTunes();
  } catch (error) {
    flash.error(error.message || "删除训练服务器失败");
  }
};

const dispatchFineTune = async (run) => {
  if (!run?.id) {
    return;
  }
  dispatchingFineTuneId.value = run.id;
  try {
    const result = await llmApi.dispatchFineTuneRun(run.id);
    const jobId = result?.dispatch?.job_id || result?.fine_tune_run?.external_job_id;
    flash.success(jobId ? `训练任务已提交：${jobId}` : "训练任务已提交");
    await fetchFineTunes();
  } catch (error) {
    flash.error(error.message || "提交远程训练失败");
  } finally {
    dispatchingFineTuneId.value = null;
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
  const server = run.runner_server_name || "训练服务器未指定";
  const remoteJob = run.external_job_id || "远端任务未提交";
  return `${run.run_key || "未分配 run_key"} / ${server} / ${remoteJob} / export:${exportStatus} / ${callbackState} / ${registration}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
};

onMounted(async () => {
  await fetchConfigs();
  if (isFineTunesMode.value) {
    fineTuneFilterModelId.value = getInitialFineTuneFilterId(configs.value, fineTuneFilterModelId.value);
    await fetchRunnerServers();
    await fetchFineTunes();
  }
});
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">{{ pageCopy.eyebrow }}</div>
        <h1 class="page-hero__title">{{ pageCopy.title }}</h1>
        <p class="page-hero__subtitle">
          {{ pageCopy.subtitle }}
        </p>
      </div>
      <div v-if="isModelsMode" class="model-page__actions">
        <el-button @click="fetchConfigs" :loading="isLoading">刷新配置</el-button>
        <el-button type="primary" @click="openCreate('chat')">新增对话模型</el-button>
      </div>
      <div v-else class="model-page__actions">
        <el-button v-if="showConfigRetry" @click="fetchConfigs" :loading="isLoading">重试加载基础模型</el-button>
        <el-button @click="fetchFineTunes" :loading="fineTuneLoading">刷新微调记录</el-button>
        <el-button type="primary" @click="openCreateFineTune()">登记微调</el-button>
      </div>
    </section>

    <el-alert
      v-for="alert in pageAlerts"
      :key="alert.key"
      :title="alert.message"
      type="error"
      show-icon
      :closable="false"
    />

    <template v-if="isModelsMode">
      <AppSectionCard
        title="LLaMA-Factory 回流关系"
        desc="微调控制面已迁移到独立页面，模型页保留当前启用关系和回流线索，避免训练链路继续混在 provider CRUD 里。"
        admin
      >
        <div class="model-page__split-callout">
          <p class="muted-text">需要查看训练状态、导出进度或候选模型回流时，请直接进入独立的 LLaMA-Factory 页面。</p>
          <RouterLink to="/admin/llm/fine-tunes" class="model-page__jump-link">
            打开 LLaMA-Factory
          </RouterLink>
        </div>
      </AppSectionCard>

      <AppSectionCard title="对话模型" desc="支持 LiteLLM 与 DeepSeek。启用新模型后，智能问答和其它 chat 能力会自动切换。" admin>
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

      <AppSectionCard title="向量模型" desc="支持 LiteLLM 与 DashScope embedding 配置。" admin>
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

      <AppSectionCard title="重排序模型" desc="支持 DashScope rerank 配置，用于检索结果重排序以提升召回质量。" admin>
      <template #header>
        <el-button type="primary" @click="openCreate('rerank')">新增重排序模型</el-button>
      </template>
      <div v-if="isLoading && rerankConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="rerankConfigs.length === 0" class="admin-empty-state">暂无重排序模型配置</div>
      <el-table v-else :data="rerankConfigs" stripe style="width: 100%">
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
    </template>

    <AppSectionCard
      v-if="isFineTunesMode"
      title="远程训练服务器"
      desc="登记 GPU runner agent 地址、工作目录和鉴权信息，微调任务会绑定到这里并从当前服务器发起提交。"
      admin
    >
      <template #header>
        <el-button type="primary" @click="openCreateRunnerServer()">新增训练服务器</el-button>
      </template>
      <div v-if="runnerServerLoading && fineTuneRunnerServers.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="fineTuneRunnerServers.length === 0" class="admin-empty-state">暂无远程训练服务器</div>
      <el-table v-else :data="fineTuneRunnerServers" stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column label="地址" min-width="240">
          <template #default="{ row }">
            <span class="mono-text">{{ row.base_url }}</span>
          </template>
        </el-table-column>
        <el-table-column label="工作目录" min-width="200">
          <template #default="{ row }">
            <span class="mono-text">{{ row.default_work_dir || '使用 agent 默认目录' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="鉴权" width="140">
          <template #default="{ row }">
            <span class="muted-text">{{ row.has_auth_token ? row.auth_token_masked : '未配置' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '已启用' : '已停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" plain @click="openEditRunnerServer(row)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="removeRunnerServer(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <AppSectionCard
      v-if="isFineTunesMode"
      title="微调控制面"
      desc="训练执行仍保持外部运行，这里登记数据集、导出、回调与候选模型回流状态。"
      admin
    >
      <template #header>
        <RouterLink to="/admin/llm/models" class="model-page__jump-link">
          返回模型配置
        </RouterLink>
      </template>
      <div class="registry-toolbar">
        <el-select
          v-model="fineTuneFilterModelId"
          filterable
          clearable
          placeholder="按基础模型筛选"
          style="min-width: 280px"
          @change="fetchFineTunes"
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
            <div class="muted-text">{{ row.runner_server_name || '训练服务器未指定' }} / {{ row.runner_name || 'runner 未指定' }}</div>
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
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" plain @click="openEditFineTune(row)">编辑</el-button>
              <el-button
                v-if="row.runner_server_id"
                size="small"
                type="primary"
                plain
                :loading="dispatchingFineTuneId === row.id"
                @click="dispatchFineTune(row)"
              >
                {{ row.external_job_id ? '重提' : '提交' }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <el-drawer v-if="isModelsMode" v-model="drawerVisible" :title="drawerTitle" size="520px" destroy-on-close>
      <div class="model-form">
        <el-form label-position="top">
          <el-form-item label="配置名称">
            <el-input v-model="form.name" placeholder="例如：DeepSeek 生产模型" />
          </el-form-item>
          <el-form-item label="能力类型">
            <el-select v-model="form.capability" style="width: 100%">
              <el-option label="对话模型" value="chat" />
              <el-option label="向量模型" value="embedding" />
              <el-option label="重排序模型" value="rerank" />
            </el-select>
          </el-form-item>
          <el-form-item label="Provider">
            <el-select v-model="form.provider" style="width: 100%">
              <el-option label="LiteLLM" value="litellm" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="DashScope" value="dashscope" />
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

    <el-drawer v-if="isFineTunesMode" v-model="runnerServerDrawerVisible" :title="runnerServerDrawerTitle" size="520px" destroy-on-close>
      <div class="model-form">
        <el-form label-position="top">
          <el-form-item label="服务器名称">
            <el-input v-model="runnerServerForm.name" placeholder="例如：gpu-runner-a" />
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="runnerServerForm.base_url" placeholder="例如：https://gpu-runner.example" />
          </el-form-item>
          <el-form-item label="Agent Bearer Token">
            <el-input
              v-model="runnerServerForm.auth_token"
              type="password"
              show-password
              placeholder="新建时可填写，编辑时留空表示保留原 token"
            />
            <div v-if="runnerServerForm.has_auth_token" class="form-footnote">已保存令牌：{{ runnerServerForm.auth_token_masked || '已配置' }}</div>
          </el-form-item>
          <el-form-item label="默认工作目录">
            <el-input v-model="runnerServerForm.default_work_dir" placeholder="例如：/srv/llamafactory/jobs" />
          </el-form-item>
          <el-form-item>
            <el-switch v-model="runnerServerForm.is_enabled" active-text="允许微调任务提交到该服务器" />
          </el-form-item>
        </el-form>

        <div class="drawer-actions">
          <el-button @click="runnerServerDrawerVisible = false">取消</el-button>
          <el-button type="primary" @click="submitRunnerServer" :loading="runnerServerSaving">保存服务器</el-button>
        </div>
      </div>
    </el-drawer>

    <el-drawer v-if="isFineTunesMode" v-model="fineTuneDrawerVisible" :title="fineTuneDrawerTitle" size="780px" destroy-on-close>
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
            <el-form-item label="训练服务器">
              <el-select v-model="fineTuneForm.runner_server_id" clearable filterable style="width: 100%" placeholder="选择远程训练服务器">
                <el-option
                  v-for="option in runnerServerOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="Runner 标识">
              <el-input v-model="fineTuneForm.runner_name" placeholder="例如：llamafactory-runner-a" />
            </el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="数据集名称">
              <el-input v-model="fineTuneForm.dataset_name" placeholder="例如：财报基准集" />
            </el-form-item>
            <el-form-item label="数据集版本">
              <el-input v-model="fineTuneForm.dataset_version" placeholder="例如：2026Q1" />
            </el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="训练阶段">
              <el-input :model-value="String(fineTuneForm.training.stage || 'sft').toUpperCase()" disabled />
            </el-form-item>
            <el-form-item label="微调方式">
              <el-select v-model="fineTuneForm.training.strategy" style="width: 100%">
                <el-option
                  v-for="option in LLAMAFACTORY_STRATEGY_OPTIONS"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </div>
          <div class="form-grid">
            <el-form-item label="Template">
              <el-input v-model="fineTuneForm.training.template" placeholder="例如：llama3 / qwen / deepseek" />
            </el-form-item>
            <el-form-item label="远端作业">
              <el-input v-model="fineTuneForm.external_job_id" disabled placeholder="提交后自动回填" />
            </el-form-item>
          </div>
          <el-alert
            title="输出目录、导出目录和回调地址仍由 runner/control plane 管理，这里只暴露常用训练参数；未覆盖的原生字段可放在高级附加参数 JSON。"
            type="info"
            :closable="false"
            show-icon
          />

          <div class="llamafactory-section">
            <div class="llamafactory-section__title">数据参数</div>
            <div class="form-grid">
              <el-form-item label="cutoff_len">
                <el-input-number v-model="fineTuneForm.training.cutoff_len" :min="128" :max="32768" :step="128" style="width: 100%" />
              </el-form-item>
              <el-form-item label="max_samples">
                <el-input-number v-model="fineTuneForm.training.max_samples" :min="1" :step="1000" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="preprocessing_num_workers">
                <el-input-number v-model="fineTuneForm.training.preprocessing_num_workers" :min="0" :max="64" style="width: 100%" />
              </el-form-item>
              <el-form-item label="dataloader_num_workers">
                <el-input-number v-model="fineTuneForm.training.dataloader_num_workers" :min="0" :max="64" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid form-grid--toggles">
              <el-form-item label="overwrite_cache">
                <el-switch v-model="fineTuneForm.training.overwrite_cache" />
              </el-form-item>
              <el-form-item label="packing">
                <el-switch v-model="fineTuneForm.training.packing" />
              </el-form-item>
            </div>
          </div>

          <div class="llamafactory-section">
            <div class="llamafactory-section__title">训练参数</div>
            <div class="form-grid">
              <el-form-item label="per_device_train_batch_size">
                <el-input-number v-model="fineTuneForm.training.per_device_train_batch_size" :min="1" :max="512" style="width: 100%" />
              </el-form-item>
              <el-form-item label="gradient_accumulation_steps">
                <el-input-number v-model="fineTuneForm.training.gradient_accumulation_steps" :min="1" :max="1024" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="learning_rate">
                <el-input-number v-model="fineTuneForm.training.learning_rate" :min="0" :step="0.00001" :precision="6" style="width: 100%" />
              </el-form-item>
              <el-form-item label="num_train_epochs">
                <el-input-number v-model="fineTuneForm.training.num_train_epochs" :min="1" :step="1" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="lr_scheduler_type">
                <el-select v-model="fineTuneForm.training.lr_scheduler_type" style="width: 100%">
                  <el-option
                    v-for="option in LLAMAFACTORY_SCHEDULER_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="warmup_ratio">
                <el-input-number v-model="fineTuneForm.training.warmup_ratio" :min="0" :max="1" :step="0.01" :precision="2" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="max_grad_norm">
                <el-input-number v-model="fineTuneForm.training.max_grad_norm" :min="0" :step="0.1" :precision="2" style="width: 100%" />
              </el-form-item>
              <el-form-item label="precision">
                <el-select v-model="fineTuneForm.training.precision_type" style="width: 100%">
                  <el-option
                    v-for="option in LLAMAFACTORY_PRECISION_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="logging_steps">
                <el-input-number v-model="fineTuneForm.training.logging_steps" :min="1" :step="1" style="width: 100%" />
              </el-form-item>
              <el-form-item label="save_steps">
                <el-input-number v-model="fineTuneForm.training.save_steps" :min="1" :step="1" style="width: 100%" />
              </el-form-item>
            </div>
          </div>

          <div class="llamafactory-section">
            <div class="llamafactory-section__title">评估参数</div>
            <div class="form-grid">
              <el-form-item label="val_size">
                <el-input-number v-model="fineTuneForm.training.val_size" :min="0" :max="0.9" :step="0.01" :precision="2" style="width: 100%" />
              </el-form-item>
              <el-form-item label="per_device_eval_batch_size">
                <el-input-number v-model="fineTuneForm.training.per_device_eval_batch_size" :min="1" :max="512" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="eval_strategy">
                <el-select v-model="fineTuneForm.training.eval_strategy" style="width: 100%">
                  <el-option
                    v-for="option in LLAMAFACTORY_EVAL_STRATEGY_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="eval_steps">
                <el-input-number v-model="fineTuneForm.training.eval_steps" :min="1" :step="1" style="width: 100%" />
              </el-form-item>
            </div>
          </div>

          <div class="llamafactory-section">
            <div class="llamafactory-section__title">LoRA 参数</div>
            <div class="form-grid">
              <el-form-item label="lora_rank">
                <el-input-number v-model="fineTuneForm.training.lora_rank" :min="1" :max="1024" style="width: 100%" />
              </el-form-item>
              <el-form-item label="lora_alpha">
                <el-input-number v-model="fineTuneForm.training.lora_alpha" :min="1" :max="4096" style="width: 100%" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="lora_dropout">
                <el-input-number v-model="fineTuneForm.training.lora_dropout" :min="0" :max="1" :step="0.01" :precision="2" style="width: 100%" />
              </el-form-item>
              <el-form-item label="lora_target">
                <el-input v-model="fineTuneForm.training.lora_target" placeholder="例如：all / q_proj,v_proj" />
              </el-form-item>
            </div>
          </div>

          <div v-if="isQlorStrategy" class="llamafactory-section">
            <div class="llamafactory-section__title">QLoRA 参数</div>
            <div class="form-grid">
              <el-form-item label="quantization_bit">
                <el-select v-model="fineTuneForm.training.quantization_bit" style="width: 100%">
                  <el-option label="8" :value="8" />
                  <el-option label="4" :value="4" />
                  <el-option label="2" :value="2" />
                </el-select>
              </el-form-item>
              <el-form-item label="quantization_method">
                <el-input v-model="fineTuneForm.training.quantization_method" placeholder="例如：bitsandbytes" />
              </el-form-item>
            </div>
            <el-form-item label="double_quantization">
              <el-switch v-model="fineTuneForm.training.double_quantization" />
            </el-form-item>
          </div>

          <div class="llamafactory-section">
            <div class="llamafactory-section__title">输出与运行</div>
            <div class="form-grid">
              <el-form-item label="report_to">
                <el-select v-model="fineTuneForm.training.report_to" style="width: 100%">
                  <el-option
                    v-for="option in LLAMAFACTORY_REPORT_TO_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="gradient_checkpointing">
                <el-switch v-model="fineTuneForm.training.gradient_checkpointing" />
              </el-form-item>
            </div>
            <div class="form-grid form-grid--toggles">
              <el-form-item label="plot_loss">
                <el-switch v-model="fineTuneForm.training.plot_loss" />
              </el-form-item>
              <el-form-item label="save_only_model">
                <el-switch v-model="fineTuneForm.training.save_only_model" />
              </el-form-item>
            </div>
          </div>

          <el-form-item label="高级附加参数 JSON">
            <el-input
              v-model="fineTuneForm.training.advanced_config_json"
              type="textarea"
              :rows="6"
              placeholder='{"ddp_timeout": 180000000}'
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

.model-page__split-callout {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.model-page__jump-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  color: var(--text-primary);
  background: var(--surface-1);
  text-decoration: none;
  white-space: nowrap;
}

.model-page__jump-link:hover {
  border-color: var(--line-strong);
  background: var(--surface-2);
}

.table-actions {
  display: flex;
  gap: 8px;
}

.model-form {
  display: grid;
  gap: 20px;
}

.llamafactory-section {
  display: grid;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  background: var(--surface-1);
}

.llamafactory-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-muted);
  letter-spacing: 0;
  text-transform: uppercase;
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

@media (max-width: 768px) {
  .model-page__actions,
  .model-page__split-callout,
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
