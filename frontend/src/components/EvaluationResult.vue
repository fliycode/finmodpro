<script setup>
import { ref, onMounted } from "vue";
import { llmApi } from "../api/llm.js";

const evaluations = ref([]);
const isLoading = ref(false);
const isTriggering = ref(false);
const errorMsg = ref("");

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
    await fetchEvaluations();
  } catch (error) {
    console.error("Failed to trigger evaluation:", error);
    alert(error.message || "触发评测失败");
  } finally {
    isTriggering.value = false;
  }
};

onMounted(fetchEvaluations);

const getStatusColor = (status) => {
  const colors = {
    pending: "#f59e0b",
    running: "#3b82f6",
    completed: "#10b981",
    failed: "#ef4444"
  };
  return colors[status?.toLowerCase()] || "#64748b";
};

const getStatusText = (status) => {
  const texts = {
    pending: "等待中",
    running: "评测中",
    completed: "已完成",
    failed: "失败"
  };
  return texts[status?.toLowerCase()] || status;
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
  <div class="evaluation-shell">
    <div class="header">
      <div class="title-group">
        <h3>模型评测结果</h3>
        <span class="badge">管理员模式</span>
      </div>
      <div class="actions">
        <button class="secondary-btn" @click="fetchEvaluations" :disabled="isLoading">
          {{ isLoading ? "刷新中..." : "刷新列表" }}
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="error-state">{{ errorMsg }}</div>

    <div class="trigger-section">
      <h4>新建评测任务</h4>
      <div class="trigger-form">
        <select v-model="triggerForm.task_type" class="form-select">
          <option value="qa">问答评测 (QA)</option>
          <option value="extraction">提取评测 (Extraction)</option>
        </select>
        <input type="text" v-model="triggerForm.version" placeholder="评测版本 (例: v1.0)" class="form-input" />
        <button class="primary-btn" @click="triggerEvaluation" :disabled="isTriggering">
          {{ isTriggering ? "触发中..." : "触发评测" }}
        </button>
      </div>
    </div>

    <div class="table-container">
      <div v-if="isLoading && evaluations.length === 0" class="loading-state">加载中...</div>
      <div v-else-if="evaluations.length === 0" class="empty-state">暂无评测记录</div>
      <table v-else class="eval-table">
        <thead>
          <tr>
            <th>任务类型</th>
            <th>版本</th>
            <th>状态</th>
            <th>QA 准确率</th>
            <th>提取准确率</th>
            <th>平均延迟 (ms)</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in evaluations" :key="item.id">
            <td><span class="task-type">{{ item.task_type }}</span></td>
            <td>{{ item.version || "--" }}</td>
            <td>
              <span class="status-badge" :style="{ color: getStatusColor(item.status) }">
                ● {{ getStatusText(item.status) }}
              </span>
            </td>
            <td>{{ formatPercent(item.qa_accuracy) }}</td>
            <td>{{ formatPercent(item.extraction_accuracy) }}</td>
            <td>{{ item.average_latency_ms !== null ? item.average_latency_ms : "--" }}</td>
            <td class="created-at">{{ formatDate(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.evaluation-shell { display: flex; flex-direction: column; gap: 24px; }
.header { display: flex; align-items: center; justify-content: space-between; }
.title-group { display: flex; align-items: center; gap: 12px; }
.header h3 { margin: 0; color: #1e293b; }
.badge { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; }

.primary-btn { padding: 8px 16px; background: #6366f1; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.primary-btn:hover:not(:disabled) { background: #4f46e5; }
.primary-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.secondary-btn { padding: 8px 16px; background: white; border: 1px solid #e2e8f0; color: #475569; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
.secondary-btn:hover:not(:disabled) { background: #f8fafc; border-color: #cbd5e1; }
.secondary-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.error-state { padding: 12px; background: #fef2f2; color: #ef4444; border-radius: 8px; font-size: 14px; text-align: center; border: 1px solid #fca5a5; }

.trigger-section { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.trigger-section h4 { margin: 0 0 16px 0; color: #1e293b; font-size: 15px; }
.trigger-form { display: flex; gap: 12px; align-items: center; }
.form-select, .form-input { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; outline: none; font-size: 13px; color: #1e293b; transition: border-color 0.2s; }
.form-select:focus, .form-input:focus { border-color: #6366f1; }
.form-select { min-width: 150px; }
.form-input { flex: 1; max-width: 200px; }

.table-container { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
.loading-state, .empty-state { text-align: center; padding: 48px; color: #64748b; font-size: 14px; }

.eval-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
.eval-table th { background: #f8fafc; padding: 14px 16px; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.eval-table td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; color: #1e293b; vertical-align: middle; }
.eval-table tr:last-child td { border-bottom: none; }
.eval-table tr:hover { background: #f8fafc; }

.task-type { background: #e2e8f0; padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #475569; font-weight: 600; }
.status-badge { font-weight: 600; font-size: 13px; white-space: nowrap; }
.created-at { color: #64748b; font-size: 13px; white-space: nowrap; }
</style>
