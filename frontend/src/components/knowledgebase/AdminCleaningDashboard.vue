<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import CleaningRuleDialog from './CleaningRuleDialog.vue';
import { cleaningApi } from '../../api/cleaning.js';

const loading = ref(true);
const summaryLoading = ref(true);
const rules = ref([]);
const summary = ref(null);
const dialogVisible = ref(false);
const editingRule = ref(null);
const router = useRouter();

const RULE_TYPE_LABELS = {
  clean_whitespace: '空白清理',
  fix_encoding: '编码修复',
  normalize_quotes: '引号标准化',
  remove_bullets: '移除项目符号',
  group_broken_paragraphs: '段落合并',
  remove_header_footer: '移除页眉页脚',
  remove_page_numbers: '移除页码',
  remove_boilerplate: '移除模板文本',
  remove_urls_emails: '移除URL/邮箱',
  dedup_exact: '精确去重',
  dedup_near: '模糊去重',
  fix_ocr_artifacts: 'OCR纠错',
  normalize_financial_numbers: '数字格式标准化',
};

const GATE_STATUS_LABELS = {
  passed: '通过',
  warning: '告警',
  blocked: '阻断',
};

const metricCards = computed(() => {
  if (!summary.value) {
    return [];
  }

  return [
    {
      key: 'defaults',
      label: '默认规则覆盖',
      value: `${summary.value.defaultRuleCount}/${summary.value.defaultRuleTotal}`,
      hint: summary.value.defaultRulesInitialized ? '默认规则已齐全' : '仍有默认规则缺失',
    },
    {
      key: 'enabled',
      label: '已启用规则',
      value: `${summary.value.enabledRuleCount}`,
      hint: `默认规则中启用 ${summary.value.enabledDefaultRuleCount} 条`,
    },
    {
      key: 'history',
      label: '最近清洗样本',
      value: `${summary.value.recentResultCount}`,
      hint: summary.value.lastCleanedAt ? `最后一次执行 ${summary.value.lastCleanedAt}` : '尚无清洗记录',
    },
  ];
});

const governanceStatus = computed(() => {
  if (!summary.value || summary.value.averageQualityScore == null) {
    return {
      status: 'warning',
      title: '等待首批样本',
      detail: '当前还没有足够的清洗结果沉淀。先选一份代表性文档执行清洗，再判断规则是否需要收紧。',
    };
  }

  const score = summary.value.averageQualityScore;
  const { minQualityScore, warnQualityScore, blockBelowThreshold } = summary.value.qualityGate;
  if (score < minQualityScore) {
    return {
      status: blockBelowThreshold ? 'blocked' : 'warning',
      title: blockBelowThreshold ? '当前规则有阻断风险' : '当前规则需要人工复核',
      detail: `平均清洗分 ${score.toFixed(1)} 低于最低阈值 ${minQualityScore.toFixed(1)}，应优先检查低分文档与误伤规则。`,
    };
  }

  if (score < warnQualityScore) {
    return {
      status: 'warning',
      title: '整体质量可用，但仍需调优',
      detail: `平均清洗分 ${score.toFixed(1)} 低于建议阈值 ${warnQualityScore.toFixed(1)}，建议优先排查命中频繁但收益有限的规则。`,
    };
  }

  return {
    status: 'passed',
    title: '清洗链路整体稳定',
    detail: `平均清洗分 ${score.toFixed(1)} 已高于建议阈值 ${warnQualityScore.toFixed(1)}，当前可继续按样本抽检维护规则。`,
  };
});

const workflowSteps = [
  { key: 'defaults', label: '补齐默认规则', detail: '先确保基础清洗规则完整，避免每次从零配置。' },
  { key: 'tune', label: '调优优先级与配置', detail: '按命中顺序调整规则，先处理收益最高的前几条。' },
  { key: 'verify', label: '回到文档验证结果', detail: '通过文档详情的“清洗结果”页判断新规则是否真正改善正文质量。' },
];

const recentResults = computed(() => summary.value?.recentResults || []);

async function loadRules() {
  loading.value = true;
  try {
    const data = await cleaningApi.listRules();
    rules.value = Array.isArray(data) ? data : data.rules || [];
  } catch (err) {
    ElMessage.error(err.message || '加载清洗规则失败');
  } finally {
    loading.value = false;
  }
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    summary.value = await cleaningApi.getSummary();
  } catch (err) {
    ElMessage.error(err.message || '加载清洗状态失败');
  } finally {
    summaryLoading.value = false;
  }
}

