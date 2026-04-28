import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildLlamaFactoryTrainingConfig,
  createLlamaFactoryTrainingFormState,
  normalizeLlamaFactoryTrainingConfig,
} from '../llamafactory-config.js';

test('normalizeLlamaFactoryTrainingConfig maps native and legacy fields into form state', () => {
  const formState = normalizeLlamaFactoryTrainingConfig({
    strategy: 'qlora',
    trainingConfig: {
      template: 'llama3',
      cutoff_len: 4096,
      epochs: 5,
      batch_size: 2,
      lora_rank: 16,
      unknown_flag: 'keep-me',
    },
  });

  assert.equal(formState.strategy, 'qlora');
  assert.equal(formState.template, 'llama3');
  assert.equal(formState.cutoff_len, 4096);
  assert.equal(formState.num_train_epochs, 5);
  assert.equal(formState.per_device_train_batch_size, 2);
  assert.equal(formState.lora_rank, 16);
  assert.match(formState.advanced_config_json, /unknown_flag/);
});

test('buildLlamaFactoryTrainingConfig emits native keys and omits qlora-only flags for lora', () => {
  const formState = createLlamaFactoryTrainingFormState();
  Object.assign(formState, {
    strategy: 'lora',
    template: 'qwen',
    cutoff_len: 2048,
    max_samples: 1000,
    per_device_train_batch_size: 1,
    gradient_accumulation_steps: 8,
    learning_rate: 0.0001,
    num_train_epochs: 3,
    lora_rank: 8,
    lora_alpha: 16,
    lora_dropout: 0.05,
    lora_target: 'all',
    advanced_config_json: '{\n  "ddp_timeout": 180000000\n}',
  });

  const trainingConfig = buildLlamaFactoryTrainingConfig(formState);

  assert.deepEqual(trainingConfig.template, 'qwen');
  assert.deepEqual(trainingConfig.cutoff_len, 2048);
  assert.deepEqual(trainingConfig.max_samples, 1000);
  assert.deepEqual(trainingConfig.per_device_train_batch_size, 1);
  assert.deepEqual(trainingConfig.gradient_accumulation_steps, 8);
  assert.deepEqual(trainingConfig.learning_rate, 0.0001);
  assert.deepEqual(trainingConfig.num_train_epochs, 3);
  assert.deepEqual(trainingConfig.lora_rank, 8);
  assert.deepEqual(trainingConfig.lora_alpha, 16);
  assert.deepEqual(trainingConfig.lora_dropout, 0.05);
  assert.deepEqual(trainingConfig.lora_target, 'all');
  assert.deepEqual(trainingConfig.ddp_timeout, 180000000);
  assert.equal('quantization_bit' in trainingConfig, false);
});
