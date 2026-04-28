const LEGACY_TRAINING_KEY_MAP = {
  epochs: 'num_train_epochs',
  batch_size: 'per_device_train_batch_size',
};

const STRUCTURED_TRAINING_KEYS = new Set([
  'stage',
  'template',
  'cutoff_len',
  'max_samples',
  'preprocessing_num_workers',
  'dataloader_num_workers',
  'overwrite_cache',
  'packing',
  'per_device_train_batch_size',
  'gradient_accumulation_steps',
  'learning_rate',
  'num_train_epochs',
  'lr_scheduler_type',
  'warmup_ratio',
  'max_grad_norm',
  'val_size',
  'per_device_eval_batch_size',
  'eval_strategy',
  'eval_steps',
  'logging_steps',
  'save_steps',
  'plot_loss',
  'save_only_model',
  'report_to',
  'bf16',
  'fp16',
  'gradient_checkpointing',
  'lora_rank',
  'lora_alpha',
  'lora_dropout',
  'lora_target',
  'quantization_bit',
  'quantization_method',
  'double_quantization',
]);

export const LLAMAFACTORY_STRATEGY_OPTIONS = [
  { label: 'LoRA', value: 'lora' },
  { label: 'QLoRA', value: 'qlora' },
];

export const LLAMAFACTORY_SCHEDULER_OPTIONS = [
  { label: 'cosine', value: 'cosine' },
  { label: 'linear', value: 'linear' },
  { label: 'constant', value: 'constant' },
  { label: 'polynomial', value: 'polynomial' },
];

export const LLAMAFACTORY_REPORT_TO_OPTIONS = [
  { label: 'none', value: 'none' },
  { label: 'tensorboard', value: 'tensorboard' },
  { label: 'wandb', value: 'wandb' },
  { label: 'mlflow', value: 'mlflow' },
  { label: 'swanlab', value: 'swanlab' },
];

export const LLAMAFACTORY_EVAL_STRATEGY_OPTIONS = [
  { label: 'no', value: 'no' },
  { label: 'steps', value: 'steps' },
  { label: 'epoch', value: 'epoch' },
];

export const LLAMAFACTORY_PRECISION_OPTIONS = [
  { label: 'bf16', value: 'bf16' },
  { label: 'fp16', value: 'fp16' },
  { label: 'auto', value: 'auto' },
];

export const createLlamaFactoryTrainingFormState = () => ({
  stage: 'sft',
  strategy: 'lora',
  template: '',
  cutoff_len: 2048,
  max_samples: null,
  preprocessing_num_workers: 4,
  dataloader_num_workers: 0,
  overwrite_cache: true,
  packing: false,
  per_device_train_batch_size: 1,
  gradient_accumulation_steps: 8,
  learning_rate: 0.0001,
  num_train_epochs: 3,
  lr_scheduler_type: 'cosine',
  warmup_ratio: 0.1,
  max_grad_norm: 1,
  val_size: null,
  per_device_eval_batch_size: 1,
  eval_strategy: 'no',
  eval_steps: null,
  logging_steps: 10,
  save_steps: 200,
  plot_loss: true,
  save_only_model: false,
  report_to: 'none',
  precision_type: 'bf16',
  gradient_checkpointing: true,
  lora_rank: 8,
  lora_alpha: 16,
  lora_dropout: 0,
  lora_target: 'all',
  quantization_bit: 4,
  quantization_method: 'bitsandbytes',
  double_quantization: true,
  advanced_config_json: '',
});

const normalizeLegacyTrainingConfig = (trainingConfig = {}) => {
  const normalized = { ...trainingConfig };

  for (const [legacyKey, normalizedKey] of Object.entries(LEGACY_TRAINING_KEY_MAP)) {
    if (
      normalized[normalizedKey] === undefined &&
      normalized[legacyKey] !== undefined
    ) {
      normalized[normalizedKey] = normalized[legacyKey];
    }
  }

  return normalized;
};

const toPrettyJson = (value) => {
  if (!value || Object.keys(value).length === 0) {
    return '';
  }
  return JSON.stringify(value, null, 2);
};

const parseAdvancedConfigJson = (value) => {
  if (!String(value || '').trim()) {
    return {};
  }
  return JSON.parse(value);
};

const toOptionalNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