function handleCreate() {
  editingRule.value = null;
  dialogVisible.value = true;
}

function handleEdit(rule) {
  editingRule.value = { ...rule };
  dialogVisible.value = true;
}

async function handleDelete(rule) {
  try {
    await ElMessageBox.confirm(`确定删除规则「${rule.name}」？`, '确认删除', { type: 'warning' });
    await cleaningApi.deleteRule(rule.id);
    ElMessage.success('已删除');
    await Promise.all([loadRules(), loadSummary()]);
  } catch {
    // cancelled
  }
}

async function handleToggle(rule) {
  try {
    await cleaningApi.updateRule(rule.id, { enabled: !rule.enabled });
    ElMessage.success(rule.enabled ? '已禁用' : '已启用');
    await Promise.all([loadRules(), loadSummary()]);
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
  }
}

async function handleBootstrapDefaults() {
  try {
    await ElMessageBox.confirm(
      '这会补齐缺失的默认规则，但不会覆盖你已经修改过的规则配置。是否继续？',
      '初始化默认规则',
      { type: 'warning' },
    );
    const result = await cleaningApi.bootstrapDefaultRules();
    ElMessage.success(result.created_count > 0 ? `已初始化 ${result.created_count} 条默认规则` : '默认规则已齐全');
    await Promise.all([loadRules(), loadSummary()]);
  } catch (err) {
    if (err?.message && !String(err.message).toLowerCase().includes('cancel')) {
      ElMessage.error(err.message || '初始化默认规则失败');
    }
  }
}

async function handleSubmit(payload) {
  try {
    if (editingRule.value?.id) {
      await cleaningApi.updateRule(editingRule.value.id, payload);
      ElMessage.success('规则已更新');
    } else {
      await cleaningApi.createRule(payload);
      ElMessage.success('规则已创建');
    }
    dialogVisible.value = false;
    await Promise.all([loadRules(), loadSummary()]);
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
  }
}

function handleOpenDocument(result) {
  if (!result?.documentId) {
    ElMessage.warning('当前结果没有关联文档');
    return;
  }
  router.push(`/admin/knowledge/documents/${result.documentId}?tab=cleaning`);
}

onMounted(async () => {
  await Promise.all([loadRules(), loadSummary()]);
});
</script>

