<script setup>
import { computed, onMounted, ref } from 'vue';
import { dashboardApi } from '../../api/dashboard.js';
import OpsSectionFrame from '../../components/admin/ops/OpsSectionFrame.vue';
import AppIcon from '../../components/ui/AppIcon.vue';

const audits = ref([]);
const isLoading = ref(false);
const errorMsg = ref('');
const currentPage = ref(1);
const pageSize = ref(10);
const total = ref(0);
const searchQuery = ref('');
const searchInput = ref('');

const actionLabels = {
  'knowledgebase.ingest': '知识入库',
  'risk.extract': '风险提取',
  'risk.extract.retry': '重试风险提取',
  'risk.batch_extract': '批量风险提取',
  'risk.batch_extract.retry': '重试批量提取',
  'risk.sentiment': '舆情分析',
};
const formatAction = (action) => actionLabels[action] || action || '--';

const actionTones = {
  'knowledgebase.ingest': 'brand',
  'risk.extract': 'risk',
  'risk.extract.retry': 'risk',
  'risk.batch_extract': 'risk',
  'risk.batch_extract.retry': 'risk',
  'risk.sentiment': 'accent',
};

const statusLabels = { succeeded: '成功', failed: '失败', pending: '待处理', retried: '已重试' };

const stats = computed(() => {
  const failed = audits.value.filter((i) => i.status === 'failed').length;
  const actors = new Set(audits.value.map((i) => i.actor_name).filter(Boolean)).size;
  return { total: total.value || audits.value.length, failed, actors };
});

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = { page: currentPage.value, page_size: pageSize.value };
    if (searchQuery.value) params.search = searchQuery.value;
    const data = await dashboardApi.getAudits(params);
    audits.value = data.results || data.audits || [];
    total.value = data.total || 0;
  } catch (err) {
    errorMsg.value = err.message || '加载操作日志失败';
  } finally {
    isLoading.value = false;
  }
};

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));

const onSearch = () => {
  searchQuery.value = searchInput.value.trim();
  currentPage.value = 1;
  fetchData();
};

const goToPage = (page) => {
  if (page < 1 || page > totalPages.value) return;
  currentPage.value = page;
  fetchData();
};

const pad = (n) => String(n).padStart(2, '0');
const formatTime = (iso) => {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return iso;
  }
};

onMounted(fetchData);
</script>

