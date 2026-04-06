<script setup>
import { ref, onMounted } from "vue";
import { llmApi } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";
import AppSectionCard from "./ui/AppSectionCard.vue";
import AppToolbar from "./ui/AppToolbar.vue";

const evaluations = ref([]);
const isLoading = ref(false);
const isTriggering = ref(false);
const errorMsg = ref("");
const flash = useFlash();

const triggerForm = ref({
  task_type: "qa",
  version: "v1.0"
});

const fetchEvaluations = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getEvaluations();
    evaluations.value = data || [];
  } catch (error) {
    console.error("Failed to fetch evaluations:", error);
    errorMsg.value = error.message || "加载评测记录失败";
  } finally {
    isLoading.value = false;
  }
};

const triggerEvaluation = async () => {
  isTriggering.value = true;
  errorMsg.value = "";
  try {
    await llmApi.triggerEvaluation(triggerForm.value);
    flash.success('评测任务已触发');
    await fetchEvaluations();
  } catch (error) {
    console.error("Failed to trigger evaluation:", error);
    flash.error(error.message || "触发评测失败");
  } finally {
    isTriggering.value = false;
  }
};

onMounted(fetchEvaluations);

const getStatusText = (status) => {
  const texts = {
    pending: "等待中",
    running: "评测中",
    completed: "已完成",
    failed: "失败"
  };
  return texts[status?.toLowerCase()] || status;
};

const getStatusTagType = (status) => {
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'running') return 'primary';
  if (status === 'pending') return 'warning';
  return 'info';
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleString();
  } catch (e) {
    return dateStr;
  }
};

const formatPercent = (val) => {
  if (val === null || val === undefined) return "--";
  return (val * 100).toFixed(1) + "%";
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Evaluation</div>
        <h1 class="page-hero__title">模型评测结果</h1>
        <p class="page-hero__subtitle">
          在后台触发与查看模型评测记录，统一评测状态、精度和延迟指标的呈现方式。
        </p>
      </div>
      <el-button type="primary" @click="fetchEvaluations" :loading="isLoading">刷新列表</el-button>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <AppSectionCard title="新建评测任务" desc="支持手动触发问答与提取评测，用于验证模型版本表现。" admin>
      <AppToolbar>
        <el-form :inline="true" class="admin-form-row">
          <el-form-item>
            <el-select v-model="triggerForm.task_type" placeholder="任务类型">
              <el-option label="问答评测 (QA)" value="qa" />
              <el-option label="提取评测 (Extraction)" value="extraction" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-input v-model="triggerForm.version" placeholder="评测版本 (例: v1.0)" clearable />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="triggerEvaluation" :loading="isTriggering">触发评测</el-button>
          </el-form-item>
        </el-form>
      </AppToolbar>
    </AppSectionCard>

    <AppSectionCard title="评测记录" desc="展示任务状态、准确率和平均延迟，便于快速比较模型表现。" admin>
      <el-table :data="evaluations" stripe style="width: 100%" v-loading="isLoading">
        <el-table-column prop="task_type" label="任务类型" min-width="140">
          <template #default="scope">
            <el-tag effect="plain">{{ scope.row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="140">
          <template #default="scope">
            {{ scope.row.version || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="QA 准确率" width="120">
          <template #default="scope">{{ formatPercent(scope.row.qa_accuracy) }}</template>
        </el-table-column>
        <el-table-column label="提取准确率" width="120">
          <template #default="scope">{{ formatPercent(scope.row.extraction_accuracy) }}</template>
        </el-table-column>
        <el-table-column label="平均延迟 (ms)" width="140">
          <template #default="scope">{{ scope.row.average_latency_ms !== null ? scope.row.average_latency_ms : '--' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="scope">
            <span class="muted-text">{{ formatDate(scope.row.created_at) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="admin-empty-state">暂无评测记录</div>
        </template>
      </el-table>
    </AppSectionCard>
  </div>
</template>