<template>
  <div class="cleaning-dashboard">
    <section v-if="summary" class="cleaning-dashboard__hero" v-loading="summaryLoading">
      <div class="cleaning-dashboard__hero-main">
        <p class="cleaning-dashboard__eyebrow">Knowledge governance / Cleaning</p>
        <h2>把规则配置页，变成可判断的清洗治理台</h2>
        <p class="cleaning-dashboard__hero-copy">
          这里不只是维护规则，还用于判断当前清洗链路是否稳定、哪些文档需要复核，以及新规则上线后该去哪里验证效果。
        </p>

        <div :class="['cleaning-dashboard__score-panel', `is-${governanceStatus.status}`]">
          <div class="cleaning-dashboard__score-main">
            <p class="cleaning-dashboard__status-label">整体清洗判断</p>
            <div class="cleaning-dashboard__score-row">
              <strong class="cleaning-dashboard__score-value">
                {{ summary.averageQualityScore == null ? '--' : summary.averageQualityScore.toFixed(1) }}
              </strong>
              <span :class="['cleaning-dashboard__status-pill', `is-${governanceStatus.status}`]">
                {{ GATE_STATUS_LABELS[governanceStatus.status] || governanceStatus.status }}
              </span>
            </div>
            <p class="cleaning-dashboard__score-title">{{ governanceStatus.title }}</p>
            <p class="cleaning-dashboard__score-detail">{{ governanceStatus.detail }}</p>
          </div>

          <div class="cleaning-dashboard__metric-grid">
            <article
              v-for="card in metricCards"
              :key="card.key"
              class="cleaning-dashboard__metric-card"
            >
              <p class="cleaning-dashboard__status-label">{{ card.label }}</p>
              <strong class="cleaning-dashboard__metric-value">{{ card.value }}</strong>
              <p class="cleaning-dashboard__status-hint">{{ card.hint }}</p>
            </article>
          </div>
        </div>
      </div>

      <aside :class="['cleaning-dashboard__hero-side', `is-${governanceStatus.status}`]">
        <div class="cleaning-dashboard__hero-side-head">
          <span :class="['cleaning-dashboard__status-pill', `is-${governanceStatus.status}`]">
            {{ governanceStatus.title }}
          </span>
          <h3>清洗门槛与操作顺序</h3>
        </div>
        <p>
          当前最低质量分为
          <strong>{{ summary.qualityGate.minQualityScore.toFixed(1) }}</strong>，
          建议阈值为
          <strong>{{ summary.qualityGate.warnQualityScore.toFixed(1) }}</strong>。
          <span>{{ summary.qualityGate.blockBelowThreshold ? '低于最低阈值会阻断入库。' : '低于最低阈值仅做告警。' }}</span>
        </p>
        <div class="cleaning-dashboard__workflow">
          <article
            v-for="step in workflowSteps"
            :key="step.key"
            class="cleaning-dashboard__workflow-step"
          >
            <strong>{{ step.label }}</strong>
            <span>{{ step.detail }}</span>
          </article>
        </div>
        <p v-if="summary.missingDefaultRuleNames.length" class="cleaning-dashboard__warning">
          缺失默认规则：{{ summary.missingDefaultRuleNames.join('、') }}
        </p>
        <el-button type="primary" plain @click="handleBootstrapDefaults">
          初始化默认规则
        </el-button>
      </aside>
    </section>

    <section class="cleaning-dashboard__workspace">
      <div class="cleaning-dashboard__main">
        <section class="cleaning-dashboard__surface">
          <div class="cleaning-dashboard__header">
            <div>
              <h3>清洗规则</h3>
              <p class="cleaning-dashboard__header-copy">规则决定文档在清洗阶段会如何被修正、去重和评分，优先级越靠前越先命中。</p>
            </div>
            <el-button type="primary" @click="handleCreate">新建规则</el-button>
          </div>

          <el-table :data="rules" v-loading="loading" stripe style="width: 100%">
            <el-table-column prop="name" label="规则名称" min-width="160" />
            <el-table-column label="类型" min-width="140">
              <template #default="{ row }">
                <el-tag size="small">{{ RULE_TYPE_LABELS[row.rule_type] || row.rule_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="90" align="center" />
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
                <el-button link type="primary" size="small" @click="handleToggle(row)">
                  {{ row.enabled ? '禁用' : '启用' }}
                </el-button>
                <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>

      <aside class="cleaning-dashboard__rail">
        <section class="cleaning-dashboard__surface cleaning-dashboard__guide">
          <div>
            <h3>怎么使用这套清洗能力</h3>
            <p>
              这里主要负责配置规则与观察最近结果。修改规则后，历史文档不会自动重新清洗；
              要让规则生效，请到具体文档详情页执行“清洗结果 / 执行清洗”，或重新入库让文档重走完整链路。
            </p>
          </div>
          <p class="cleaning-dashboard__guide-note">
            推荐操作顺序：补齐默认规则 → 调整优先级/配置 → 打开文档详情查看清洗结果 → 需要时重新入库。
          </p>
        </section>

        <section class="cleaning-dashboard__surface cleaning-dashboard__recent">
          <div class="cleaning-dashboard__recent-header">
            <h3>最近清洗结果</h3>
            <p>最近一次清洗时间：{{ summary?.lastCleanedAt || '暂无记录' }}</p>
          </div>
          <div v-if="recentResults.length" class="cleaning-dashboard__recent-list">
            <button
              v-for="row in recentResults"
              :key="row.id"
              type="button"
              class="cleaning-dashboard__recent-card"
              @click="handleOpenDocument(row)"
            >
              <div class="cleaning-dashboard__recent-card-head">
                <strong>{{ row.documentTitle }}</strong>
                <span :class="['cleaning-dashboard__status-pill', `is-${row.qualityGate.status}`]">
                  {{ GATE_STATUS_LABELS[row.qualityGate.status] || row.qualityGate.status }}
                </span>
              </div>
              <div class="cleaning-dashboard__recent-card-meta">
                <span>质量分 {{ row.qualityScore.toFixed(1) }}</span>
                <span>{{ row.cleanedAt || '暂无时间' }}</span>
              </div>
            </button>
          </div>
          <div v-else class="cleaning-dashboard__empty">
            当前还没有清洗记录。先选择一份文档执行清洗，再回到这里观察治理效果。
          </div>
        </section>
      </aside>
    </section>

    <CleaningRuleDialog
      v-model:visible="dialogVisible"
      :rule="editingRule"
      @submit="handleSubmit"
    />
  </div>
</template>

<style scoped>
.cleaning-dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.cleaning-dashboard__hero,
.cleaning-dashboard__workspace {
  display: grid;
  gap: 16px;
}

.cleaning-dashboard__hero {
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.9fr);
  align-items: stretch;
}

.cleaning-dashboard__workspace {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.85fr);
  align-items: start;
}

