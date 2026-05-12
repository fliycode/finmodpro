<script setup>
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import { cleaningApi } from '../../api/cleaning.js';
import CleaningRuleDialog from './CleaningRuleDialog.vue';

const loading = ref(true);
const rules = ref([]);
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
    await loadRules();
  } catch {
    // cancelled
  }
}

async function handleToggle(rule) {
  try {
    await cleaningApi.updateRule(rule.id, { enabled: !rule.enabled });
    ElMessage.success(rule.enabled ? '已禁用' : '已启用');
    await loadRules();
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
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
    await loadRules();
  } catch (err) {
    ElMessage.error(err.message || '操作失败');
  }
}

onMounted(async () => {
  await loadRules();
});
</script>

<template>
  <section class="cleaning-dashboard">
    <div class="cleaning-dashboard__surface">
      <div class="cleaning-dashboard__header">
        <h3>清洗规则</h3>
        <el-button type="primary" @click="handleCreate">新增规则</el-button>
      </div>

      <el-table :data="rules" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="规则名称" min-width="180" />
        <el-table-column label="类型" min-width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ RULE_TYPE_LABELS[row.rule_type] || row.rule_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="96" align="center" />
        <el-table-column label="状态" width="96" align="center">
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
    </div>

    <CleaningRuleDialog
      v-model:visible="dialogVisible"
      :rule="editingRule"
      @submit="handleSubmit"
    />
  </section>
</template>

<style scoped>
.cleaning-dashboard {
  display: flex;
  flex-direction: column;
}

.cleaning-dashboard__surface {
  border: 1px solid color-mix(in oklab, var(--brand) 14%, var(--line-soft));
  border-radius: 22px;
  background: var(--surface-2);
  box-shadow: 0 14px 38px rgba(15, 23, 42, 0.06);
  padding: 20px 22px;
}

.cleaning-dashboard__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.cleaning-dashboard__header h3 {
  margin: 0;
  color: var(--text-primary);
}

:deep(.el-table) {
  --el-table-border-color: color-mix(in oklab, var(--brand) 12%, var(--line-soft));
  --el-table-header-bg-color: color-mix(in oklab, var(--brand) 4%, var(--surface-2));
  --el-table-row-hover-bg-color: color-mix(in oklab, var(--brand) 5%, var(--surface-2));
}

@media (max-width: 720px) {
  .cleaning-dashboard__surface {
    padding: 16px;
  }

  .cleaning-dashboard__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
