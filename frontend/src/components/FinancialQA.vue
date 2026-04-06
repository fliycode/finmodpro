<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { chatApi } from '../api/chat.js';
import { qaApi } from '../api/qa.js';

const props = defineProps({
  sessionId: {
    type: [String, Number],
    default: null,
  },
});

const router = useRouter();
const currentSessionId = ref(props.sessionId);
const query = ref('');
const messages = ref([{ role: 'system', content: '您好，我是您的金融助手。请输入您的问题。', tone: 'info' }]);
const isAsking = ref(false);
const messagesContainer = ref(null);
const sessionOptions = ref([]);
const isLoadingSessions = ref(false);
const isHydratingSession = ref(false);

const getAvatarLabel = (role) => {
  if (role === 'user') return '我';
  if (role === 'assistant') return 'AI';
  return '系统';
};

const getAvatarClass = (role) => ({
  avatar: true,
  [`avatar-${role}`]: true,
});

const getFriendlyErrorMessage = (error) => {
  const message = String(error?.message || '').trim();

  if (!message) {
    return '请求失败，请稍后重试。';
  }

  if (/当前未配置可用的对话模型|模型|llm|未启用|未配置/i.test(message)) {
    return '当前未配置可用的对话模型，请联系管理员在模型配置中启用聊天模型后再试。';
  }

  return message;
};

const pushSystemMessage = (content, tone = 'info') => {
  messages.value.push({ role: 'system', content, tone });
};

const refreshSessionOptions = async () => {
  isLoadingSessions.value = true;
  try {
    sessionOptions.value = await chatApi.listHistory();
  } catch (error) {
    console.error('加载会话列表失败:', error);
  } finally {
    isLoadingSessions.value = false;
  }
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth',
    });
  }
};

const syncSessionRoute = async (sessionId) => {
  if (!sessionId || router.currentRoute.value.query.session === String(sessionId)) {
    return;
  }

  await router.replace({
    query: {
      ...router.currentRoute.value.query,
      session: String(sessionId),
    },
  });
};

const loadSession = async (id) => {
  if (!id) return;
  isHydratingSession.value = true;

  try {
    const session = await chatApi.getSession(id);
    if (session.messages && session.messages.length > 0) {
      messages.value = session.messages;
    } else {
      messages.value = [{ role: 'system', content: `已加载会话：${session.title || '未命名会话'}`, tone: 'success' }];
    }
  } catch (error) {
    console.error('加载会话失败:', error);
    messages.value = [{ role: 'system', content: '加载会话失败，请刷新页面后重试。', tone: 'error' }];
  } finally {
    isHydratingSession.value = false;
  }

  await scrollToBottom();
};

watch(() => props.sessionId, (newId) => {
  currentSessionId.value = newId;
  if (newId && !isHydratingSession.value && !isAsking.value) {
    loadSession(newId);
  } else if (!newId) {
    messages.value = [{ role: 'system', content: '您好，我是您的金融助手。请输入您的问题。', tone: 'info' }];
  }
});

onMounted(async () => {
  await refreshSessionOptions();
  if (currentSessionId.value) {
    loadSession(currentSessionId.value);
  }
});

const handleSessionChange = async (event) => {
  const nextId = event.target.value;
  currentSessionId.value = nextId || null;

  if (nextId) {
    await syncSessionRoute(nextId);
    await loadSession(nextId);
    return;
  }

  const nextQuery = { ...router.currentRoute.value.query };
  delete nextQuery.session;
  await router.replace({ query: nextQuery });
  messages.value = [{ role: 'system', content: '您好，我是您的金融助手。请输入您的问题。', tone: 'info' }];
};

const handleAsk = async () => {
  if (!query.value.trim() || isAsking.value) return;

  const currentQuery = query.value;
  query.value = '';

  messages.value.push({ role: 'user', content: currentQuery });
  isAsking.value = true;
  await scrollToBottom();

  try {
    if (!currentSessionId.value) {
      try {
        const session = await chatApi.createSession(currentQuery.substring(0, 50));
        if (session?.id) {
          currentSessionId.value = session.id;
          await refreshSessionOptions();
          await syncSessionRoute(session.id);
        }
      } catch (error) {
        console.warn('Failed to create session, continuing without session ID:', error);
        pushSystemMessage('会话创建失败，本次回答不会保存到历史记录。', 'warning');
      }
    }

    const response = await qaApi.askQuestion(currentQuery);
    messages.value.push({
      role: 'assistant',
      content: response.answer || '未获取到回答，请稍后重试。',
      citations: response.citations,
      answer_mode: response.answer_mode,
      answer_notice: response.answer_notice,
      duration_ms: response.duration_ms,
    });
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: getFriendlyErrorMessage(error),
      isError: true,
    });
  } finally {
    isAsking.value = false;
    await scrollToBottom();
  }
};
</script>

