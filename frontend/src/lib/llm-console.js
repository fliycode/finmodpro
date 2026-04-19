const toNumber = (value, fallback = 0) => {
  const numeric = Number(value ?? fallback);
  return Number.isFinite(numeric) ? numeric : fallback;
};

const normalizeObject = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }

  return value;
};

const normalizeArray = (value) => (Array.isArray(value) ? value : []);

const normalizeObjectWithDefaults = (value, defaults) => ({
  ...defaults,
  ...normalizeObject(value),
});

const DEFAULT_ACTIVE_MODEL = {
  provider: '',
  model_name: '',
  endpoint: '',
  alias: '',
  status: '',
  raw: {},
};

const DEFAULT_RECENT_ACTIVITY = {
  chat_request_count_24h: 0,
  failed_ingestion_count: 0,
  running_fine_tune_count: 0,
  latest_fine_tune_status: '',
};

const DEFAULT_OBSERVABILITY_OVERVIEW = {
  chat_request_count_24h: 0,
  retrieval_hit_count_24h: 0,
  avg_duration_ms_24h: 0,
  failed_ingestion_count: 0,
};

const DEFAULT_LANGFUSE = {
  configured: false,
  host: '',
  has_public_key: false,
  has_secret_key: false,
};

const DEFAULT_INGESTION_SUMMARY = {
  total_documents: 0,
  queued: 0,
  running: 0,
  succeeded: 0,
  failed: 0,
};

const normalizeProvider = (provider, index = 0) => {
  const item = normalizeObject(provider);

  return {
    key: item.key ?? item.name ?? `provider-${index + 1}`,
    label: item.label ?? item.name ?? item.key ?? `Provider ${index + 1}`,
    status: item.status ?? 'missing',
    active_count: toNumber(item.active_count ?? item.activeCount, 0),
    last_active_at: item.last_active_at ?? item.lastActiveAt ?? '',
    endpoint: item.endpoint ?? item.base_url ?? '',
    model_name: item.model_name ?? item.modelName ?? '',
    alias: item.alias ?? '',
    summary: item.summary ?? item.detail ?? '',
    raw: item,
  };
};

const normalizeActiveModel = (model) => {
  const item = normalizeObject(model);

  return {
    ...DEFAULT_ACTIVE_MODEL,
    provider: item.provider ?? '',
    model_name: item.model_name ?? item.modelName ?? '',
    endpoint: item.endpoint ?? item.base_url ?? '',
    alias: item.alias ?? '',
    status: item.status ?? '',
    raw: item,
  };
};

const normalizeActiveModels = (value) => {
  const item = normalizeObject(value);
  const normalized = {
    chat: normalizeActiveModel(item.chat),
    embedding: normalizeActiveModel(item.embedding),
  };

  const extras = Object.fromEntries(
    Object.entries(item)
      .filter(([key]) => !(key in normalized))
      .map(([key, model]) => [key, normalizeActiveModel(model)]),
  );

  return {
    ...normalized,
    ...extras,
  };
};

const normalizeParserCapability = (capability) => {
  const item = normalizeObject(capability);

  return {
    parser: item.parser ?? '',
    fallback: Boolean(item.fallback),
    status: item.status ?? '',
    detail: item.detail ?? item.summary ?? '',
    raw: item,
  };
};

export function normalizeConsoleSummary(payload = {}) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    providers: normalizeArray(data.providers).map((provider, index) => normalizeProvider(provider, index)),
    active_models: normalizeActiveModels(data.active_models),
    quick_links: normalizeArray(data.quick_links).map((item) => ({
      label: item?.label ?? '',
      to: item?.to ?? '',
      kind: item?.kind ?? 'route',
      raw: item ?? {},
    })),
    recent_activity: normalizeObjectWithDefaults(data.recent_activity, DEFAULT_RECENT_ACTIVITY),
    raw: data,
  };
}

export function normalizeObservabilitySummary(payload = {}) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    overview: normalizeObjectWithDefaults(data.overview, DEFAULT_OBSERVABILITY_OVERVIEW),
    recent_failures: normalizeArray(data.recent_failures),
    langfuse: normalizeObjectWithDefaults(data.langfuse, DEFAULT_LANGFUSE),
    raw: data,
  };
}

export function normalizeKnowledgeSummary(payload = {}) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    parser_capabilities: Object.fromEntries(
      Object.entries(normalizeObject(data.parser_capabilities)).map(([key, capability]) => [
        key,
        normalizeParserCapability(capability),
      ]),
    ),
    pipeline_steps: normalizeArray(data.pipeline_steps),
    ingestion_summary: normalizeObjectWithDefaults(data.ingestion_summary, DEFAULT_INGESTION_SUMMARY),
    recent_failures: normalizeArray(data.recent_failures),
    raw: data,
  };
}

export function buildProviderTone(provider) {
  const status = String(provider?.status ?? 'missing').toLowerCase();

  if (status === 'connected') {
    return 'success';
  }

  if (status === 'configured') {
    return 'info';
  }

  return 'warning';
}

export function buildKnowledgePipeline(steps = []) {
  return normalizeArray(steps).map((step, index) => ({
    label: typeof step === 'string' ? step : String(step?.label ?? step?.name ?? ''),
    index: index + 1,
  }));
}
