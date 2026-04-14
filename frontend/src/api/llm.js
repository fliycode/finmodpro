import { createApiConfig } from './config.js';

const apiConfig = createApiConfig();

const unwrap = (data) => {
  if (data && data.data !== undefined && data.code !== undefined) {
    if (data.code !== 0 && data.code !== 200 && data.code !== 201) {
      throw new Error(data.message || '操作失败');
    }
    return data.data;
  }
  return data;
};

const toNumber = (value, fallback = 0) => {
  const numeric = Number(value ?? fallback);
  return Number.isFinite(numeric) ? numeric : fallback;
};

const getArray = (payload, keys) => {
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) {
      return payload[key];
    }
  }
  return [];
};

const buildQueryPath = (path, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
};

export const normalizeModelConfigPayload = (payload = {}) => {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results)
      ? payload.results
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.model_configs)
          ? payload.model_configs
          : Array.isArray(payload?.data)
            ? payload.data
            : [];

  return list.map((item, index) => ({
    id: item.id ?? item.config_id ?? index,
    name: item.name ?? item.config_name ?? item.model_name ?? `config-${index}`,
    provider: item.provider ?? item.vendor ?? "--",
    model_name: item.model_name ?? item.model ?? item.name ?? "--",
    endpoint: item.endpoint ?? item.api_base ?? item.base_url ?? "",
    capability: item.capability ?? item.model_type ?? item.type ?? "chat",
    is_active: item.is_active ?? item.active ?? item.enabled ?? false,
    updated_at: item.updated_at ?? item.updatedAt ?? item.modified_at ?? item.created_at ?? "",
    options: item.options ?? {},
    has_api_key: item.has_api_key ?? false,
    api_key_masked: item.api_key_masked ?? "",
    fine_tune_run_count: Number(item.fine_tune_run_count ?? 0),
    latest_fine_tune_dataset: item.latest_fine_tune_dataset ?? "",
    latest_fine_tune_status: item.latest_fine_tune_status ?? "",
    latest_fine_tune_artifact_path: item.latest_fine_tune_artifact_path ?? "",
    raw: item,
  }));
};

export const normalizeEvaluationRecord = (item, index = 0) => ({
  id: item?.id ?? item?.evaluation_id ?? index,
  model_config_id: item?.model_config_id ?? null,
  evaluation_mode: item?.evaluation_mode ?? 'baseline',
  target_name: item?.target_name ?? item?.targetName ?? item?.name ?? `evaluation-${index}`,
  task_type: item?.task_type ?? item?.taskType ?? item?.type ?? '--',
  status: item?.status ?? item?.state ?? 'pending',
  qa_accuracy: item?.qa_accuracy ?? item?.qaAccuracy ?? null,
  extraction_accuracy: item?.extraction_accuracy ?? item?.extractionAccuracy ?? null,
  precision: item?.precision ?? null,
  recall: item?.recall ?? null,
  f1_score: item?.f1_score ?? null,
  average_latency_ms: item?.average_latency_ms ?? item?.avg_latency_ms ?? null,
  version: item?.version ?? item?.eval_version ?? item?.tag ?? '--',
  dataset_name: item?.dataset_name ?? '',
  dataset_version: item?.dataset_version ?? '',
  run_notes: item?.run_notes ?? '',
  metadata: item?.metadata ?? {},
  created_at: item?.created_at ?? item?.createdAt ?? item?.started_at ?? item?.updated_at ?? '',
  raw: item ?? {},
});

export const normalizeEvaluationGroup = (group, index = 0) => {
  const records = getArray(group, ['records', 'eval_records']).map((item, recordIndex) => normalizeEvaluationRecord(item, recordIndex));
  const summary = group?.summary || {};
  return {
    evaluation_mode: group?.evaluation_mode ?? 'baseline',
    label: group?.label ?? `分组 ${index + 1}`,
    total: toNumber(group?.total, records.length),
    summary: {
      qa_accuracy: summary.qa_accuracy ?? null,
      extraction_accuracy: summary.extraction_accuracy ?? null,
      precision: summary.precision ?? null,
      recall: summary.recall ?? null,
      f1_score: summary.f1_score ?? null,
      average_latency_ms: summary.average_latency_ms ?? null,
    },
    records,
    raw: group ?? {},
  };
};

