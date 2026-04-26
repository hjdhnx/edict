<template>
  <div class="panel-grid officials-panel">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">完成任务</div><div class="kpi-value">{{ data?.totals.tasks_done || 0 }}</div><div class="kpi-hint">累计完成</div></div>
      <div class="kpi-card"><div class="kpi-label">总成本</div><div class="kpi-value">¥{{ (data?.totals.cost_cny || 0).toFixed(2) }}</div><div class="kpi-hint">估算消耗</div></div>
      <div class="kpi-card"><div class="kpi-label">首席功臣</div><div class="kpi-value" style="font-size: 22px">{{ data?.top_official || '-' }}</div><div class="kpi-hint">按功绩排名</div></div>
      <div class="kpi-card"><div class="kpi-label">官员数</div><div class="kpi-value">{{ data?.officials.length || 0 }}</div><div class="kpi-hint">纳入统计</div></div>
    </div>

    <a-card v-if="activeOfficials.length" class="surface-card" :bordered="false" title="当前活跃官员">
      <div class="wrap-row">
        <a-tag v-for="official in activeOfficials" :key="official.id" color="success">{{ official.emoji }} {{ official.label }} · {{ official.heartbeat.label }}</a-tag>
      </div>
    </a-card>

    <div class="two-col">
      <a-card class="surface-card" :bordered="false" title="功绩榜">
        <a-list :data-source="data?.officials || []">
          <template #renderItem="{ item }">
            <a-list-item :class="['official-row', { selected: selected?.id === item.id }]" @click="store.selectedOfficial = item.id">
              <a-list-item-meta :title="`${item.emoji} ${item.label}`" :description="`${item.role} · 功绩 ${item.merit_score}`" />
              <a-tag :color="item.heartbeat.status === 'active' ? 'success' : 'default'">{{ item.heartbeat.label }}</a-tag>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
      <a-card class="surface-card" :bordered="false" title="官员详情">
        <template v-if="selected">
          <div class="wrap-row"><span style="font-size: 30px">{{ selected.emoji }}</span><div><h2>{{ selected.label }}</h2><div class="muted">{{ selected.role }} · {{ selected.rank }}</div></div></div>
          <div class="wrap-row" style="margin-top: 10px">
            <a-tag :color="selected.heartbeat.status === 'active' ? 'success' : 'default'">{{ selected.heartbeat.label }}</a-tag>
            <a-tag>功绩 {{ selected.merit_score }} · 第 {{ selected.merit_rank }} 名</a-tag>
          </div>
          <a-descriptions style="margin-top: 10px" :column="1" size="small">
            <a-descriptions-item label="模型">{{ selected.model_short || selected.model }}</a-descriptions-item>
            <a-descriptions-item label="会话/消息">{{ selected.sessions }} / {{ selected.messages }}</a-descriptions-item>
            <a-descriptions-item label="完成/活跃任务">{{ selected.tasks_done }} / {{ selected.tasks_active }}</a-descriptions-item>
            <a-descriptions-item label="流转参与">{{ selected.flow_participations }}</a-descriptions-item>
            <a-descriptions-item label="Token 输入/输出">{{ selected.tokens_in }} / {{ selected.tokens_out }}</a-descriptions-item>
            <a-descriptions-item label="缓存读/写">{{ selected.cache_read }} / {{ selected.cache_write }}</a-descriptions-item>
            <a-descriptions-item label="总 Token">{{ totalTokens }}</a-descriptions-item>
            <a-descriptions-item label="成本">¥{{ selected.cost_cny.toFixed(4) }} / ${{ selected.cost_usd.toFixed(4) }}</a-descriptions-item>
            <a-descriptions-item label="最近活跃">{{ formatDashboardDateTime(selected.last_active) || '-' }}</a-descriptions-item>
          </a-descriptions>
          <div class="token-bars">
            <a-progress :percent="tokenPercent(selected.tokens_in)" size="small" status="active" />
            <a-progress :percent="tokenPercent(selected.tokens_out)" size="small" />
          </div>
          <a-list size="small" :data-source="selected.participated_edicts || []">
            <template #renderItem="{ item }"><a-list-item @click="store.modalTaskId = item.id" style="cursor: pointer">{{ item.id }} · {{ item.title }} <a-tag>{{ item.state }}</a-tag></a-list-item></template>
          </a-list>
        </template>
        <a-empty v-else description="选择左侧官员查看详情" />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { formatDashboardDateTime } from '../time';
import { useDashboardStore } from '../stores/dashboard';
const store = useDashboardStore();
onMounted(() => store.loadOfficials());
const data = computed(() => store.officialsData);
const selected = computed(() => data.value?.officials.find((o) => o.id === store.selectedOfficial) || data.value?.officials[0]);
const activeOfficials = computed(() => (data.value?.officials || []).filter((official) => official.heartbeat.status === 'active'));
const totalTokens = computed(() => selected.value ? selected.value.tokens_in + selected.value.tokens_out + selected.value.cache_read + selected.value.cache_write : 0);
function tokenPercent(value: number) { return totalTokens.value ? Math.round(value / totalTokens.value * 100) : 0; }
</script>

<style scoped>
.official-row {
  cursor: pointer;
  border-radius: 10px;
  min-width: 0;
}

.official-row.selected,
.official-row:hover {
  background: var(--app-surface-strong);
}

.token-bars {
  display: grid;
  gap: 6px;
  margin: 8px 0;
}
</style>
