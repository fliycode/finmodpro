<script setup>
import { ref, onMounted, computed } from "vue";
import { llmApi } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";

const configs = ref([]);
const isLoading = ref(false);
const errorMsg = ref("");
const flash = useFlash();

const normalizeConfigs = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.model_configs)) return payload.model_configs;
  return [];
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

const chatConfigs = computed(() => configs.value.filter((c) => c.capability === "chat"));
const embeddingConfigs = computed(() => configs.value.filter((c) => c.capability === "embedding"));

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

    <el-card class="ui-card ui-card--admin admin-section-card" shadow="never">
      <template #header>
        <div class="section-heading">
          <h3 class="section-heading__title">对话模型 (Chat)</h3>
          <div class="section-heading__desc">仅能启用一个对话模型用于问答。启用新模型将自动停用当前启用的模型。</div>
        </div>
      </template>

      <div v-if="isLoading && chatConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="chatConfigs.length === 0" class="admin-empty-state">暂无对话模型配置</div>
      <el-table v-else :data="chatConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名" min-width="180" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="API Endpoint" min-width="220">
          <template #default="scope">
            <span class="mono-text">{{ scope.row.endpoint || '默认' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'">
              {{ scope.row.is_active ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="scope">
            <span class="muted-text">{{ formatDate(scope.row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button :type="scope.row.is_active ? 'danger' : 'primary'" plain size="small" @click="toggleActivation(scope.row)">
              {{ scope.row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="ui-card ui-card--admin admin-section-card" shadow="never">
      <template #header>
        <div class="section-heading">
          <h3 class="section-heading__title">向量模型 (Embedding)</h3>
          <div class="section-heading__desc">仅能启用一个向量模型用于知识库处理。启用新模型将自动停用当前启用的模型。</div>
        </div>
      </template>

      <div v-if="isLoading && embeddingConfigs.length === 0" class="admin-empty-state">加载中...</div>
      <div v-else-if="embeddingConfigs.length === 0" class="admin-empty-state">暂无向量模型配置</div>
      <el-table v-else :data="embeddingConfigs" stripe style="width: 100%">
        <el-table-column prop="name" label="配置名" min-width="180" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column prop="model_name" label="模型名" min-width="180" />
        <el-table-column label="API Endpoint" min-width="220">
          <template #default="scope">
            <span class="mono-text">{{ scope.row.endpoint || '默认' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'">
              {{ scope.row.is_active ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="scope">
            <span class="muted-text">{{ formatDate(scope.row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button :type="scope.row.is_active ? 'danger' : 'primary'" plain size="small" @click="toggleActivation(scope.row)">
              {{ scope.row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
