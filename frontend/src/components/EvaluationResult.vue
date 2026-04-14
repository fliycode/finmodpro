<script setup>
import { ref, onMounted } from "vue";
import { llmApi } from "../api/llm.js";
import { useFlash } from "../lib/flash.js";
import AppSectionCard from "./ui/AppSectionCard.vue";
import AppToolbar from "./ui/AppToolbar.vue";

const evaluations = ref([]);
const comparisonGroups = ref([]);
const isLoading = ref(false);
const isTriggering = ref(false);
const errorMsg = ref("");
const flash = useFlash();

const triggerForm = ref({
  task_type: "qa",
  evaluation_mode: "baseline",
  dataset_name: "qa-smoke",
  dataset_version: "2026Q1",
  version: "v1.0",
  run_notes: "baseline smoke",
});

const fetchEvaluations = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const data = await llmApi.getEvaluations();
    evaluations.value = Array.isArray(data?.eval_records) ? data.eval_records : [];
    comparisonGroups.value = Array.isArray(data?.comparison_groups) ? data.comparison_groups : [];
  } catch (error) {
    console.error("Failed to fetch evaluations:", error);
    errorMsg.value = error.message || "加载评测记录失败";
    evaluations.value = [];
    comparisonGroups.value = [];
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
    succeeded: "已完成",
    failed: "失败"
  };
  return texts[status?.toLowerCase()] || status;
};

const getStatusTagType = (status) => {
  if (status === 'completed') return 'success';
  if (status === 'succeeded') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'running') return 'primary';
  if (status === 'pending') return 'warning';
  return 'info';
};

const getEvaluationModeLabel = (mode) => {
  const labels = {
    baseline: "基线",
    rag: "RAG 增强",
    fine_tuned: "微调",
  };
  return labels[mode] || mode || '--';
};

