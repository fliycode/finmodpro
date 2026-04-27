import { toRaw } from 'vue';

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

const normalizeFilters = (value) => {
  const item = normalizeObject(value);
  return {
    model: item.model ?? null,
    status: item.status ?? null,
    time: item.time ?? '24h',
  };
};

const normalizeGatewayLog = (value) => {
  const item = normalizeObject(value);
  return {
    time: item.time ?? item.created_at ?? '',
    alias: item.alias ?? '',
    upstream_model: item.upstream_model ?? '',
    capability: item.capability ?? '',
    stage: item.stage ?? '',
    latency_ms: toNumber(item.latency_ms, 0),
    request_tokens: toNumber(item.request_tokens, 0),
    response_tokens: toNumber(item.response_tokens, 0),
    status: item.status ?? '',
    error_code: item.error_code ?? '',
    error_message: item.error_message ?? '',
    trace_id: item.trace_id ?? '',
    request_id: item.request_id ?? '',
    raw: item,
  };
};

export const normalizeGatewaySummary = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};
  const gateway = normalizeObject(data.gateway);
  const traffic = normalizeObject(data.traffic);
  const recentSync = data.recent_sync ? normalizeObject(data.recent_sync) : null;

  return {
    gateway: {
      status: gateway.status ?? 'missing',
      active_model_count: toNumber(gateway.active_model_count, 0),
      total_model_count: toNumber(gateway.total_model_count, 0),
    },
    recent_sync: recentSync
      ? {
          status: recentSync.status ?? '',
          message: recentSync.message ?? '',
          created_at: recentSync.created_at ?? '',
          raw: recentSync,
        }
      : null,
    traffic: {
      request_count: toNumber(traffic.request_count, 0),
      failed_count: toNumber(traffic.failed_count, 0),
      error_rate_pct: toNumber(traffic.error_rate_pct, 0),
    },
    top_models: normalizeArray(data.top_models).map((item) => ({
      alias: item?.alias ?? '',
      request_count: toNumber(item?.request_count, 0),
      raw: item ?? {},
    })),
    recent_errors: normalizeArray(data.recent_errors).map(normalizeGatewayLog),
    raw: data,
  };
};

export const normalizeGatewayLogs = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    filters: normalizeFilters(data.filters),
    total: toNumber(data.total, 0),
    page: toNumber(data.page, 1),
    page_size: toNumber(data.page_size, 50),
    logs: normalizeArray(data.logs).map(normalizeGatewayLog),
    raw: data,
  };
};

export const normalizeGatewayLogsSummary = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    filters: normalizeFilters(data.filters),
    total_requests: toNumber(data.total_requests, 0),
    error_rate_pct: toNumber(data.error_rate_pct, 0),
    avg_latency_ms: toNumber(data.avg_latency_ms, 0),
    error_breakdown: normalizeArray(data.error_breakdown).map((item) => ({
      error_code: item?.error_code ?? 'unknown',
      count: toNumber(item?.count, 0),
      raw: item ?? {},
    })),
    latency_buckets: normalizeArray(data.latency_buckets).map((item) => ({
      label: item?.label ?? '',
      count: toNumber(item?.count, 0),
      raw: item ?? {},
    })),
    raw: data,
  };
};

export const normalizeGatewayTrace = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    trace_id: data.trace_id ?? '',
    status: data.status ?? '',
    started_at: data.started_at ?? '',
    ended_at: data.ended_at ?? '',
    logs: normalizeArray(data.logs).map(normalizeGatewayLog),
    raw: data,
  };
};

export const normalizeGatewayErrors = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    total_failed_requests: toNumber(data.total_failed_requests, 0),
    error_types: normalizeArray(data.error_types).map((item) => ({
      error_code: item?.error_code ?? 'unknown',
      count: toNumber(item?.count, 0),
      raw: item ?? {},
    })),
    recent_errors: normalizeArray(data.recent_errors).map(normalizeGatewayLog),
    raw: data,
  };
};

export const normalizeGatewayCostsSummary = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    filters: normalizeFilters(data.filters),
    total_requests: toNumber(data.total_requests, 0),
    total_request_tokens: toNumber(data.total_request_tokens, 0),
    total_response_tokens: toNumber(data.total_response_tokens, 0),
    estimated_input_cost: toNumber(data.estimated_input_cost, 0),
    estimated_output_cost: toNumber(data.estimated_output_cost, 0),
    estimated_total_cost: toNumber(data.estimated_total_cost, 0),
    raw: data,
  };
};

export const normalizeGatewayCostsTimeseries = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    filters: normalizeFilters(data.filters),
    granularity_hours: data.granularity_hours ?? null,
    granularity_minutes: data.granularity_minutes ?? null,
    points: normalizeArray(data.points).map((item) => ({
      bucket: item?.bucket ?? '',
      request_count: toNumber(item?.request_count, 0),
      estimated_cost: toNumber(item?.estimated_cost, 0),
      raw: item ?? {},
    })),
    raw: data,
  };
};

export const normalizeGatewayCostsModels = (payload = {}) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    filters: normalizeFilters(data.filters),
    total_requests: toNumber(data.total_requests, 0),
    models: normalizeArray(data.models).map((item) => ({
      alias: item?.alias ?? '',
      request_count: toNumber(item?.request_count, 0),
      request_share_pct: toNumber(item?.request_share_pct, 0),
      total_request_tokens: toNumber(item?.total_request_tokens, 0),
      total_response_tokens: toNumber(item?.total_response_tokens, 0),
      estimated_input_cost: toNumber(item?.estimated_input_cost, 0),
      estimated_output_cost: toNumber(item?.estimated_output_cost, 0),
      estimated_total_cost: toNumber(item?.estimated_total_cost, 0),
      raw: item ?? {},
    })),
    raw: data,
  };
};

export const getRouteDeleteBlockReason = (route = {}) => (
  route?.is_active
    ? '当前默认路由不能直接删除，请先切换默认链路或在编辑抽屉里取消默认状态。'
    : ''
);

export const cloneRouteOptions = (options = {}) => structuredClone(toRaw(options));
