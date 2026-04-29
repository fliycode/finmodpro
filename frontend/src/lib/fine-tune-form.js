import {
  buildLlamaFactoryTrainingConfig,
  createLlamaFactoryTrainingFormState,
} from './llamafactory-config.js';

export const createFineTuneFormState = () => ({
  base_model_id: '',
  runner_server_id: '',
  dataset_name: '',
  dataset_version: '',
  runner_name: '',
  training: createLlamaFactoryTrainingFormState(),
  status: 'pending',
  external_job_id: '',
  artifact_path: '',
  metrics_json: '{\n  "f1_score": 0.9\n}',
  notes: '',
});

export const buildFineTunePayload = ({
  fineTuneForm,
  editingFineTuneId = null,
}) => {
  if (!fineTuneForm.base_model_id) {
    throw new Error('请选择基础模型');
  }

  if (!String(fineTuneForm.dataset_name || '').trim()) {
    throw new Error('请填写数据集名称');
  }

  if (!String(fineTuneForm.training.template || '').trim()) {
    throw new Error('请填写 LLaMA-Factory template');
  }

  let trainingConfig = {};
  try {
    trainingConfig = buildLlamaFactoryTrainingConfig(fineTuneForm.training);
  } catch (error) {
    throw new Error('高级附加参数 JSON 格式不正确');
  }

  const payload = {
    base_model_id: Number(fineTuneForm.base_model_id),
    runner_server_id: fineTuneForm.runner_server_id ? Number(fineTuneForm.runner_server_id) : null,
    dataset_name: fineTuneForm.dataset_name.trim(),
    dataset_version: fineTuneForm.dataset_version.trim(),
    strategy: fineTuneForm.training.strategy || 'lora',
    runner_name: fineTuneForm.runner_name.trim(),
    training_config: trainingConfig,
    notes: fineTuneForm.notes.trim(),
  };

  if (!editingFineTuneId) {
    return payload;
  }

  let metrics = {};
  if (fineTuneForm.metrics_json.trim()) {
    try {
      metrics = JSON.parse(fineTuneForm.metrics_json);
    } catch (error) {
      throw new Error('微调指标 JSON 格式不正确');
    }
  }

  return {
    ...payload,
    status: fineTuneForm.status,
    artifact_path: fineTuneForm.artifact_path.trim(),
    metrics,
  };
};