const formatMetric = (value, suffix = "") => {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return String(value);
  }
  return suffix ? `${number.toFixed(2)}${suffix}` : number.toFixed(4);
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
        <el-form class="admin-form-row evaluation-form">
          <div class="evaluation-form__grid">
          <el-form-item>
            <el-select v-model="triggerForm.task_type" placeholder="任务类型">
              <el-option label="问答评测 (QA)" value="qa" />
              <el-option label="提取评测 (Extraction)" value="extraction" />
              <el-option label="报告评测" value="report" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="triggerForm.evaluation_mode" placeholder="比较模式">
              <el-option label="基线" value="baseline" />
              <el-option label="RAG 增强" value="rag" />
              <el-option label="微调模型" value="fine_tuned" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-input v-model="triggerForm.dataset_name" placeholder="数据集名称" clearable />
          </el-form-item>
          <el-form-item>
            <el-input v-model="triggerForm.dataset_version" placeholder="数据集版本 (例: 2026Q1)" clearable />
          </el-form-item>
          <el-form-item>
            <el-input v-model="triggerForm.version" placeholder="评测版本 (例: v1.0)" clearable />
          </el-form-item>
          </div>
          <el-form-item class="evaluation-form__notes">
            <el-input v-model="triggerForm.run_notes" type="textarea" :rows="2" placeholder="评测备注或上线背景说明" />
          </el-form-item>
          <div class="evaluation-form__footer">
            <el-button type="primary" @click="triggerEvaluation" :loading="isTriggering">触发评测</el-button>
          </div>
        </el-form>
      </AppToolbar>
    </AppSectionCard>

    <AppSectionCard title="比较视图" desc="按 baseline / RAG / fine-tuned 分组展示评测结果，便于直接比较效果。">
      <div v-if="comparisonGroups.length === 0" class="admin-empty-state">暂无比较分组</div>
      <div v-else class="comparison-grid">
        <article v-for="group in comparisonGroups" :key="group.evaluation_mode" class="comparison-card">
          <header class="comparison-card__header">
            <div>
              <el-tag effect="plain">{{ getEvaluationModeLabel(group.evaluation_mode) }}</el-tag>
              <div class="comparison-card__label">{{ group.label }}</div>
            </div>
            <div class="muted-text">{{ group.total }} 条记录</div>
          </header>
          <ul class="comparison-card__metrics">
            <li>QA {{ formatPercent(group.summary.qa_accuracy) }}</li>
            <li>提取 {{ formatPercent(group.summary.extraction_accuracy) }}</li>
            <li>Precision {{ formatPercent(group.summary.precision) }}</li>
            <li>Recall {{ formatPercent(group.summary.recall) }}</li>
            <li>F1 {{ formatPercent(group.summary.f1_score) }}</li>
            <li>延迟 {{ formatMetric(group.summary.average_latency_ms, " ms") }}</li>
          </ul>
          <div class="comparison-card__records">
            <div v-for="record in group.records" :key="record.id" class="comparison-card__record">
              <div class="comparison-card__record-header">
                <strong>{{ record.target_name }}</strong>
                <span class="muted-text">{{ record.task_type }}</span>
              </div>
              <div class="comparison-card__record-body">
                <span>{{ record.dataset_name || "未指定数据集" }}</span>
                <span>{{ record.dataset_version || "--" }}</span>
                <span>{{ formatPercent(record.f1_score) }}</span>
                <span>{{ formatDate(record.created_at) }}</span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </AppSectionCard>

    <AppSectionCard title="评测记录" desc="展示任务状态、准确率和平均延迟，便于快速比较模型表现。" admin>
      <el-table :data="evaluations" stripe style="width: 100%" v-loading="isLoading">
        <el-table-column prop="evaluation_mode" label="模式" width="120">
          <template #default="scope">
            <el-tag effect="plain">{{ getEvaluationModeLabel(scope && scope.row ? scope.row.evaluation_mode : '') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_type" label="任务类型" min-width="140">
          <template #default="scope">
            <el-tag effect="plain">{{ scope && scope.row ? scope.row.task_type : '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="140">
          <template #default="scope">
            {{ scope && scope.row ? (scope.row.version || '--') : '--' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope && scope.row ? scope.row.status : undefined)">
              {{ getStatusText(scope && scope.row ? scope.row.status : '--') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据集" min-width="180">
          <template #default="scope">
            <div>{{ scope && scope.row ? (scope.row.dataset_name || '--') : '--' }}</div>
            <div class="muted-text">{{ scope && scope.row ? (scope.row.dataset_version || '--') : '--' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="QA 准确率" width="120">
          <template #default="scope">{{ formatPercent(scope && scope.row ? scope.row.qa_accuracy : null) }}</template>
        </el-table-column>
        <el-table-column label="提取准确率" width="120">
          <template #default="scope">{{ formatPercent(scope && scope.row ? scope.row.extraction_accuracy : null) }}</template>
        </el-table-column>
        <el-table-column label="Precision" width="120">
          <template #default="scope">{{ formatPercent(scope && scope.row ? scope.row.precision : null) }}</template>
        </el-table-column>
        <el-table-column label="Recall" width="120">
          <template #default="scope">{{ formatPercent(scope && scope.row ? scope.row.recall : null) }}</template>
        </el-table-column>
        <el-table-column label="F1" width="120">
          <template #default="scope">{{ formatPercent(scope && scope.row ? scope.row.f1_score : null) }}</template>
        </el-table-column>
        <el-table-column label="平均延迟 (ms)" width="140">
          <template #default="scope">{{ scope && scope.row && scope.row.average_latency_ms !== null ? scope.row.average_latency_ms : '--' }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="220">
          <template #default="scope">
            <span class="muted-text">{{ scope && scope.row ? (scope.row.run_notes || '--') : '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="scope">
            <span class="muted-text">{{ formatDate(scope && scope.row ? scope.row.created_at : '') }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="admin-empty-state">暂无评测记录</div>
        </template>
      </el-table>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.evaluation-form {
  width: 100%;
}

.evaluation-form__grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.evaluation-form__notes {
  margin-top: 8px;
}

.evaluation-form__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.comparison-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 16px;
  background: var(--el-bg-color);
  display: grid;
  gap: 12px;
}

.comparison-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.comparison-card__label {
  margin-top: 6px;
  font-weight: 600;
}

.comparison-card__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}

.comparison-card__records {
  display: grid;
  gap: 8px;
}

.comparison-card__record {
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
  display: grid;
  gap: 6px;
}

.comparison-card__record-header,
.comparison-card__record-body {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.comparison-card__record-body {
  color: var(--app-text-muted);
  font-size: 12px;
}

@media (max-width: 768px) {
  .evaluation-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
