<script setup>
import { computed, ref, nextTick, onMounted, watch } from "vue";
import { useRouter } from 'vue-router';
import { qaApi } from "../api/qa.js";
import { chatApi } from "../api/chat.js";

const props = defineProps({
  sessionId: {
    type: [String, Number],
    default: null
  }
});

const router = useRouter();
const currentSessionId = ref(props.sessionId);
const query = ref("");
const messages = ref([{ role: "system", content: "您好，我是您的金融助手。请输入您的问题。" }]);
const isAsking = ref(false);
const messagesContainer = ref(null);

const getAvatarLabel = (role) => {
  if (role === 'user') return '我';
  if (role === 'assistant') return 'AI';
  return '系';
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
    return '当前未配置可用的对话模型，请联系管理员在“模型配置管理”中启用聊天模型后再试。';
  }

  return message;
};

const pushSystemMessage = (content, tone = 'info') => {
  messages.value.push({ role: 'system', content, tone });
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth'
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
  try {
    const session = await chatApi.getSession(id);
    if (session.messages && session.messages.length > 0) {
      messages.value = [{ role: "system", content: "已加载历史会话...", tone: 'success' }, ...session.messages];
    } else {
      messages.value = [{ role: "system", content: `已加载会话：${session.title || '无标题'}`, tone: 'success' }];
    }
  } catch (error) {
    console.error("加载会话失败:", error);
    messages.value = [{ role: "system", content: "加载会话失败，请刷新页面后重试。", tone: 'error' }];
  }
  await scrollToBottom();
};

watch(() => props.sessionId, (newId) => {
  currentSessionId.value = newId;
  if (newId) {
    loadSession(newId);
  } else {
    messages.value = [{ role: "system", content: "您好，我是您的金融助手。请输入您的问题。", tone: 'info' }];
  }
});

onMounted(() => {
  if (currentSessionId.value) {
    loadSession(currentSessionId.value);
  }
});

