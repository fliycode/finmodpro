<script setup>
import { ref, onMounted, computed } from "vue";
import { llmApi } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";
import AppSectionCard from "./ui/AppSectionCard.vue";

const configs = ref([]);
const isLoading = ref(false);
const errorMsg = ref("");
const flash = useFlash();

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
    provider: item.provider ?? item.vendor ?? '--',
    model_name: item.model_name ?? item.model ?? item.name ?? '--',
    endpoint: item.endpoint ?? item.api_base ?? item.base_url ?? '',
    capability: item.capability ?? item.model_type ?? item.type ?? 'chat',
    is_active: item.is_active ?? item.active ?? item.enabled ?? false,
    updated_at: item.updated_at ?? item.updatedAt ?? item.modified_at ?? item.created_at ?? '',
    raw: item,
  }));
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

onMounted(fetchConfigs);

const toggleActivation = async (config) => {
  try {
    const newStatus = !config.is_active;
    await llmApi.activateModelConfig(config.id, newStatus);
    flash.success(`${config.name} 已${newStatus ? '启用' : '停用'}`);
    await fetchConfigs();
  } catch (error) {
    flash.error(error.message || "操作失败");
  }
};

const chatConfigs = computed(() => configs.value.filter((c) => ["chat", "llm", "generation"].includes(String(c.capability).toLowerCase())));
const embeddingConfigs = computed(() => configs.value.filter((c) => ["embedding", "embed", "vector"].includes(String(c.capability).toLowerCase())));

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch (e) {
    return dateStr;
  }
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Models</div>
        <h1 class="page-hero__title">模型配置管理</h1>
        <p class="page-hero__subtitle">
          用于切换聊天模型和向量模型的激活状态。后台先标准化到 Element Plus，减少手写管理控件的维护负担。
        </p>
      </div>
      <el-button type="primary" @click="fetchConfigs" :loading="isLoading">刷新配置</el-button>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard title="对话模型 (Chat)" desc="仅能启用一个对话模型用于问答。启用新模型将自动停用当前启用的模型。" admin>
      <div v-if="isLoading && chatConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="chatConfigs.length === 0" class="admin-empty-state">暂无对话模型配置</div>
      <el-table v-else :data="chatConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名" min-width="180" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="API Endpoint" min-width="220">
          <template #default="{ row }">
            <span class="mono-text">{{ row.endpoint || '默认' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button :type="row.is_active ? 'danger' : 'primary'" plain size="small" @click="toggleActivation(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <AppSectionCard title="向量模型 (Embedding)" desc="仅能启用一个向量模型用于知识库处理。启用新模型将自动停用当前启用的模型。" admin>
      <div v-if="isLoading && embeddingConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="embeddingConfigs.length === 0" class="admin-empty-state">暂无向量模型配置</div>
      <el-table v-else :data="embeddingConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名" min-width="180" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="API Endpoint" min-width="220">
          <template #default="{ row }">
            <span class="mono-text">{{ row.endpoint || '默认' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            <span class="muted-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button :type="row.is_active ? 'danger' : 'primary'" plain size="small" @click="toggleActivation(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>
  </div>
</template>
