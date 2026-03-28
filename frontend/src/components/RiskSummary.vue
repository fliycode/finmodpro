<script setup>
import { ref, onMounted } from "vue";
import { riskApi } from "../api/risk.js";

const analysis = ref(null);
const isLoading = ref(false);

const fetchAnalysis = async () => {
  isLoading.value = true;
  try {
    analysis.value = await riskApi.getAnalysis();
  } catch (error) {
    console.error("Failed to fetch analysis:", error);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchAnalysis);

const getRiskLevelColor = (level) => {
  const colors = {
    high: '#ef4444',
    medium: '#f59e0b',
    low: '#10b981'
  };
  return colors[level] || '#64748b';
};
</script>

<template>
  <div class="risk-shell">
    <div v-if="isLoading" class="loading-state">分析生成中...</div>
    <div v-else-if="analysis" class="grid">
      <div class="card summary-card">
        <h3>📊 报告核心摘要</h3>
        <div class="summary-content">
          {{ analysis.summary }}
        </div>
      </div>
      
      <div class="card risk-card">
        <h3>⚠️ 潜在风险点</h3>
        <div class="risk-list">
          <div v-for="(risk, index) in analysis.risks" :key="index" class="risk-item">
            <div class="risk-header">
              <span class="risk-level" :style="{ backgroundColor: getRiskLevelColor(risk.level) }">
                {{ risk.level.toUpperCase() }}
              </span>
              <span class="risk-category">{{ risk.category }}</span>
            </div>
            <p class="risk-desc">{{ risk.description }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-shell { display: flex; flex-direction: column; gap: 24px; }
.loading-state { padding: 48px; text-align: center; color: #64748b; background: white; border-radius: 12px; }
.grid { display: grid; grid-template-columns: 3fr 2fr; gap: 24px; }
.card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card h3 { margin-top: 0; margin-bottom: 20px; font-size: 18px; color: #1e293b; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; }

.summary-content { line-height: 1.8; color: #334155; font-size: 15px; }

.risk-list { display: flex; flex-direction: column; gap: 16px; }
.risk-item { padding: 12px; background: #f8fafc; border-radius: 8px; border-left: 4px solid #e2e8f0; }
.risk-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.risk-level { font-size: 10px; font-weight: 800; color: white; padding: 2px 6px; border-radius: 4px; }
.risk-category { font-weight: 600; color: #1e293b; font-size: 14px; }
.risk-desc { margin: 0; font-size: 13px; color: #475569; line-height: 1.5; }

@media (max-width: 1024px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
