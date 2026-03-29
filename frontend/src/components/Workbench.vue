<script setup>
import { ref } from "vue";
import KnowledgeBase from "./KnowledgeBase.vue";
import FinancialQA from "./FinancialQA.vue";
import ChatHistory from "./ChatHistory.vue";
import RiskSummary from "./RiskSummary.vue";
import OpsDashboard from "./OpsDashboard.vue";
import ModelConfig from "./ModelConfig.vue";
import EvaluationResult from "./EvaluationResult.vue";

const props = defineProps({
  user: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(["back"]);

const activeTab = ref("qa");
const currentSessionId = ref(null);

const handleOpenSession = (sessionId) => {
  currentSessionId.value = sessionId;
  activeTab.value = "qa";
};

const handleNewSession = () => {
  currentSessionId.value = null;
  activeTab.value = "qa";
};

const tabs = [
  { id: "qa", label: "金融问答", icon: "💬" },
  { id: "knowledge", label: "知识库管理", icon: "📚" },
  { id: "history", label: "历史会话", icon: "🕒" },
  { id: "risk", label: "风险与摘要", icon: "📊" },
  { id: "ops", label: "工作台大盘", icon: "📈", adminOnly: true },
  { id: "model-config", label: "模型配置", icon: "🧠", adminOnly: true },
  { id: "eval-result", label: "评测结果", icon: "⚖️", adminOnly: true }
];

const availableTabs = tabs.filter(tab => !tab.adminOnly || props.user.permissions.includes("admin") || props.user.groups.includes("admin") || props.user.groups.includes("super_admin"));

</script>

<template>
  <div class="workbench-container">
    <aside class="sidebar">
      <div class="brand">
        <h3>FinModPro 工作台</h3>
      </div>
      <nav class="nav-menu">
        <button 
          v-for="tab in availableTabs" 
          :key="tab.id"
          :class="['nav-item', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          <span class="icon">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
      </nav>
      <div class="sidebar-footer">
        <div class="user-info">
          <span class="avatar">👤</span>
          <span class="username">{{ user.user?.username || "用户" }}</span>
        </div>
        <button @click="emit('back')" class="exit-btn">返回主页</button>
      </div>
    </aside>

    <main class="main-content">
      <header class="content-header">
        <h2>{{ tabs.find(t => t.id === activeTab)?.label }}</h2>
      </header>
      <div class="content-body">
        <FinancialQA v-if="activeTab === 'qa'" :session-id="currentSessionId" />
        <KnowledgeBase v-else-if="activeTab === 'knowledge'" />
        <ChatHistory v-else-if="activeTab === 'history'" @open-session="handleOpenSession" />
        <RiskSummary v-else-if="activeTab === 'risk'" />
        <OpsDashboard v-else-if="activeTab === 'ops'" />
        <ModelConfig v-else-if="activeTab === 'model-config'" />
        <EvaluationResult v-else-if="activeTab === 'eval-result'" />
      </div>
    </main>
  </div>
</template>

<style scoped>
.workbench-container { display: flex; height: 100vh; background-color: #f8fafc; }
.sidebar { width: 260px; background: white; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; }
.brand { padding: 24px; border-bottom: 1px solid #e2e8f0; color: #6366f1; }
.brand h3 { margin: 0; font-size: 18px; }
.nav-menu { flex: 1; padding: 16px 12px; display: flex; flex-direction: column; gap: 8px; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: none; background: transparent; border-radius: 8px; cursor: pointer; font-size: 15px; color: #475569; transition: all 0.2s; text-align: left; }
.nav-item:hover { background: #f1f5f9; }
.nav-item.active { background: #e0e7ff; color: #4338ca; font-weight: 600; }
.sidebar-footer { padding: 16px; border-top: 1px solid #e2e8f0; }
.user-info { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 14px; color: #1e293b; font-weight: 500; }
.exit-btn { width: 100%; padding: 8px; background: transparent; border: 1px solid #cbd5e1; border-radius: 6px; cursor: pointer; color: #64748b; }
.exit-btn:hover { background: #f1f5f9; }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.content-header { height: 64px; background: white; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; padding: 0 32px; }
.content-header h2 { margin: 0; font-size: 20px; color: #1e293b; }
.content-body { flex: 1; padding: 32px; overflow-y: auto; }
</style>