<template>
  <OpsSectionFrame>
    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <!-- Stats strip -->
    <div class="audit-stats">
      <div class="audit-stat">
        <span class="audit-stat__label">操作记录</span>
        <strong class="audit-stat__num">{{ stats.total }}</strong>
      </div>
      <div class="audit-stat" :class="{ 'has-risk': stats.failed > 0 }">
        <span class="audit-stat__label">失败记录</span>
        <strong class="audit-stat__num">{{ stats.failed }}</strong>
      </div>
      <div class="audit-stat">
        <span class="audit-stat__label">操作人员</span>
        <strong class="audit-stat__num">{{ stats.actors }}</strong>
      </div>
    </div>

    <!-- Table card -->
    <section class="audit-card">
      <header class="audit-card__head">
        <div class="audit-search">
          <AppIcon name="search" :size="14" class="audit-search__icon" aria-hidden="true" />
          <input
            v-model="searchInput"
            type="text"
            class="audit-search__input"
            placeholder="搜索操作人或操作..."
            @keydown.enter="onSearch"
          />
        </div>
        <div class="audit-pagination">
          <button class="audit-page-btn" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)" aria-label="上一页">&lsaquo;</button>
          <span class="audit-page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button class="audit-page-btn" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)" aria-label="下一页">&rsaquo;</button>
        </div>
      </header>

      <div v-if="isLoading" class="audit-loading">加载中...</div>
      <div v-else-if="audits.length === 0" class="audit-empty">暂无操作记录</div>

      <table v-else class="audit-table">
        <thead>
          <tr>
            <th class="audit-th audit-th--id">ID</th>
            <th class="audit-th">操作人</th>
            <th class="audit-th">操作</th>
            <th class="audit-th">目标类型</th>
            <th class="audit-th">状态</th>
            <th class="audit-th audit-th--time">时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in audits" :key="row.id" class="audit-row">
            <td class="audit-td audit-td--id">{{ row.id }}</td>
            <td class="audit-td audit-td--actor">{{ row.actor_name || '--' }}</td>
            <td class="audit-td">
              <span class="audit-action-badge" :class="`is-${actionTones[row.action] || 'neutral'}`">{{ formatAction(row.action) }}</span>
            </td>
            <td class="audit-td audit-td--muted">{{ row.target_type || '--' }}</td>
            <td class="audit-td">
              <span class="audit-status-badge" :class="`is-${row.status}`">{{ statusLabels[row.status] || row.status }}</span>
            </td>
            <td class="audit-td audit-td--time">{{ formatTime(row.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </OpsSectionFrame>
</template>

<style scoped>
/* ---- Stats Strip ---- */

.audit-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.audit-stat {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  padding: 14px 16px;
}

.audit-stat__label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.audit-stat__num {
  display: block;
  margin-top: 4px;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1;
}

.audit-stat.has-risk .audit-stat__num {
  color: var(--risk-red, #c4493d);
}

/* ---- Table Card ---- */

.audit-card {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  overflow: hidden;
}

.audit-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-soft);
}

/* ---- Search ---- */

.audit-search {
  position: relative;
  flex: 1;
  max-width: 280px;
}

.audit-search__icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.audit-search__input {
  width: 100%;
  height: 32px;
  padding: 0 10px 0 30px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-3);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.audit-search__input::placeholder {
  color: var(--text-muted);
}

.audit-search__input:focus {
  border-color: var(--brand, #2457c5);
}

/* ---- Pagination ---- */

.audit-pagination {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.audit-page-btn {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}

.audit-page-btn:hover:not(:disabled) {
  border-color: var(--brand, #2457c5);
  color: var(--text-primary);
}

.audit-page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.audit-page-info {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 40px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

/* ---- Table ---- */

.audit-table {
  width: 100%;
  border-collapse: collapse;
}

.audit-th {
  padding: 8px 16px;
  text-align: left;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--surface-3);
  border-bottom: 1px solid var(--line-soft);
}

.audit-th--id { width: 64px; }
.audit-th--time { width: 170px; }

.audit-row {
  transition: background 0.15s;
}

.audit-row:hover {
  background: var(--surface-hover);
}

.audit-td {
  padding: 10px 16px;
  font-size: 12px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--line-soft);
}

.audit-td--id {
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  font-size: 11px;
}

.audit-td--actor {
  font-weight: 600;
}

.audit-td--muted {
  color: var(--text-secondary);
}

.audit-td--time {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* ---- Badges ---- */

.audit-action-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-3);
  color: var(--text-secondary);
}

.audit-action-badge.is-brand {
  background: rgba(36, 87, 197, 0.1);
  color: #5b8af5;
}

.audit-action-badge.is-risk {
  background: rgba(196, 73, 61, 0.1);
  color: #e07060;
}

.audit-action-badge.is-accent {
  background: rgba(91, 108, 255, 0.1);
  color: #7d8cff;
}

.audit-status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.audit-status-badge.is-succeeded {
  background: rgba(33, 129, 92, 0.1);
  color: #3aab7a;
}

.audit-status-badge.is-failed {
  background: rgba(196, 73, 61, 0.1);
  color: #e07060;
}

.audit-status-badge.is-pending {
  background: rgba(183, 121, 31, 0.1);
  color: #c9922a;
}

.audit-status-badge.is-retried {
  background: rgba(91, 108, 255, 0.1);
  color: #7d8cff;
}

/* ---- States ---- */

.audit-loading,
.audit-empty {
  padding: 40px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- Responsive ---- */

@media (max-width: 720px) {
  .audit-stats {
    grid-template-columns: 1fr;
  }

  .audit-card__head {
    flex-direction: column;
    align-items: stretch;
  }

  .audit-search {
    max-width: none;
  }

  .audit-table {
    display: block;
    overflow-x: auto;
  }
}
</style>