const handleAsk = async () => {
  if (!query.value.trim() || isAsking.value) return;

  const currentQuery = query.value;
  query.value = "";

  messages.value.push({ role: "user", content: currentQuery });
  isAsking.value = true;
  await scrollToBottom();

  try {
    if (!currentSessionId.value) {
      try {
        const session = await chatApi.createSession(currentQuery.substring(0, 50));
        if (session?.id) {
          currentSessionId.value = session.id;
          await syncSessionRoute(session.id);
        }
      } catch (err) {
        console.warn("Failed to create session, continuing without session ID:", err);
        pushSystemMessage('会话创建失败，本次回答不会保存到历史记录。', 'warning');
      }
    }

    const response = await qaApi.askQuestion(currentQuery);
    messages.value.push({
      role: "assistant",
      content: response.answer || '未获取到回答，请稍后重试。',
      citations: response.citations,
      duration_ms: response.duration_ms
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
  <div class="qa-shell">
    <div class="chat-window">
      <div class="messages" ref="messagesContainer">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role, msg.tone ? `tone-${msg.tone}` : '']">
          <div :class="getAvatarClass(msg.role)">{{ getAvatarLabel(msg.role) }}</div>
          <div class="message-content">
            <div :class="['bubble', { 'bubble-error': msg.isError }]">
              {{ msg.content }}
              <div v-if="msg.duration_ms" class="duration-info">
                耗时: {{ (msg.duration_ms / 1000).toFixed(2) }}s
              </div>
            </div>

            <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
              <div class="citations-title">
                <svg viewBox="0 0 24 24" fill="none" class="icon-small"><path d="M12 2L2 22h20L12 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
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
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
          </div>
        </div>
      </div>
      <div class="input-area">
        <textarea v-model="query" placeholder="输入您的金融分析问题... (Shift+Enter 换行，Enter 发送)" @keydown.enter.exact.prevent="handleAsk"></textarea>
        <button @click="handleAsk" :disabled="isAsking || !query.trim()" class="send-btn">发送</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qa-shell { height: calc(100vh - 160px); display: flex; flex-direction: column; }
.chat-window { flex: 1; background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 16px; box-shadow: 0 12px 30px -18px rgba(15, 23, 42, 0.35); display: flex; flex-direction: column; overflow: hidden; border: 1px solid #e2e8f0; }
.messages { flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 24px; scroll-behavior: smooth; }
.message { display: flex; gap: 16px; max-width: 85%; }
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.message.system { align-self: center; color: #64748b; font-size: 13px; max-width: min(100%, 720px); }
.message.system .message-content { align-items: center; }
.message.system .bubble { background: #fff; border: 1px solid #dbeafe; box-shadow: none; padding: 10px 14px; color: #475569; border-radius: 999px; }
.message.system .avatar { display: none; }
.message.system.tone-warning .bubble { background: #fff7ed; border-color: #fdba74; color: #9a3412; }
.message.system.tone-error .bubble { background: #fef2f2; border-color: #fca5a5; color: #b91c1c; }
.message.system.tone-success .bubble { background: #ecfdf5; border-color: #86efac; color: #166534; }
.avatar { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; letter-spacing: 0.08em; color: #fff; border-radius: 14px; box-shadow: 0 10px 20px -16px rgba(15, 23, 42, 0.9); flex-shrink: 0; }
.avatar-user { background: linear-gradient(135deg, #6366f1, #4f46e5); }
.avatar-assistant { background: linear-gradient(135deg, #0f172a, #1d4ed8); }
.avatar-system { background: linear-gradient(135deg, #64748b, #475569); }
.message-content { display: flex; flex-direction: column; gap: 8px; flex: 1; max-width: 100%; }
.bubble { padding: 14px 18px; border-radius: 18px; line-height: 1.7; word-break: break-word; font-size: 15px; letter-spacing: 0.2px; box-shadow: 0 10px 30px -24px rgba(15, 23, 42, 0.45); }
.assistant .bubble { background: rgba(255, 255, 255, 0.96); color: #334155; border-top-left-radius: 6px; border: 1px solid #dbe4f0; }
.user .bubble { background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border-top-right-radius: 6px; }
.bubble-error { background: #fff7f7 !important; color: #b91c1c !important; border: 1px solid #fecaca !important; }
.duration-info { font-size: 11px; color: #94a3b8; margin-top: 8px; text-align: right; }
.user .duration-info { display: none; }
.typing { display: flex; align-items: center; justify-content: center; gap: 6px; height: 24px; padding: 14px 18px !important; width: fit-content; }
.dot { width: 6px; height: 6px; background-color: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
.citations-container { margin-top: 6px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; max-width: 100%; }
.citations-title { display: flex; align-items: center; gap: 6px; color: #64748b; font-weight: 600; font-size: 12px; }
.icon-small { width: 14px; height: 14px; }
.citations-list.tag-style { display: flex; flex-wrap: wrap; gap: 8px; }
.citation-tag { display: inline-flex; align-items: center; gap: 6px; background: #f1f5f9; border: 1px solid #e2e8f0; padding: 4px 10px; border-radius: 16px; cursor: pointer; color: #475569; transition: all 0.2s; position: relative; }
.citation-tag:hover { background: #e2e8f0; border-color: #cbd5e1; }
.cite-index { color: #6366f1; font-weight: 700; font-size: 11px; }
.cite-title { font-weight: 500; font-size: 12px; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tooltip-container .tooltip-content { visibility: hidden; opacity: 0; position: absolute; bottom: 100%; left: 0; margin-bottom: 8px; width: max-content; max-width: 300px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); z-index: 10; transition: all 0.2s; pointer-events: none; display: flex; flex-direction: column; gap: 8px; }
.tooltip-container:hover .tooltip-content { visibility: visible; opacity: 1; transform: translateY(0); }
.tooltip-container .tooltip-content { transform: translateY(4px); }
.cite-meta { display: flex; gap: 12px; color: #64748b; font-size: 11px; flex-wrap: wrap; align-items: center; }
.cite-type { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 10px; text-transform: uppercase; color: #475569; }
.cite-snippet { color: #334155; line-height: 1.5; font-size: 12px; white-space: normal; text-align: left; background: #f8fafc; padding: 8px; border-radius: 6px; border-left: 2px solid #6366f1; }
.input-area { padding: 16px 24px; border-top: 1px solid #e2e8f0; display: flex; gap: 16px; background: rgba(255, 255, 255, 0.92); align-items: flex-end; backdrop-filter: blur(10px); }
textarea { flex: 1; height: 50px; max-height: 150px; padding: 12px 16px; border: 1px solid #cbd5e1; border-radius: 12px; resize: none; font-family: inherit; transition: all 0.2s; background: #f8fafc; line-height: 1.5; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05); }
textarea:focus { outline: none; border-color: #6366f1; background: white; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1); }
.send-btn { height: 50px; padding: 0 28px; background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 15px; transition: all 0.2s; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2); }
.send-btn:hover:not(:disabled) { box-shadow: 0 4px 6px rgba(99, 102, 241, 0.3); transform: translateY(-1px); }
.send-btn:disabled { opacity: 0.6; cursor: not-allowed; box-shadow: none; transform: none; }
</style>
