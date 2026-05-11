<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import CleaningRuleDialog from './CleaningRuleDialog.vue';
import { cleaningApi } from '../../api/cleaning.js';

const loading = ref(true);
const summaryLoading = ref(true);
const rules = ref([]);
const summary = ref(null);
const dialogVisible = ref(false);
const editingRule = ref(null);

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

const GATE_STATUS_TYPES = {
  passed: 'success',
  warning: 'warning',
  blocked: 'danger',
};

const statusCards = computed(() => {
  if (!summary.value) {
    return [];
  }

  return [
    {
      key: 'defaults',
      label: '默认规则覆盖',
      value: `${summary.value.defaultRuleCount}/${summary.value.defaultRuleTotal}`,
      hint: summary.value.defaultRulesInitialized ? '默认规则已初始化' : '还有缺失规则',
    },
    {
      key: 'enabled',
      label: '已启用规则',
      value: `${summary.value.enabledRuleCount}`,
      hint: `其中默认规则 ${summary.value.enabledDefaultRuleCount} 条`,
    },
    {
      key: 'quality',
      label: '平均清洗分',
      value: summary.value.averageQualityScore == null ? '--' : summary.value.averageQualityScore.toFixed(1),
      hint: `最近 ${summary.value.recentResultCount} 次清洗`,
    },
    {
      key: 'threshold',
      label: '阻断阈值',
      value: `${summary.value.qualityGate.minQualityScore.toFixed(1)}`,
      hint: summary.value.qualityGate.blockBelowThreshold ? '低于阈值阻断入库' : '低于阈值仅告警',
    },
  ];
});

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

onMounted(async () => {
  await Promise.all([loadRules(), loadSummary()]);
});
</script>

<template>
  <div class="cleaning-dashboard">
    <section class="cleaning-dashboard__summary" v-loading="summaryLoading">
      <div
        v-for="card in statusCards"
        :key="card.key"
        class="cleaning-dashboard__status-card"
      >
        <p class="cleaning-dashboard__status-label">{{ card.label }}</p>
        <p class="cleaning-dashboard__status-value">{{ card.value }}</p>
        <p class="cleaning-dashboard__status-hint">{{ card.hint }}</p>
      </div>
    </section>

    <section v-if="summary" class="cleaning-dashboard__gate">
      <div class="cleaning-dashboard__gate-copy">
        <h3>清洗门槛</h3>
        <p>
          当前最低质量分为
          <strong>{{ summary.qualityGate.minQualityScore.toFixed(1) }}</strong>，
          建议阈值为
          <strong>{{ summary.qualityGate.warnQualityScore.toFixed(1) }}</strong>。
          <span>{{ summary.qualityGate.blockBelowThreshold ? '低于最低阈值会阻断入库。' : '低于最低阈值仅做告警。' }}</span>
        </p>
        <p v-if="summary.missingDefaultRuleNames.length" class="cleaning-dashboard__warning">
          缺失默认规则：{{ summary.missingDefaultRuleNames.join('、') }}
        </p>
      </div>
      <el-button type="primary" plain @click="handleBootstrapDefaults">
        初始化默认规则
      </el-button>
    </section>

    <div class="cleaning-dashboard__header">
      <h3>清洗规则</h3>
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

    <section v-if="summary?.recentResults?.length" class="cleaning-dashboard__recent">
      <div class="cleaning-dashboard__recent-header">
        <h3>最近清洗结果</h3>
        <p>最近一次清洗时间：{{ summary.lastCleanedAt || '暂无记录' }}</p>
      </div>
      <el-table :data="summary.recentResults" stripe style="width: 100%">
        <el-table-column prop="documentTitle" label="文档" min-width="200" />
        <el-table-column label="质量分" width="120" align="center">
          <template #default="{ row }">
            {{ row.qualityScore.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column label="门槛判定" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="GATE_STATUS_TYPES[row.qualityGate.status] || 'info'" size="small">
              {{ GATE_STATUS_LABELS[row.qualityGate.status] || row.qualityGate.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cleanedAt" label="清洗时间" min-width="180" />
      </el-table>
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
  gap: 20px;
}

.cleaning-dashboard__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.cleaning-dashboard__status-card,
.cleaning-dashboard__gate,
.cleaning-dashboard__recent {
  border: 1px solid rgba(36, 87, 197, 0.14);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  padding: 18px 20px;
}

.cleaning-dashboard__status-label,
.cleaning-dashboard__status-hint,
.cleaning-dashboard__recent-header p,
.cleaning-dashboard__gate-copy p {
  margin: 0;
}

.cleaning-dashboard__status-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.cleaning-dashboard__status-value {
  margin: 8px 0 6px;
  font-size: 1.9rem;
  font-weight: 700;
  color: var(--text-primary);
}

.cleaning-dashboard__status-hint {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.cleaning-dashboard__gate,
.cleaning-dashboard__recent-header,
.cleaning-dashboard__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.cleaning-dashboard__gate-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cleaning-dashboard__gate-copy h3,
.cleaning-dashboard__header h3,
.cleaning-dashboard__recent-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.cleaning-dashboard__warning {
  color: #9a4f00;
}

.cleaning-dashboard__recent {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1100px) {
  .cleaning-dashboard__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .cleaning-dashboard__summary {
    grid-template-columns: 1fr;
  }

  .cleaning-dashboard__gate,
  .cleaning-dashboard__recent-header,
  .cleaning-dashboard__header {
    flex-direction: column;
  }
}
</style>
