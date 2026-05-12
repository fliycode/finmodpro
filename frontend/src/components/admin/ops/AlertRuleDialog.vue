<script setup>
import { computed, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  ALERT_NOTIFICATION_CHANNEL_OPTIONS,
  CONDITION_LABELS,
  DEFAULT_ALERT_NOTIFICATION_CHANNELS,
  METRIC_OPTIONS,
  SEVERITY_LABELS,
} from '../../../lib/admin-monitoring.js';

const props = defineProps({
  visible: { type: Boolean, default: false },
  rule: { type: Object, default: null },
});

const emit = defineEmits(['update:visible', 'submit']);

const form = ref({
  name: '',
  metric_name: '',
  condition: 'gt',
  threshold: 0,
  severity: 'warning',
  enabled: true,
   notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
  description: '',
});

watch(
  () => props.visible,
  (val) => {
    if (val && props.rule) {
      form.value = {
        name: props.rule.name || '',
        metric_name: props.rule.metricName || props.rule.metric_name || '',
        condition: props.rule.condition || 'gt',
        threshold: props.rule.threshold ?? 0,
        severity: props.rule.severity || 'warning',
        enabled: props.rule.enabled !== false,
        notification_channels: Array.isArray(props.rule.notificationChannels)
          ? [...props.rule.notificationChannels]
          : Array.isArray(props.rule.notification_channels)
            ? [...props.rule.notification_channels]
            : [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
        description: props.rule.description || '',
      };
    } else if (val) {
      form.value = {
        name: '',
        metric_name: '',
        condition: 'gt',
        threshold: 0,
        severity: 'warning',
        enabled: true,
        notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
        description: '',
      };
    }
  },
);

const isEditMode = computed(() => Boolean(props.rule?.id));
const conditionOptions = Object.entries(CONDITION_LABELS).map(([value, label]) => ({ value, label }));
const severityOptions = Object.entries(SEVERITY_LABELS).map(([value, label]) => ({ value, label }));

function handleSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入规则名称');
    return;
  }

  if (!form.value.metric_name) {
    ElMessage.warning('请选择监控指标');
    return;
  }

  if (!Array.isArray(form.value.notification_channels) || !form.value.notification_channels.length) {
    ElMessage.warning('请至少选择一种通知方式');
    return;
  }

  emit('submit', { ...form.value });
  emit('update:visible', false);
}

function handleClose() {
  emit('update:visible', false);
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="isEditMode ? '编辑告警规则' : '新建告警规则'"
    width="520px"
    @update:model-value="handleClose"
  >
    <el-form label-width="100px" label-position="left">
      <el-form-item label="规则名称">
        <el-input v-model="form.name" placeholder="如: CPU 使用率过高" />
      </el-form-item>

      <el-form-item label="监控指标">
        <el-select v-model="form.metric_name" placeholder="选择指标" style="width: 100%">
          <el-option
            v-for="opt in METRIC_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="触发条件">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-select v-model="form.condition" style="width: 140px">
            <el-option
              v-for="opt in conditionOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-input-number v-model="form.threshold" :precision="2" style="flex: 1" />
        </div>
      </el-form-item>

      <el-form-item label="严重程度">
        <el-select v-model="form.severity" style="width: 100%">
          <el-option
            v-for="opt in severityOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>

      <el-form-item label="通知方式">
        <el-checkbox-group v-model="form.notification_channels">
          <el-checkbox
            v-for="option in ALERT_NOTIFICATION_CHANNEL_OPTIONS"
            :key="option.value"
            :label="option.value"
          >
            {{ option.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit">
        {{ isEditMode ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>
