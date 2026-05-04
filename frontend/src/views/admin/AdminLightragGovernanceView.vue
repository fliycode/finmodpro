<script setup>
import { reactive, ref } from 'vue';

import { lightragApi } from '../../api/lightrag.js';
import { useFlash } from '../../lib/flash.js';
import LightragPanel from '../../components/lightrag/LightragPanel.vue';

const flash = useFlash();
const errorMsg = ref('');
const isRunning = ref(false);
const activeTab = ref('entities');
const entityExistsResult = ref(null);
const lastResult = ref(null);

const entityCreateForm = reactive({
  entity_name: '',
  entity_data: '{\n  "description": "",\n  "entity_type": "risk"\n}',
});

const entityUpdateForm = reactive({
  entity_name: '',
  updated_data: '{\n  "description": ""\n}',
  allow_rename: false,
  allow_merge: false,
});

const entityMergeForm = reactive({
  entity_to_change_into: '',
  entities_to_change: '',
});

const relationCreateForm = reactive({
  source_entity: '',
  target_entity: '',
  relation_data: '{\n  "relation": "related_to",\n  "description": ""\n}',
});

const relationUpdateForm = reactive({
  source_id: '',
  target_id: '',
  updated_data: '{\n  "description": ""\n}',
});

const cleanupForm = reactive({
  entity_name: '',
  source_entity: '',
  target_entity: '',
});

const parseJson = (value, label) => {
  try {
    return JSON.parse(value);
  } catch (error) {
    throw new Error(`${label} 不是有效 JSON。`);
  }
};

const runAction = async (handler) => {
  isRunning.value = true;
  errorMsg.value = '';
  try {
    lastResult.value = await handler();
    flash.success('治理操作已提交。');
  } catch (error) {
    errorMsg.value = error.message || '图谱治理操作失败。';
  } finally {
    isRunning.value = false;
  }
};

const checkEntityExists = async () => {
  if (!cleanupForm.entity_name.trim()) {
    flash.warning('请输入要检查的实体名。');
    return;
  }
  await runAction(async () => {
    entityExistsResult.value = await lightragApi.entityExists(cleanupForm.entity_name.trim());
    return entityExistsResult.value;
  });
};
</script>