export const normalizeLlamaFactoryTrainingConfig = ({
  strategy = 'lora',
  trainingConfig = {},
} = {}) => {
  const formState = createLlamaFactoryTrainingFormState();
  const normalizedConfig = normalizeLegacyTrainingConfig(trainingConfig);

  formState.strategy = normalizedConfig.finetuning_type || strategy || formState.strategy;
  formState.stage = normalizedConfig.stage || formState.stage;
  formState.template = normalizedConfig.template || '';
  formState.cutoff_len = normalizedConfig.cutoff_len ?? formState.cutoff_len;
  formState.max_samples = normalizedConfig.max_samples ?? formState.max_samples;
  formState.preprocessing_num_workers =
    normalizedConfig.preprocessing_num_workers ?? formState.preprocessing_num_workers;
  formState.dataloader_num_workers =
    normalizedConfig.dataloader_num_workers ?? formState.dataloader_num_workers;
  formState.overwrite_cache = normalizedConfig.overwrite_cache ?? formState.overwrite_cache;
  formState.packing = normalizedConfig.packing ?? formState.packing;
  formState.per_device_train_batch_size =
    normalizedConfig.per_device_train_batch_size ?? formState.per_device_train_batch_size;
  formState.gradient_accumulation_steps =
    normalizedConfig.gradient_accumulation_steps ?? formState.gradient_accumulation_steps;
  formState.learning_rate = normalizedConfig.learning_rate ?? formState.learning_rate;
  formState.num_train_epochs =
    normalizedConfig.num_train_epochs ?? formState.num_train_epochs;
  formState.lr_scheduler_type =
    normalizedConfig.lr_scheduler_type || formState.lr_scheduler_type;
  formState.warmup_ratio = normalizedConfig.warmup_ratio ?? formState.warmup_ratio;
  formState.max_grad_norm = normalizedConfig.max_grad_norm ?? formState.max_grad_norm;
  formState.val_size = normalizedConfig.val_size ?? formState.val_size;
  formState.per_device_eval_batch_size =
    normalizedConfig.per_device_eval_batch_size ?? formState.per_device_eval_batch_size;
  formState.eval_strategy = normalizedConfig.eval_strategy || formState.eval_strategy;
  formState.eval_steps = normalizedConfig.eval_steps ?? formState.eval_steps;
  formState.logging_steps = normalizedConfig.logging_steps ?? formState.logging_steps;
  formState.save_steps = normalizedConfig.save_steps ?? formState.save_steps;
  formState.plot_loss = normalizedConfig.plot_loss ?? formState.plot_loss;
  formState.save_only_model = normalizedConfig.save_only_model ?? formState.save_only_model;
  formState.report_to = normalizedConfig.report_to || formState.report_to;
  formState.gradient_checkpointing =
    normalizedConfig.gradient_checkpointing ?? formState.gradient_checkpointing;
  formState.lora_rank = normalizedConfig.lora_rank ?? formState.lora_rank;
  formState.lora_alpha = normalizedConfig.lora_alpha ?? formState.lora_alpha;
  formState.lora_dropout = normalizedConfig.lora_dropout ?? formState.lora_dropout;
  formState.lora_target = normalizedConfig.lora_target || formState.lora_target;
  formState.quantization_bit =
    normalizedConfig.quantization_bit ?? formState.quantization_bit;
  formState.quantization_method =
    normalizedConfig.quantization_method || formState.quantization_method;
  formState.double_quantization =
    normalizedConfig.double_quantization ?? formState.double_quantization;

  if (normalizedConfig.bf16) {
    formState.precision_type = 'bf16';
  } else if (normalizedConfig.fp16) {
    formState.precision_type = 'fp16';
  } else {
    formState.precision_type = 'auto';
  }

  const advancedConfig = Object.entries(normalizedConfig).reduce((acc, [key, value]) => {
    if (STRUCTURED_TRAINING_KEYS.has(key) || key === 'finetuning_type') {
      return acc;
    }
    if (LEGACY_TRAINING_KEY_MAP[key]) {
      return acc;
    }
    acc[key] = value;
    return acc;
  }, {});

  formState.advanced_config_json = toPrettyJson(advancedConfig);
  return formState;
};

export const buildLlamaFactoryTrainingConfig = (formState) => {
  const advancedConfig = parseAdvancedConfigJson(formState.advanced_config_json);
  const trainingConfig = {
    stage: formState.stage || 'sft',
    template: String(formState.template || '').trim(),
    cutoff_len: toOptionalNumber(formState.cutoff_len),
    max_samples: toOptionalNumber(formState.max_samples),
    preprocessing_num_workers: toOptionalNumber(formState.preprocessing_num_workers),
    dataloader_num_workers: toOptionalNumber(formState.dataloader_num_workers),
    overwrite_cache: Boolean(formState.overwrite_cache),
    packing: Boolean(formState.packing),
    per_device_train_batch_size: toOptionalNumber(formState.per_device_train_batch_size),
    gradient_accumulation_steps: toOptionalNumber(formState.gradient_accumulation_steps),
    learning_rate: toOptionalNumber(formState.learning_rate),
    num_train_epochs: toOptionalNumber(formState.num_train_epochs),
    lr_scheduler_type: String(formState.lr_scheduler_type || '').trim(),
    warmup_ratio: toOptionalNumber(formState.warmup_ratio),
    max_grad_norm: toOptionalNumber(formState.max_grad_norm),
    val_size: toOptionalNumber(formState.val_size),
    per_device_eval_batch_size: toOptionalNumber(formState.per_device_eval_batch_size),
    eval_strategy: String(formState.eval_strategy || '').trim(),
    eval_steps: toOptionalNumber(formState.eval_steps),
    logging_steps: toOptionalNumber(formState.logging_steps),
    save_steps: toOptionalNumber(formState.save_steps),
    plot_loss: Boolean(formState.plot_loss),
    save_only_model: Boolean(formState.save_only_model),
    report_to: String(formState.report_to || '').trim(),
    gradient_checkpointing: Boolean(formState.gradient_checkpointing),
    lora_rank: toOptionalNumber(formState.lora_rank),
    lora_alpha: toOptionalNumber(formState.lora_alpha),
    lora_dropout: toOptionalNumber(formState.lora_dropout),
    lora_target: String(formState.lora_target || '').trim(),
  };

  if (formState.precision_type === 'bf16') {
    trainingConfig.bf16 = true;
  } else if (formState.precision_type === 'fp16') {
    trainingConfig.fp16 = true;
  }

  if (formState.strategy === 'qlora') {
    trainingConfig.quantization_bit = toOptionalNumber(formState.quantization_bit);
    trainingConfig.quantization_method = String(formState.quantization_method || '').trim();
    trainingConfig.double_quantization = Boolean(formState.double_quantization);
  }

  const mergedConfig = { ...advancedConfig };
  for (const [key, value] of Object.entries(trainingConfig)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    mergedConfig[key] = value;
  }

  return mergedConfig;
};