.cleaning-dashboard__surface,
.cleaning-dashboard__hero-main,
.cleaning-dashboard__hero-side {
  border: 1px solid color-mix(in oklab, var(--brand) 14%, var(--line-soft));
  border-radius: 22px;
  background:
    linear-gradient(180deg, color-mix(in oklab, var(--brand) 4%, var(--surface-2)) 0%, var(--surface-2) 100%);
  box-shadow: 0 14px 38px rgba(15, 23, 42, 0.06);
  padding: 20px 22px;
}

.cleaning-dashboard__hero-main,
.cleaning-dashboard__hero-side,
.cleaning-dashboard__main,
.cleaning-dashboard__rail,
.cleaning-dashboard__guide,
.cleaning-dashboard__recent,
.cleaning-dashboard__score-main,
.cleaning-dashboard__score-panel,
.cleaning-dashboard__metric-card,
.cleaning-dashboard__workflow,
.cleaning-dashboard__workflow-step,
.cleaning-dashboard__recent-list {
  display: flex;
  flex-direction: column;
}

.cleaning-dashboard__hero-main,
.cleaning-dashboard__hero-side,
.cleaning-dashboard__guide,
.cleaning-dashboard__recent,
.cleaning-dashboard__score-panel,
.cleaning-dashboard__recent-list {
  gap: 16px;
}

.cleaning-dashboard__eyebrow,
.cleaning-dashboard__status-label,
.cleaning-dashboard__status-hint,
.cleaning-dashboard__hero-copy,
.cleaning-dashboard__hero-side p,
.cleaning-dashboard__guide p,
.cleaning-dashboard__header-copy,
.cleaning-dashboard__recent-header p,
.cleaning-dashboard__workflow-step span,
.cleaning-dashboard__empty,
.cleaning-dashboard__recent-card-meta {
  margin: 0;
  color: var(--text-secondary);
}

.cleaning-dashboard__eyebrow,
.cleaning-dashboard__status-label {
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.cleaning-dashboard__hero-main h2,
.cleaning-dashboard__header h3,
.cleaning-dashboard__hero-side h3,
.cleaning-dashboard__guide h3,
.cleaning-dashboard__recent-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.cleaning-dashboard__hero-main h2 {
  font-size: 2rem;
  line-height: 1.1;
  max-width: 14ch;
}

.cleaning-dashboard__hero-copy,
.cleaning-dashboard__hero-side p,
.cleaning-dashboard__guide p,
.cleaning-dashboard__header-copy,
.cleaning-dashboard__empty,
.cleaning-dashboard__workflow-step span,
.cleaning-dashboard__recent-card-meta {
  font-size: 0.95rem;
  line-height: 1.65;
}

.cleaning-dashboard__score-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(280px, 0.95fr);
  gap: 16px;
  border-radius: 20px;
  padding: 18px;
}

.cleaning-dashboard__score-panel.is-passed,
.cleaning-dashboard__hero-side.is-passed {
  border-color: color-mix(in oklab, var(--success) 32%, var(--line-soft));
  background:
    linear-gradient(180deg, color-mix(in oklab, var(--success) 8%, var(--surface-2)) 0%, var(--surface-2) 100%);
}

