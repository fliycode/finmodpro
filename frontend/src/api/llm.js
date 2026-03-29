import { createApiConfig, joinUrl } from "./config.js";
import { authStorage } from "../lib/auth-storage.js";

const apiConfig = createApiConfig();

const getHeaders = () => {
  const token = authStorage.getToken();
  const headers = { ...apiConfig.headers };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || data.error || "请求失败");
  }
  // 处理后端统一包裹 { code, message, data } 的情况
  if (data && data.data !== undefined && data.code !== undefined) {
    if (data.code !== 0 && data.code !== 200 && data.code !== 201) {
      throw new Error(data.message || "操作失败");
    }
    return data.data;
  }
  return data;
};

export const llmApi = {
  // 模型配置
  async getModelConfigs() {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, "/api/ops/model-configs/"), {
      method: "GET",
      headers: getHeaders(),
    });
    return parseResponse(response);
  },

  async activateModelConfig(id, isActive) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/ops/model-configs/${id}/activation/`), {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ is_active: isActive }),
    });
    return parseResponse(response);
  },

  // 评测任务
  async getEvaluations() {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, "/api/ops/evaluations"), {
      method: "GET",
      headers: getHeaders(),
    });
    return parseResponse(response);
  },

  async triggerEvaluation(data) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, "/api/ops/evaluations"), {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    return parseResponse(response);
  }
};