<template>
  <div class="page-stack qa-page">
    <div class="qa-toolbar ui-card">
      <div class="qa-toolbar__controls">
        <label class="qa-toolbar__session-picker">
          <span>历史会话</span>
          <select
            :value="currentSessionId || ''"
            :disabled="isLoadingSessions || isAsking"
            @change="handleSessionChange"
          >
            <option value="">新对话</option>
            <option v-for="session in sessionOptions" :key="session.id" :value="session.id">
              {{ session.title }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <div class="chat-window ui-card">
      <div ref="messagesContainer" class="messages">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role, msg.tone ? `tone-${msg.tone}` : '']">
          <div :class="getAvatarClass(msg.role)">{{ getAvatarLabel(msg.role) }}</div>
          <div class="message-content">
            <div :class="['bubble', { 'bubble-error': msg.isError }]">
              {{ msg.content }}
              <div v-if="msg.duration_ms" class="duration-info">
                耗时: {{ (msg.duration_ms / 1000).toFixed(2) }}s
              </div>
              <div v-if="msg.answer_notice" class="answer-notice">
                {{ msg.answer_notice }}
              </div>
            </div>

            <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
              <div class="citations-title">
                <svg viewBox="0 0 24 24" fill="none" class="icon-small">
                  <path d="M12 2L2 22h20L12 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                </svg>
                参考来源
              </div>
              <div class="citations-list tag-style">
                <div v-for="(cite, i) in msg.citations" :key="i" class="citation-tag tooltip-container">
                  <span class="cite-index">[{{ i + 1 }}]</span>
                  <span class="cite-title">{{ cite.document_title }}</span>
                  <div class="tooltip-content">
                    <div class="cite-meta">
                      <span class="cite-type">{{ cite.doc_type }}</span>
                      <span v-if="cite.page_label && cite.page_label !== 'N/A'">页码: {{ cite.page_label }}</span>
                      <span v-if="cite.score > 0">相关度: {{ (cite.score * 100).toFixed(0) }}%</span>
                    </div>
                    <div class="cite-snippet">"{{ cite.snippet }}"</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isAsking" class="message assistant">
          <div :class="getAvatarClass('assistant')">AI</div>
          <div class="message-content">
            <div class="bubble typing">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <textarea
          v-model="query"
          placeholder="输入您的金融分析问题...（Shift+Enter 换行，Enter 发送）"
          @keydown.enter.exact.prevent="handleAsk"
        />
        <button @click="handleAsk" :disabled="isAsking || !query.trim()" class="send-btn">发送</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qa-page {
  min-height: calc(100vh - 180px);
}

.qa-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 18px 22px;
}

.qa-toolbar__controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.qa-toolbar__session-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #5a677d;
  font-weight: 600;
}

.qa-toolbar__session-picker select {
  min-width: 240px;
  height: 42px;
  border-radius: 12px;
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  padding: 0 12px;
  color: #142033;
}

.chat-window {
  flex: 1;
  min-height: calc(100vh - 360px);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(243, 245, 247, 0.95) 100%);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages {
  flex: 1;
  padding: 28px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
  scroll-behavior: smooth;
}

