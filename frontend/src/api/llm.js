import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const apiConfig = createApiConfig();

const getHeaders = () => {
  const token = authStorage.getToken();
  const headers = { ...apiConfig.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const llmApi = {
  async getModelConfigs() {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/llm/model-configs/'), {
      method: 'GET',
      headers: getHeaders(),
    });
    if (!response.ok) {
      throw new Error('获取模型配置失败');
    }
    return await response.json();
  },

  async activateModelConfig(id, isActive) {
    const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/llm/model-configs/${id}/activation/`), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ is_active: isActive }),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || '切换模型状态失败');
    }
    return await response.json();
  }
};