.cleaning-dashboard__score-panel.is-warning,
.cleaning-dashboard__hero-side.is-warning {
  border-color: color-mix(in oklab, #d97706 28%, var(--line-soft));
  background:
    linear-gradient(180deg, color-mix(in oklab, #d97706 7%, var(--surface-2)) 0%, var(--surface-2) 100%);
}

.cleaning-dashboard__score-panel.is-blocked,
.cleaning-dashboard__hero-side.is-blocked {
  border-color: color-mix(in oklab, var(--risk) 30%, var(--line-soft));
  background:
    linear-gradient(180deg, color-mix(in oklab, var(--risk) 8%, var(--surface-2)) 0%, var(--surface-2) 100%);
}

.cleaning-dashboard__score-row,
.cleaning-dashboard__header,
.cleaning-dashboard__recent-header,
.cleaning-dashboard__recent-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.cleaning-dashboard__score-value {
  font-size: 4.25rem;
  line-height: 0.92;
  font-weight: 700;
  color: var(--text-primary);
}

.cleaning-dashboard__score-title,
.cleaning-dashboard__score-detail {
  margin: 0;
}

.cleaning-dashboard__score-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cleaning-dashboard__score-detail {
  color: var(--text-secondary);
  line-height: 1.65;
}

.cleaning-dashboard__metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cleaning-dashboard__metric-card {
  gap: 8px;
  border: 1px solid color-mix(in oklab, var(--brand) 14%, var(--line-soft));
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  padding: 14px 15px;
}

.cleaning-dashboard__metric-value {
  font-size: 1.45rem;
  line-height: 1.1;
  font-weight: 700;
  color: var(--text-primary);
}

.cleaning-dashboard__status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1;
}

.cleaning-dashboard__status-pill.is-passed {
  background: color-mix(in oklab, var(--success) 12%, var(--surface-2));
  color: color-mix(in oklab, var(--success) 72%, var(--text-primary));
}

.cleaning-dashboard__status-pill.is-warning {
  background: color-mix(in oklab, #d97706 14%, var(--surface-2));
  color: color-mix(in oklab, #d97706 76%, var(--text-primary));
}

.cleaning-dashboard__status-pill.is-blocked {
  background: color-mix(in oklab, var(--risk) 12%, var(--surface-2));
  color: color-mix(in oklab, var(--risk) 74%, var(--text-primary));
}

.cleaning-dashboard__hero-side-head {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cleaning-dashboard__workflow {
  gap: 10px;
}

.cleaning-dashboard__workflow-step {
  gap: 4px;
  border-top: 1px solid color-mix(in oklab, var(--brand) 10%, var(--line-soft));
  padding-top: 10px;
}

.cleaning-dashboard__workflow-step strong,
.cleaning-dashboard__recent-card-head strong {
  color: var(--text-primary);
}

.cleaning-dashboard__warning {
  margin: 0;
  color: color-mix(in oklab, #9a4f00 80%, var(--text-primary));
}

.cleaning-dashboard__rail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cleaning-dashboard__recent {
  min-height: 100%;
}

.cleaning-dashboard__recent-list {
  gap: 10px;
}

.cleaning-dashboard__recent-card {
  border: 1px solid color-mix(in oklab, var(--brand) 14%, var(--line-soft));
  border-radius: 16px;
  background: color-mix(in oklab, var(--brand) 4%, var(--surface-2));
  padding: 14px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.cleaning-dashboard__recent-card:hover {
  border-color: color-mix(in oklab, var(--brand) 28%, var(--line-soft));
  background: color-mix(in oklab, var(--brand) 8%, var(--surface-2));
  transform: translateY(-1px);
}

.cleaning-dashboard__recent-card-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

:deep(.el-table) {
  --el-table-border-color: color-mix(in oklab, var(--brand) 12%, var(--line-soft));
  --el-table-header-bg-color: color-mix(in oklab, var(--brand) 4%, var(--surface-2));
  --el-table-row-hover-bg-color: color-mix(in oklab, var(--brand) 5%, var(--surface-2));
}

@media (max-width: 1100px) {
  .cleaning-dashboard__hero,
  .cleaning-dashboard__workspace,
  .cleaning-dashboard__score-panel {
    grid-template-columns: 1fr;
  }

  .cleaning-dashboard__metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .cleaning-dashboard__metric-grid {
    grid-template-columns: 1fr;
  }

  .cleaning-dashboard__score-row,
  .cleaning-dashboard__recent-header,
  .cleaning-dashboard__header,
  .cleaning-dashboard__recent-card-head {
    flex-direction: column;
  }

  .cleaning-dashboard__score-value {
    font-size: 3.2rem;
  }
}
</style>