export const normalizeEvaluationPayload = (payload = {}) => {
  const evalRecords = getArray(payload, ['eval_records', 'evaluations']).map((item, index) => normalizeEvaluationRecord(item, index));
  const comparisonGroups = getArray(payload, ['comparison_groups']).map((group, index) => normalizeEvaluationGroup(group, index));

  return {
    total: toNumber(payload.total, evalRecords.length),
    eval_records: evalRecords,
    comparison_groups: comparisonGroups,
  };
};

export const normalizeFineTuneRun = (item, index = 0) => ({
  id: item?.id ?? item?.fine_tune_run_id ?? index,
  base_model_id: item?.base_model_id ?? null,
  base_model_name: item?.base_model_name ?? item?.baseModelName ?? '',
  base_model_capability: item?.base_model_capability ?? '',
  base_model_provider: item?.base_model_provider ?? '',
  dataset_name: item?.dataset_name ?? '',
  dataset_version: item?.dataset_version ?? '',
  strategy: item?.strategy ?? 'lora',
  status: item?.status ?? 'pending',
  artifact_path: item?.artifact_path ?? '',
  metrics: item?.metrics ?? {},
  notes: item?.notes ?? '',
  created_at: item?.created_at ?? '',
  updated_at: item?.updated_at ?? '',
  raw: item ?? {},
});

export const normalizeFineTunePayload = (payload = {}) => {
  const fineTuneRuns = getArray(payload, ['fine_tune_runs']).map((item, index) => normalizeFineTuneRun(item, index));

  return {
    total: toNumber(payload.total, fineTuneRuns.length),
    fine_tune_runs: fineTuneRuns,
  };
};

export const llmApi = {
  async getModelConfigs() {
    return unwrap(await apiConfig.fetchJson('/api/ops/model-configs/', {
      method: 'GET',
      auth: true,
    }));
  },

  async activateModelConfig(id, isActive) {
    return unwrap(await apiConfig.fetchJson(`/api/ops/model-configs/${id}/activation/`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify({ is_active: isActive }),
    }));
  },

  async createModelConfig(payload) {
    return unwrap(await apiConfig.fetchJson('/api/ops/model-configs/', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async updateModelConfig(id, payload) {
    return unwrap(await apiConfig.fetchJson(`/api/ops/model-configs/${id}/`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async testModelConfigConnection(payload) {
    return unwrap(await apiConfig.fetchJson('/api/ops/model-configs/test-connection/', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    }));
  },

  async getEvaluations() {
    return normalizeEvaluationPayload(unwrap(await apiConfig.fetchJson('/api/ops/evaluations', {
      method: 'GET',
      auth: true,
    })));
  },

  async triggerEvaluation(data) {
    const payload = unwrap(await apiConfig.fetchJson('/api/ops/evaluations', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(data),
    }));
    return {
      eval_record: normalizeEvaluationRecord(payload.eval_record || payload),
    };
  },

  async getFineTuneRuns(params = {}) {
    return normalizeFineTunePayload(unwrap(await apiConfig.fetchJson(buildQueryPath('/api/ops/fine-tunes/', params), {
      method: 'GET',
      auth: true,
    })));
  },

  async createFineTuneRun(payload) {
    const data = unwrap(await apiConfig.fetchJson('/api/ops/fine-tunes/', {
      method: 'POST',
      auth: true,
      body: JSON.stringify(payload),
    }));
    return {
      fine_tune_run: normalizeFineTuneRun(data.fine_tune_run || data),
    };
  },

  async updateFineTuneRun(id, payload) {
    const data = unwrap(await apiConfig.fetchJson(`/api/ops/fine-tunes/${id}/`, {
      method: 'PATCH',
      auth: true,
      body: JSON.stringify(payload),
    }));
    return {
      fine_tune_run: normalizeFineTuneRun(data.fine_tune_run || data),
    };
  },
};
