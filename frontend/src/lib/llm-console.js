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
    provider: item.provider ?? '',
    model_name: item.model_name ?? item.modelName ?? '',
    endpoint: item.endpoint ?? item.base_url ?? '',
    alias: item.alias ?? '',
    status: item.status ?? '',
    raw: item,
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
  const activeModels = normalizeObject(data.active_models);

  return {
    providers: normalizeArray(data.providers).map((provider, index) => normalizeProvider(provider, index)),
    active_models: Object.fromEntries(
      Object.entries(activeModels).map(([key, model]) => [key, normalizeActiveModel(model)]),
    ),
    quick_links: normalizeArray(data.quick_links).map((item) => ({
      label: item?.label ?? '',
      to: item?.to ?? '',
      kind: item?.kind ?? 'route',
      raw: item ?? {},
    })),
    recent_failures: normalizeArray(data.recent_failures),
    overview: normalizeObject(data.overview),
    langfuse: normalizeObject(data.langfuse),
    raw: data,
  };
}

export function normalizeObservabilitySummary(payload = {}) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    overview: {
      ...normalizeObject(data.overview),
      chat_request_count_24h: toNumber(data?.overview?.chat_request_count_24h),
      avg_duration_ms_24h: toNumber(data?.overview?.avg_duration_ms_24h),
      failure_count_24h: toNumber(data?.overview?.failure_count_24h),
      retried_request_count_24h: toNumber(data?.overview?.retried_request_count_24h),
    },
    recent_failures: normalizeArray(data.recent_failures),
    langfuse: {
      ...normalizeObject(data.langfuse),
      configured: Boolean(data?.langfuse?.configured),
      host: data?.langfuse?.host ?? '',
      project: data?.langfuse?.project ?? '',
      workspace: data?.langfuse?.workspace ?? '',
    },
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
    parser_failures: normalizeArray(data.parser_failures),
    ingestion_status: normalizeObject(data.ingestion_status),
    raw: data,
  };
}

export function buildProviderTone(provider) {
  const status = String(provider?.status ?? 'missing').toLowerCase();

  if (status === 'connected' || status === 'healthy' || status === 'ready') {
    return 'success';
  }

  if (status === 'missing' || status === 'degraded' || status === 'warning' || status === 'failed') {
    return 'warning';
  }

  return 'warning';
}

export function buildKnowledgePipeline(steps = []) {
  return normalizeArray(steps).map((step, index) => ({
    label: typeof step === 'string' ? step : String(step?.label ?? step?.name ?? ''),
    index: index + 1,
  }));
}
