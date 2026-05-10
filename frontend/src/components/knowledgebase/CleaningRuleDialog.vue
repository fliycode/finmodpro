<script setup>
import { ref, watch, computed } from 'vue';

const props = defineProps({
  visible: Boolean,
  rule: Object,
});

const emit = defineEmits(['update:visible', 'submit']);

const form = ref({
  name: '',
  rule_type: 'clean_whitespace',
  config: '{}',
  enabled: true,
  priority: 100,
});

const RULE_TYPE_OPTIONS = [
  { value: 'clean_whitespace', label: '空白清理' },
  { value: 'fix_encoding', label: '编码修复' },
  { value: 'normalize_quotes', label: '引号标准化' },
  { value: 'remove_bullets', label: '移除项目符号' },
  { value: 'group_broken_paragraphs', label: '段落合并' },
  { value: 'remove_header_footer', label: '移除页眉页脚' },
  { value: 'remove_page_numbers', label: '移除页码' },
  { value: 'remove_boilerplate', label: '移除模板文本' },
  { value: 'remove_urls_emails', label: '移除URL/邮箱' },
  { value: 'dedup_exact', label: '精确去重' },
  { value: 'dedup_near', label: '模糊去重' },
  { value: 'fix_ocr_artifacts', label: 'OCR纠错' },
  { value: 'normalize_financial_numbers', label: '数字格式标准化' },
];

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const isEditing = computed(() => Boolean(props.rule?.id));

watch(() => props.visible, (val) => {
  if (val && props.rule) {
    form.value = {
      name: props.rule.name || '',
      rule_type: props.rule.rule_type || 'clean_whitespace',
      config: JSON.stringify(props.rule.config || {}, null, 2),
      enabled: props.rule.enabled !== false,
      priority: props.rule.priority ?? 100,
    };
  } else if (val) {
    form.value = { name: '', rule_type: 'clean_whitespace', config: '{}', enabled: true, priority: 100 };
  }
});

function handleSubmit() {
  let parsedConfig;
  try {
    parsedConfig = JSON.parse(form.value.config);
  } catch {
    parsedConfig = {};
  }
  emit('submit', {
    ...form.value,
    config: parsedConfig,
  });
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEditing ? '编辑清洗规则' : '新建清洗规则'"
    width="540px"
    destroy-on-close
  >
    <el-form label-width="100px" :model="form">
      <el-form-item label="规则名称">
        <el-input v-model="form.name" placeholder="如: 移除重复页眉" />
      </el-form-item>
      <el-form-item label="规则类型">
        <el-select v-model="form.rule_type" style="width: 100%">
          <el-option
            v-for="opt in RULE_TYPE_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="优先级">
        <el-input-number v-model="form.priority" :min="1" :max="999" />
      </el-form-item>
      <el-form-item label="配置 (JSON)">
        <el-input v-model="form.config" type="textarea" :rows="4" placeholder="{}" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit">
        {{ isEditing ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>