<template>
  <div class="page-stack lightrag-page">
    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    <el-alert title="治理页默认面向管理员，建议在实际使用前先确认实体名与关系 id。" type="warning" show-icon :closable="false" />

    <el-tabs v-model="activeTab" class="lightrag-tabs">
      <el-tab-pane label="实体治理" name="entities">
        <div class="lightrag-grid">
          <LightragPanel title="Check + create entity" desc="先检查实体是否已存在，再决定是否创建。">
            <div class="lightrag-form-stack">
              <el-input v-model="cleanupForm.entity_name" placeholder="检查实体名，例如：流动性风险" />
              <div class="lightrag-inline-row">
                <el-button :loading="isRunning" @click="checkEntityExists">检查实体</el-button>
                <span v-if="entityExistsResult">存在结果：{{ entityExistsResult.exists ? '已存在' : '不存在' }}</span>
              </div>
              <el-input v-model="entityCreateForm.entity_name" placeholder="创建实体名" />
              <el-input v-model="entityCreateForm.entity_data" type="textarea" :rows="6" />
              <el-button
                type="primary"
                :loading="isRunning"
                @click="runAction(() => lightragApi.createEntity({
                  entity_name: entityCreateForm.entity_name.trim(),
                  entity_data: parseJson(entityCreateForm.entity_data, '实体数据'),
                }))"
              >
                创建实体
              </el-button>
            </div>
          </LightragPanel>

          <LightragPanel title="Update + merge + delete" desc="把高风险实体治理动作集中放在一块，减少误触。">
            <div class="lightrag-form-stack">
              <el-input v-model="entityUpdateForm.entity_name" placeholder="待更新实体名" />
              <el-input v-model="entityUpdateForm.updated_data" type="textarea" :rows="6" />
              <div class="lightrag-inline-row">
                <el-switch v-model="entityUpdateForm.allow_rename" inline-prompt active-text="Rename" inactive-text="Rename" />
                <el-switch v-model="entityUpdateForm.allow_merge" inline-prompt active-text="Merge" inactive-text="Merge" />
              </div>
              <el-button
                :loading="isRunning"
                @click="runAction(() => lightragApi.updateEntity({
                  entity_name: entityUpdateForm.entity_name.trim(),
                  updated_data: parseJson(entityUpdateForm.updated_data, '更新数据'),
                  allow_rename: entityUpdateForm.allow_rename,
                  allow_merge: entityUpdateForm.allow_merge,
                }))"
              >
                更新实体
              </el-button>

              <el-input v-model="entityMergeForm.entity_to_change_into" placeholder="保留的目标实体名" />
              <el-input
                v-model="entityMergeForm.entities_to_change"
                type="textarea"
                :rows="3"
                placeholder="待合并实体，每行一个"
              />
              <el-button
                :loading="isRunning"
                @click="runAction(() => lightragApi.mergeEntities({
                  entity_to_change_into: entityMergeForm.entity_to_change_into.trim(),
                  entities_to_change: entityMergeForm.entities_to_change.split('\n').map((item) => item.trim()).filter(Boolean),
                }))"
              >
                合并实体
              </el-button>

              <el-button
                type="danger"
                plain
                :loading="isRunning"
                @click="runAction(() => lightragApi.deleteEntity(cleanupForm.entity_name.trim()))"
              >
                删除实体
              </el-button>
            </div>
          </LightragPanel>
        </div>
      </el-tab-pane>

      <el-tab-pane label="关系治理" name="relations">
        <div class="lightrag-grid">
          <LightragPanel title="Create + update relation" desc="直接创建关系，或按 source / target id 更新关系。">
            <div class="lightrag-form-stack">
              <el-input v-model="relationCreateForm.source_entity" placeholder="source entity" />
              <el-input v-model="relationCreateForm.target_entity" placeholder="target entity" />
              <el-input v-model="relationCreateForm.relation_data" type="textarea" :rows="6" />
              <el-button
                :loading="isRunning"
                @click="runAction(() => lightragApi.createRelation({
                  source_entity: relationCreateForm.source_entity.trim(),
                  target_entity: relationCreateForm.target_entity.trim(),
                  relation_data: parseJson(relationCreateForm.relation_data, '关系数据'),
                }))"
              >
                创建关系
              </el-button>

              <el-input v-model="relationUpdateForm.source_id" placeholder="source id" />
              <el-input v-model="relationUpdateForm.target_id" placeholder="target id" />
              <el-input v-model="relationUpdateForm.updated_data" type="textarea" :rows="6" />
              <el-button
                :loading="isRunning"
                @click="runAction(() => lightragApi.updateRelation({
                  source_id: relationUpdateForm.source_id.trim(),
                  target_id: relationUpdateForm.target_id.trim(),
                  updated_data: parseJson(relationUpdateForm.updated_data, '关系更新数据'),
                }))"
              >
                更新关系
              </el-button>
            </div>
          </LightragPanel>

          <LightragPanel title="Delete relation" desc="按 source entity + target entity 删除关系。">
            <div class="lightrag-form-stack">
              <el-input v-model="cleanupForm.source_entity" placeholder="source entity" />
              <el-input v-model="cleanupForm.target_entity" placeholder="target entity" />
              <el-button
                type="danger"
                plain
                :loading="isRunning"
                @click="runAction(() => lightragApi.deleteRelation({
                  source_entity: cleanupForm.source_entity.trim(),
                  target_entity: cleanupForm.target_entity.trim(),
                }))"
              >
                删除关系
              </el-button>
            </div>
          </LightragPanel>
        </div>
      </el-tab-pane>

      <el-tab-pane label="最近返回" name="result">
        <LightragPanel title="Last response" desc="保留原始返回，方便判断 LightRAG 是否接受了治理指令。">
          <pre v-if="lastResult">{{ JSON.stringify(lastResult, null, 2) }}</pre>
          <div v-else class="admin-empty-state">执行治理操作后，这里会展示最近一次返回。</div>
        </LightragPanel>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.lightrag-page,
.lightrag-form-stack {
  display: grid;
  gap: 16px;
}

.lightrag-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.lightrag-inline-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.lightrag-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
}

pre {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 1180px) {
  .lightrag-grid {
    grid-template-columns: 1fr;
  }
}
</style>
