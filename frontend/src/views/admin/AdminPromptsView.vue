<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmApi } from '../../api/llm.js';
import { useFlash } from '../../lib/flash.js';
import AppIcon from '../../components/ui/AppIcon.vue';
import AppSectionCard from '../../components/ui/AppSectionCard.vue';

const flash = useFlash();

const isLoading = ref(false);
const isSaving = ref(false);
const errorMsg = ref('');
const configs = ref([]);
const editingItem = ref(null);
const editingTemplate = ref('');
const dialogVisible = ref(false);

const categoryGroups = computed(() => {
  const map = new Map();
  for (const item of configs.value) {
    const cat = item.category || '未分类';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push(item);
  }
  return [...map.entries()];
});

async function load() {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    configs.value = await llmApi.getPromptConfigs();
  } catch (e) {
    errorMsg.value = e.message || '加载失败';
  } finally {
    isLoading.value = false;
  }
}

function openEdit(item) {
  editingItem.value = item;
  editingTemplate.value = item.template || '';
  dialogVisible.value = true;
}

function closeEdit() {
  dialogVisible.value = false;
  editingItem.value = null;
  editingTemplate.value = '';
}

async function save() {
  if (!editingItem.value) return;
  isSaving.value = true;
  try {
    await llmApi.updatePromptConfig(editingItem.value.key, editingTemplate.value);
    flash.success('模板已更新');
    closeEdit();
    await load();
  } catch (e) {
    flash.error(e.message || '保存失败');
  } finally {
    isSaving.value = false;
  }
}

function displayVar(varName) {
  return '{{' + varName + '}}';
}

function insertVar(varName) {
  editingTemplate.value += displayVar(varName);
}

function formatTime(iso) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', { hour12: false });
}

onMounted(load);
</script>

<template>
  <div class="page-stack prompts-page">
    <!-- 页面标题栏 -->
    <div class="prompts-page__header">
      <div class="prompts-page__title-row">
        <h2 class="prompts-page__title">Prompt 模板</h2>
        <span class="prompts-page__count">{{ configs.length }} 个配置</span>
      </div>
      <div class="prompts-page__header-actions">
        <el-button :loading="isLoading" @click="load">
          <AppIcon name="refresh" />
          刷新
        </el-button>
      </div>
    </div>

    <!-- 错误提示 -->
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      show-icon
      :closable="false"
    />

    <!-- 空状态 -->
    <div v-if="!isLoading && !errorMsg && configs.length === 0" class="admin-empty-state">
      暂无 Prompt 配置
    </div>

    <!-- 按分类展示的卡片 -->
    <AppSectionCard
      v-for="[category, items] in categoryGroups"
      :key="category"
      :title="category"
      admin
    >
      <el-table
        :data="items"
        row-key="key"
        size="small"
        v-loading="isLoading"
        element-loading-text="加载中..."
      >
        <el-table-column label="名称" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="prompts-page__name-cell">
              <strong>{{ row.name || row.key }}</strong>
              <small>{{ row.key }}</small>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="变量" min-width="200">
          <template #default="{ row }">
            <div class="prompts-page__var-list">
              <el-tag
                v-for="v in row.variables"
                :key="v"
                size="small"
                type="info"
                class="prompts-page__var-tag"
              >
                {{ v }}
              </el-tag>
              <span v-if="!row.variables?.length" class="prompts-page__muted">--</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="更新时间" width="172">
          <template #default="{ row }">
            <span class="prompts-page__time">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="92" fixed="right" align="right" header-align="right">
          <template #default="{ row }">
            <el-tooltip content="编辑模板" placement="top">
              <button
                type="button"
                class="prompts-page__icon-button"
                @click="openEdit(row)"
              >
                <AppIcon name="pencil" />
              </button>
            </el-tooltip>
          </template>
        </el-table-column>

        <template #empty>
          <div class="admin-empty-state">暂无 Prompt 配置</div>
        </template>
      </el-table>
    </AppSectionCard>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="`编辑模板 · ${editingItem?.key || ''}`"
      width="680px"
      class="prompts-page__dialog-modal"
      destroy-on-close
    >
      <div class="prompts-page__dialog-body">
        <div v-if="editingItem?.variables?.length" class="prompts-page__dialog-vars">
          <span class="prompts-page__dialog-label">可用变量</span>
          <div class="prompts-page__dialog-var-list">
            <el-tag
              v-for="v in editingItem.variables"
              :key="v"
              size="small"
              class="prompts-page__dialog-var-tag"
              @click="insertVar(v)"
            >
              {{ displayVar(v) }}
            </el-tag>
          </div>
        </div>

        <label class="prompts-page__field">
          <span class="prompts-page__field-label">模板内容</span>
          <el-input
            v-model="editingTemplate"
            type="textarea"
            :rows="16"
            class="prompts-page__template-textarea"
          />
        </label>
      </div>

      <template #footer>
        <div class="prompts-page__dialog-actions">
          <el-button @click="closeEdit" :disabled="isSaving">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="save">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.prompts-page {
  --prompts-radius-card: 18px;
  --prompts-radius-dialog: 24px;
  --prompts-radius-input: 12px;
}

