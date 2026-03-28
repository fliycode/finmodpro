<script setup>
import { ref, nextTick } from "vue";
import { qaApi } from "../api/qa.js";

const query = ref("");
const messages = ref([{ role: "system", content: "您好，我是您的金融助手。请输入您的问题。" }]);
const isAsking = ref(false);
const messagesContainer = ref(null);

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth'
    });
  }
};

const handleAsk = async () => {
  if (!query.value.trim() || isAsking.value) return;
  messages.value.push({ role: "user", content: query.value });
  const currentQuery = query.value;
  query.value = "";
  isAsking.value = true;
  await scrollToBottom();
  
  try {
    const response = await qaApi.askQuestion(currentQuery);
    messages.value.push({
      role: "assistant",
      content: response.answer,
      citations: response.citations
    });
  } catch (error) {
    messages.value.push({ role: "assistant", content: "（请求失败，请稍后重试）" });
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
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
          <div class="avatar">{{ msg.role === "user" ? "🧑" : "🤖" }}</div>
          <div class="message-content">
            <div class="bubble">{{ msg.content }}</div>
            
            <!-- Citations Block -->
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
                      <span v-if="cite.page_label">页码: {{ cite.page_label }}</span>
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
          <div class="avatar">🤖</div>
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
.chat-window { flex: 1; background: #f8fafc; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06); display: flex; flex-direction: column; overflow: hidden; border: 1px solid #e2e8f0; }
.messages { flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 24px; scroll-behavior: smooth; }
.message { display: flex; gap: 16px; max-width: 85%; }
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.avatar { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 20px; background: white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex-shrink: 0; border: 1px solid #f1f5f9; }
.message-content { display: flex; flex-direction: column; gap: 8px; flex: 1; max-width: 100%; }
.bubble { padding: 14px 18px; border-radius: 16px; line-height: 1.7; word-break: break-word; font-size: 15px; letter-spacing: 0.3px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.assistant .bubble { background: #ffffff; color: #334155; border-top-left-radius: 4px; border: 1px solid #e2e8f0; }
.user .bubble { background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border-top-right-radius: 4px; }

/* Typing Animation */
.typing { display: flex; align-items: center; justify-content: center; gap: 6px; height: 24px; padding: 14px 18px !important; width: fit-content; }
.dot { width: 6px; height: 6px; background-color: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

/* Citations Tag Style */
.citations-container { margin-top: 6px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; max-width: 100%; }
.citations-title { display: flex; align-items: center; gap: 6px; color: #64748b; font-weight: 600; font-size: 12px; }
.icon-small { width: 14px; height: 14px; }
.citations-list.tag-style { display: flex; flex-wrap: wrap; gap: 8px; }
.citation-tag { display: inline-flex; align-items: center; gap: 6px; background: #f1f5f9; border: 1px solid #e2e8f0; padding: 4px 10px; border-radius: 16px; cursor: pointer; color: #475569; transition: all 0.2s; position: relative; }
.citation-tag:hover { background: #e2e8f0; border-color: #cbd5e1; }
.cite-index { color: #6366f1; font-weight: 700; font-size: 11px; }
.cite-title { font-weight: 500; font-size: 12px; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Tooltip Hover */
.tooltip-container .tooltip-content { visibility: hidden; opacity: 0; position: absolute; bottom: 100%; left: 0; margin-bottom: 8px; width: max-content; max-width: 300px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); z-index: 10; transition: all 0.2s; pointer-events: none; display: flex; flex-direction: column; gap: 8px; }
.tooltip-container:hover .tooltip-content { visibility: visible; opacity: 1; transform: translateY(0); }
.tooltip-container .tooltip-content { transform: translateY(4px); }
.cite-meta { display: flex; gap: 12px; color: #64748b; font-size: 11px; flex-wrap: wrap; align-items: center; }
.cite-type { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 10px; text-transform: uppercase; color: #475569; }
.cite-snippet { color: #334155; line-height: 1.5; font-size: 12px; white-space: normal; text-align: left; background: #f8fafc; padding: 8px; border-radius: 6px; border-left: 2px solid #6366f1; }

.input-area { padding: 16px 24px; border-top: 1px solid #e2e8f0; display: flex; gap: 16px; background: white; align-items: flex-end; }
textarea { flex: 1; height: 50px; max-height: 150px; padding: 12px 16px; border: 1px solid #cbd5e1; border-radius: 12px; resize: none; font-family: inherit; transition: all 0.2s; background: #f8fafc; line-height: 1.5; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05); }
textarea:focus { outline: none; border-color: #6366f1; background: white; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1); }
.send-btn { height: 50px; padding: 0 28px; background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 15px; transition: all 0.2s; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2); }
.send-btn:hover:not(:disabled) { box-shadow: 0 4px 6px rgba(99, 102, 241, 0.3); transform: translateY(-1px); }
.send-btn:disabled { opacity: 0.6; cursor: not-allowed; box-shadow: none; transform: none; }
</style>