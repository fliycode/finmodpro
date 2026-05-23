<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmApi } from '../../api/llm.js';
import { useFlash } from '../../lib/flash.js';
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
    const cat = item.category || '';
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

function formatTime(iso) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('zh-CN', { hour12: false });
}

onMounted(load);
</script>

<template>
  <div class="prompts-page">
    <AppSectionCard title="Prompt 模板" admin>
      <div v-if="isLoading" class="prompts-skeleton">
        <div v-for="i in 3" :key="i" class="skeleton-row" />
      </div>

      <div v-else-if="errorMsg" class="prompts-error">
        <span>{{ errorMsg }}</span>
        <button class="btn-retry" @click="load">重试</button>
      </div>

      <template v-else>
        <div v-for="[category, items] in categoryGroups" :key="category" class="prompts-group">
          <div class="prompts-group__label">{{ category }}</div>
          <div v-for="item in items" :key="item.key" class="prompts-row">
            <div class="prompts-row__main">
              <span class="prompts-row__name">{{ item.name || item.key }}</span>
              <span class="prompts-row__key">{{ item.key }}</span>
              <span v-if="item.variables?.length" class="prompts-row__vars">
                <span v-for="v in item.variables" :key="v" class="var-tag">{{ v }}</span>
              </span>
            </div>
            <div class="prompts-row__meta">
              <span class="prompts-row__time">{{ formatTime(item.updated_at) }}</span>
              <button class="btn-edit" @click="openEdit(item)">编辑</button>
            </div>
          </div>
        </div>
      </template>
    </AppSectionCard>

    <Teleport to="body">
      <div v-if="dialogVisible" class="dialog-overlay" @click.self="closeEdit">
        <div class="dialog-panel">
          <div class="dialog-panel__header">
            <span class="dialog-panel__title">编辑 {{ editingItem?.key }}</span>
            <button class="dialog-panel__close" @click="closeEdit" aria-label="关闭">&times;</button>
          </div>
          <div class="dialog-panel__body">
            <textarea
              v-model="editingTemplate"
              class="dialog-panel__textarea"
              rows="14"
              spellcheck="false"
            />
          </div>
          <div class="dialog-panel__footer">
            <button class="btn-cancel" @click="closeEdit">取消</button>
            <button class="btn-save" :disabled="isSaving" @click="save">
              {{ isSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.prompts-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Skeleton ── */
.prompts-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.skeleton-row {
  height: 40px;
  border-radius: 6px;
  background: var(--surface-3);
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.7; }
}

/* ── Error ── */
.prompts-error {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: var(--fs-xs);
}
.btn-retry {
  background: none;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--fs-xs);
  padding: 3px 10px;
  transition: background 0.15s;
}
.btn-retry:hover {
  background: var(--surface-hover);
}

/* ── Groups ── */
.prompts-group {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.prompts-group__label {
  font-size: var(--fs-2xs);
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  text-transform: uppercase;
  padding: 6px 4px 8px;
}

/* ── Row ── */
.prompts-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 4px;
  border-radius: 6px;
  transition: background 0.15s;
}
.prompts-row:hover {
  background: var(--surface-hover);
}
.prompts-row__main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}
.prompts-row__name {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
.prompts-row__key {
  font-size: var(--fs-2xs);
  font-family: var(--mono);
  color: var(--text-muted);
  white-space: nowrap;
}
.prompts-row__vars {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.var-tag {
  font-size: var(--fs-2xs);
  font-family: var(--mono);
  color: var(--brand-400);
  background: var(--brand-soft);
  border-radius: 4px;
  padding: 1px 6px;
}
.prompts-row__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.prompts-row__time {
  font-size: var(--fs-2xs);
  color: var(--text-muted);
  white-space: nowrap;
}
.btn-edit {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: var(--fs-xs);
  padding: 2px 8px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.prompts-row:hover .btn-edit {
  color: var(--text-secondary);
}
.btn-edit:hover {
  color: var(--text-primary);
  background: var(--surface-3);
}

/* ── Dialog ── */
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.48);
}
.dialog-panel {
  width: 620px;
  max-width: calc(100vw - 48px);
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  overflow: hidden;
}
.dialog-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line-soft);
}
.dialog-panel__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.dialog-panel__close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.15s;
}
.dialog-panel__close:hover {
  color: var(--text-primary);
}
.dialog-panel__body {
  padding: 16px 18px;
}
.dialog-panel__textarea {
  width: 100%;
  resize: vertical;
  background: var(--surface-1);
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  color: var(--text-primary);
  font-family: var(--mono);
  font-size: var(--fs-xs);
  line-height: 1.6;
  padding: 12px;
  outline: none;
  transition: border-color 0.15s;
}
.dialog-panel__textarea:focus {
  border-color: var(--brand-500);
  box-shadow: 0 0 0 2px var(--brand-soft);
}
.dialog-panel__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--line-soft);
}
.btn-cancel {
  background: none;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--fs-xs);
  padding: 5px 16px;
  transition: background 0.15s;
}
.btn-cancel:hover {
  background: var(--surface-hover);
}
.btn-save {
  background: var(--brand-500);
  border: none;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: var(--fs-xs);
  font-weight: 500;
  padding: 5px 16px;
  transition: background 0.15s;
}
.btn-save:hover {
  background: var(--brand-600);
}
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