/* ── 页面标题栏 ── */
.prompts-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  background: var(--surface-2);
}

.prompts-page__title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.prompts-page__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
}

.prompts-page__count {
  font-size: var(--fs-2xs);
  color: var(--text-muted);
}

/* ── 表格内名称单元格 ── */
.prompts-page__name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.prompts-page__name-cell strong {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.prompts-page__name-cell small {
  font-size: var(--fs-2xs);
  font-family: var(--mono);
  color: var(--text-muted);
}

.prompts-page__muted {
  font-size: var(--fs-2xs);
  color: var(--text-muted);
}

.prompts-page__time {
  font-size: var(--fs-2xs);
  color: var(--text-muted);
  white-space: nowrap;
}

/* ── 变量标签 ── */
.prompts-page__var-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.prompts-page__var-tag {
  font-family: var(--mono);
  font-size: var(--fs-2xs);
}

/* ── 操作图标按钮 ── */
.prompts-page__icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.prompts-page__icon-button:hover {
  color: var(--text-primary);
  background: var(--surface-3);
}

/* ── 编辑对话框 ── */
.prompts-page__dialog-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.prompts-page__dialog-vars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prompts-page__dialog-label {
  font-size: var(--fs-2xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.prompts-page__dialog-var-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.prompts-page__dialog-var-tag {
  font-family: var(--mono);
  font-size: var(--fs-2xs);
  cursor: pointer;
  transition: opacity 0.15s;
}

.prompts-page__dialog-var-tag:hover {
  opacity: 0.75;
}

.prompts-page__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prompts-page__field-label {
  font-size: var(--fs-2xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.prompts-page__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ── Element Plus 深度覆写 ── */

/* 表格 */
.prompts-page :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  border: 1px solid var(--line-soft);
  border-radius: var(--prompts-radius-card);
  overflow: hidden;
}

.prompts-page :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.prompts-page :deep(.el-table th.el-table__cell) {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--surface-3);
}

.prompts-page :deep(.el-table .cell) {
  font-size: var(--fs-xs);
}

/* 输入框 */
.prompts-page :deep(.el-input__wrapper) {
  min-height: 36px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  border-radius: var(--prompts-radius-input);
}

/* 文本域 */
.prompts-page__template-textarea :deep(.el-textarea__inner) {
  min-height: 360px;
  background: var(--surface-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--prompts-radius-input);
  color: var(--text-primary);
  font-family: var(--mono);
  font-size: var(--fs-xs);
  line-height: 1.7;
  resize: vertical;
  padding: 14px;
}

.prompts-page__template-textarea :deep(.el-textarea__inner):focus {
  border-color: var(--brand-500);
  box-shadow: 0 0 0 2px var(--brand-soft);
}

/* 对话框 */
.prompts-page :deep(.el-dialog) {
  border: 1px solid var(--line-strong);
  border-radius: var(--prompts-radius-dialog);
  background: var(--surface-1);
}

.prompts-page :deep(.el-dialog__header) {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--line-soft);
}

.prompts-page :deep(.el-dialog__title) {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.prompts-page :deep(.el-dialog__body) {
  padding: 20px 22px;
}

.prompts-page :deep(.el-dialog__footer) {
  padding: 14px 22px 18px;
  border-top: 1px solid var(--line-soft);
}

/* 标签 */
.prompts-page :deep(.el-tag--small) {
  border-radius: 6px;
  height: 22px;
  padding: 0 8px;
}

/* 加载遮罩 */
.prompts-page :deep(.el-loading-mask) {
  border-radius: var(--prompts-radius-card);
}
</style>
