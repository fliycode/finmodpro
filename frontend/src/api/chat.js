import { createApiConfig, joinUrl } from './config.js';
import { authStorage } from '../lib/auth-storage.js';

const apiConfig = createApiConfig();

const parseResponse = async (response) => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || '请求失败，请稍后重试');
  }
  return data;
};

const getHeaders = () => {
  const token = authStorage.getToken();
  const headers = { ...apiConfig.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const MOCK_HISTORY = [
  { id: 'chat_1', title: '关于2023年财报的分析', lastMessage: '好的，谢谢你的解答。', timestamp: '2024-03-20 10:00' },
  { id: 'chat_2', title: '市场风险评估讨论', lastMessage: '我们需要进一步核实供应链数据。', timestamp: '2024-03-18 15:30' }
];

export const chatApi = {
  // List chat history
  async listHistory() {
    try {
      const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, '/api/v1/chat/history'), {
        method: 'GET',
        headers: getHeaders(),
      });
      const data = await parseResponse(response);
      
      const items = Array.isArray(data) ? data : (data.history || data.sessions || data.data || []);
      return items.map(item => ({
        id: item.id || item.sessionId || item._id || item.session_id,
        title: item.title || item.name || item.topic || '未命名对话',
        lastMessage: item.lastMessage || item.last_message || item.preview || item.last_content || '',
        timestamp: item.timestamp || item.updated_at || item.created_at || item.last_activity || 'N/A'
      }));
    } catch (error) {
      console.warn('chatApi.listHistory failed, using fallback:', error.message);
      return MOCK_HISTORY;
    }
  },
  
  // Get a single chat session
  async getSession(sessionId) {
    try {
      const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/v1/chat/sessions/${sessionId}`), {
        method: 'GET',
        headers: getHeaders(),
      });
      const data = await parseResponse(response);
      
      const rawMessages = data.messages || data.history || data.data || [];
      return {
        id: data.id || data.sessionId || sessionId,
        messages: rawMessages.map(msg => ({
          role: msg.role || (msg.is_user ? 'user' : (msg.is_bot || msg.is_assistant ? 'assistant' : (msg.sender === 'user' ? 'user' : 'assistant'))),
          content: msg.content || msg.text || msg.message || msg.body || ''
        }))
      };
    } catch (error) {
      console.warn('chatApi.getSession failed, using mock data:', error.message);
      return {
        id: sessionId,
        messages: [
          { role: 'assistant', content: '您好，我是您的金融助手，请问有什么可以帮您的？' },
          { role: 'user', content: '我想了解去年的财务增长情况。' },
          { role: 'assistant', content: '好的，根据系统内的2023年度财务报告显示，净利润同比增长了15.2%...' }
        ]
      };
    }
  },

  // Send message to a session
  async sendMessage(sessionId, message) {
    try {
      const response = await apiConfig.fetchImpl(joinUrl(apiConfig.baseURL, `/api/v1/chat/sessions/${sessionId}/messages`), {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ message: message.content || message }),
      });
      const data = await parseResponse(response);
      const res = data.message || data.response || data;
      return {
        role: res.role || 'assistant',
        content: res.content || res.text || res.message || (res.response && res.response.content) || (typeof res === 'string' ? res : '')
      };
    } catch (error) {
      console.warn('chatApi.sendMessage failed, using mock response:', error.message);
      return {
        role: 'assistant',
        content: '这是一个模拟的回复。由于后端连接失败，我目前无法提供实时数据分析，但您可以继续浏览已上传的文档。'
      };
    }
  }
};
