<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { llmApi } from "../api/llm.js";
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

const defaultFormState = () => ({
  name: "",
  capability: "chat",
  provider: "deepseek",
  model_name: "deepseek-chat",
  endpoint: "https://api.deepseek.com",
  api_key: "",
  temperature: 0.2,
  max_tokens: 1024,
  is_active: false,
  has_api_key: false,
  api_key_masked: "",
});

const form = reactive(defaultFormState());

const normalizeConfigs = (payload) => {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results)
      ? payload.results
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.model_configs)
          ? payload.model_configs
          : Array.isArray(payload?.data)
            ? payload.data
            : [];

  return list.map((item, index) => ({
    id: item.id ?? item.config_id ?? index,
    name: item.name ?? item.config_name ?? item.model_name ?? `config-${index}`,
    provider: item.provider ?? item.vendor ?? "--",
    model_name: item.model_name ?? item.model ?? item.name ?? "--",
    endpoint: item.endpoint ?? item.api_base ?? item.base_url ?? "",
    capability: item.capability ?? item.model_type ?? item.type ?? "chat",
    is_active: item.is_active ?? item.active ?? item.enabled ?? false,
    updated_at: item.updated_at ?? item.updatedAt ?? item.modified_at ?? item.created_at ?? "",
    options: item.options ?? {},
    has_api_key: item.has_api_key ?? false,
    api_key_masked: item.api_key_masked ?? "",
    raw: item,
  }));
};

const chatConfigs = computed(() =>
  configs.value.filter((c) => ["chat", "llm", "generation"].includes(String(c.capability).toLowerCase())),
);
const embeddingConfigs = computed(() =>
  configs.value.filter((c) => ["embedding", "embed", "vector"].includes(String(c.capability).toLowerCase())),
);
const isDeepSeek = computed(() => form.provider === "deepseek");
const drawerTitle = computed(() => (editingId.value ? "编辑模型配置" : "新增模型配置"));

const resetForm = () => {
  Object.assign(form, defaultFormState());
  editingId.value = null;
};

const openCreate = (capability = "chat") => {
  resetForm();
  form.capability = capability;
  form.provider = capability === "embedding" ? "ollama" : "deepseek";
  form.model_name = capability === "embedding" ? "bge-m3" : "deepseek-chat";
  form.endpoint = capability === "embedding" ? "http://localhost:11434" : "https://api.deepseek.com";
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
  if (form.provider === "deepseek") {
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

const fetchConfigs = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getModelConfigs();
    configs.value = normalizeConfigs(data);
  } catch (error) {
    console.error("Failed to fetch model configs:", error);
    errorMsg.value = error.message || "加载模型配置失败";
    configs.value = [];
  } finally {
    isLoading.value = false;
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

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
};

onMounted(fetchConfigs);
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Models</div>
        <h1 class="page-hero__title">模型配置管理</h1>
        <p class="page-hero__subtitle">
          管理平台级对话和向量模型。智能问答会自动读取当前启用的 chat 模型，不需要前端额外切换。
        </p>
      </div>
      <div class="model-page__actions">
        <el-button @click="fetchConfigs" :loading="isLoading">刷新配置</el-button>
        <el-button type="primary" @click="openCreate('chat')">新增对话模型</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard title="对话模型" desc="支持 Ollama 与 DeepSeek。启用新模型后，智能问答和其它 chat 能力会自动切换。" admin>
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

    <AppSectionCard title="向量模型" desc="当前继续沿用现有 embedding 配置体系。" admin>
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
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
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
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="Ollama" value="ollama" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="form.model_name" placeholder="例如：deepseek-chat" />
          </el-form-item>
          <el-form-item label="接口地址">
            <el-input v-model="form.endpoint" placeholder="例如：https://api.deepseek.com" />
          </el-form-item>

          <template v-if="isDeepSeek">
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

@media (max-width: 768px) {
  .model-page__actions,
  .form-grid,
  .drawer-actions,
  .table-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