.message {
  display: flex;
  gap: 14px;
  max-width: min(86%, 920px);
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.system {
  align-self: center;
  color: #5a677d;
  font-size: 13px;
  max-width: min(100%, 720px);
}

.message.system .message-content {
  align-items: center;
}

.message.system .bubble {
  background: #fff;
  border: 1px solid rgba(36, 87, 197, 0.12);
  box-shadow: none;
  padding: 10px 14px;
  color: #475569;
  border-radius: 999px;
}

.message.system .avatar {
  display: none;
}

.message.system.tone-warning .bubble {
  background: #fff7ed;
  border-color: #fdba74;
  color: #9a3412;
}

.message.system.tone-error .bubble {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

.message.system.tone-success .bubble {
  background: #ecfdf5;
  border-color: #86efac;
  color: #166534;
}

.avatar {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  border-radius: 14px;
  box-shadow: 0 10px 20px -16px rgba(15, 23, 42, 0.9);
  flex-shrink: 0;
}

.avatar-user {
  background: linear-gradient(135deg, #2457c5, #1d469d);
}

.avatar-assistant {
  background: linear-gradient(135deg, #142033, #2457c5);
}

.avatar-system {
  background: linear-gradient(135deg, #64748b, #475569);
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  max-width: 100%;
}

.bubble {
  padding: 13px 16px;
  border-radius: 18px;
  line-height: 1.68;
  word-break: break-word;
  font-size: 14px;
  letter-spacing: 0.15px;
  box-shadow: 0 10px 30px -24px rgba(15, 23, 42, 0.45);
}

.assistant .bubble {
  background: rgba(255, 255, 255, 0.98);
  color: #334155;
  border-top-left-radius: 6px;
  border: 1px solid #dbe4f0;
}

.user .bubble {
  background: linear-gradient(135deg, #2457c5, #1d469d);
  color: #fff;
  border-top-right-radius: 6px;
}

.bubble-error {
  background: #fff7f7 !important;
  color: #b91c1c !important;
  border: 1px solid #fecaca !important;
}

.duration-info {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 8px;
  text-align: right;
}

.answer-notice {
  margin-top: 8px;
  font-size: 12px;
  color: #8a6a12;
  background: #fff8e6;
  border: 1px solid #f6d68a;
  border-radius: 10px;
  padding: 8px 10px;
}

.user .duration-info {
  display: none;
}

.typing {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 24px;
  padding: 14px 18px !important;
  width: fit-content;
}

.dot {
  width: 6px;
  height: 6px;
  background-color: #94a3b8;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

.citations-container {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  max-width: 100%;
}

.citations-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
}

.icon-small {
  width: 14px;
  height: 14px;
}

.citations-list.tag-style {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.citation-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 4px 10px;
  border-radius: 16px;
  cursor: pointer;
  color: #475569;
  transition: all 0.2s;
  position: relative;
}

.citation-tag:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.cite-index {
  color: #2457c5;
  font-weight: 700;
  font-size: 11px;
}

.cite-title {
  font-weight: 500;
  font-size: 12px;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tooltip-container .tooltip-content {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  width: max-content;
  max-width: 300px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  z-index: 10;
  transition: all 0.2s;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transform: translateY(4px);
}

.tooltip-container:hover .tooltip-content {
  visibility: visible;
  opacity: 1;
  transform: translateY(0);
}

.cite-meta {
  display: flex;
  gap: 12px;
  color: #64748b;
  font-size: 11px;
  flex-wrap: wrap;
  align-items: center;
}

.cite-type {
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  text-transform: uppercase;
  color: #475569;
}

.cite-snippet {
  color: #334155;
  line-height: 1.5;
  font-size: 12px;
  white-space: normal;
  text-align: left;
  background: #f8fafc;
  padding: 8px;
  border-radius: 6px;
  border-left: 2px solid #2457c5;
}

.input-area {
  padding: 18px 24px 22px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 14px;
  background: rgba(255, 255, 255, 0.96);
  align-items: flex-end;
}

textarea {
  flex: 1;
  height: 52px;
  max-height: 150px;
  padding: 13px 16px;
  border: 1px solid #cbd5e1;
  border-radius: 14px;
  resize: none;
  font-family: inherit;
  transition: all 0.2s;
  background: #f8fafc;
  line-height: 1.55;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

textarea:focus {
  outline: none;
  border-color: #2457c5;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(36, 87, 197, 0.1);
}

.send-btn {
  height: 52px;
  padding: 0 24px;
  background: linear-gradient(135deg, #2457c5, #1d469d);
  color: #fff;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  font-weight: 700;
  font-size: 14px;
  transition: all 0.2s;
  box-shadow: 0 8px 20px -16px rgba(36, 87, 197, 0.58);
}

.send-btn:hover:not(:disabled) {
  box-shadow: 0 10px 24px -16px rgba(36, 87, 197, 0.7);
  transform: translateY(-1px);
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}
</style>
