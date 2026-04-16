import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeEvaluationPayload,
  normalizeFineTunePayload,
  normalizeEvaluationRecord,
  normalizeFineTuneRun,
  normalizeModelConfigPayload,
} from '../llm.js';

test('normalizeEvaluationPayload preserves comparison groups and new metrics', () => {
  const payload = normalizeEvaluationPayload({
    total: 2,
    eval_records: [
      {
        id: 7,
        evaluation_mode: 'baseline',
        task_type: 'qa',
        qa_accuracy: '1.0000',
        precision: '0.9500',
        recall: '0.9400',
        f1_score: '0.9450',
        dataset_name: 'qa-smoke',
        dataset_version: '2026Q1',
        run_notes: 'baseline smoke',
      },
    ],
    comparison_groups: [
      {
        evaluation_mode: 'baseline',
        label: '基线',
        total: 1,
        summary: { qa_accuracy: '1.0000', f1_score: '0.9450' },
        records: [
          {
            id: 7,
            evaluation_mode: 'baseline',
            task_type: 'qa',
            qa_accuracy: '1.0000',
            dataset_name: 'qa-smoke',
            dataset_version: '2026Q1',
          },
        ],
      },
    ],
  });

  assert.equal(payload.total, 2);
  assert.equal(payload.eval_records[0].evaluation_mode, 'baseline');
  assert.equal(payload.eval_records[0].run_notes, 'baseline smoke');
  assert.equal(payload.comparison_groups[0].evaluation_mode, 'baseline');
  assert.equal(payload.comparison_groups[0].records[0].dataset_name, 'qa-smoke');
});

test('normalizeFineTunePayload preserves lineage metadata', () => {
  const payload = normalizeFineTunePayload({
    total: 1,
    fine_tune_runs: [
      {
        id: 11,
        base_model_id: 3,
        base_model_name: 'default-chat',
        base_model_capability: 'chat',
        base_model_provider: 'ollama',
        dataset_name: '财报基准集',
      dataset_version: '2026Q1',
      strategy: 'lora',
      status: 'succeeded',
      run_key: 'ft-202604160001-ab12cd',
      runner_name: 'llamafactory-runner-a',
      artifact_path: '/artifacts/runs/ft-20260413',
      export_path: '/exports/fine-tune-runs/ft-20260413',
      deployment_endpoint: 'http://localhost:4000',
      deployment_model_name: 'finmodpro-ft-chat',
      dataset_manifest: { export_status: 'ready' },
      training_config: { epochs: 3 },
      artifact_manifest: { adapter_path: '/artifacts/runs/ft-20260413' },
      metrics: { f1_score: 0.92 },
      callback_token: 'ftcb_visible_once',
      registered_model_config_id: 9,
      notes: '外部训练完成后登记。',
    },
  ],
  });

  assert.equal(payload.total, 1);
  assert.equal(payload.fine_tune_runs[0].base_model_name, 'default-chat');
  assert.equal(payload.fine_tune_runs[0].dataset_name, '财报基准集');
  assert.equal(payload.fine_tune_runs[0].metrics.f1_score, 0.92);
  assert.equal(payload.fine_tune_runs[0].run_key, 'ft-202604160001-ab12cd');
  assert.equal(payload.fine_tune_runs[0].registered_model_config_id, 9);
});

test('normalizeEvaluationRecord and normalizeFineTuneRun provide stable defaults', () => {
  assert.equal(normalizeEvaluationRecord(null).evaluation_mode, 'baseline');
  assert.equal(normalizeFineTuneRun(null).status, 'pending');
});

test('normalizeModelConfigPayload keeps litellm provider values', () => {
  const payload = normalizeModelConfigPayload({
    model_configs: [
      {
        id: 1,
        provider: 'litellm',
        capability: 'chat',
        model_name: 'chat-default',
        endpoint: 'http://localhost:4000',
      },
    ],
  });

  assert.equal(payload[0].provider, 'litellm');
  assert.equal(payload[0].model_name, 'chat-default');
  assert.equal(payload[0].endpoint, 'http://localhost:4000');
});
