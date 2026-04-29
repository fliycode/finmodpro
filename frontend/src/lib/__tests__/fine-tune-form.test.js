import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildFineTunePayload,
  createFineTuneFormState,
} from '../fine-tune-form.js';

test('buildFineTunePayload rejects blank dataset name before request submission', () => {
  const formState = createFineTuneFormState();
  formState.base_model_id = '1';
  formState.training.template = 'llama3';
  formState.dataset_name = '   ';

  assert.throws(
    () => buildFineTunePayload({
      fineTuneForm: formState,
      editingFineTuneId: null,
    }),
    /请填写数据集名称/,
  );
});

test('buildFineTunePayload keeps runner server optional for create', () => {
  const formState = createFineTuneFormState();
  formState.base_model_id = '1';
  formState.dataset_name = '财报基准集';
  formState.dataset_version = '2026Q2';
  formState.training.template = 'llama3';

  const payload = buildFineTunePayload({
    fineTuneForm: formState,
    editingFineTuneId: null,
  });

  assert.equal(payload.runner_server_id, null);
  assert.equal(payload.dataset_name, '财报基准集');
  assert.equal(payload.training_config.template, 'llama3');
});
