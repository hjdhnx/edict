<template>
  <div class="panel-grid monitor-panel">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">Gateway</div><div class="kpi-value">{{ gatewayLabel }}</div><div class="kpi-hint">{{ data?.gateway?.status || (data?.checkedAt ? formatDashboardDateTime(data.checkedAt) : '等待检测') }}</div></div>
      <div class="kpi-card"><div class="kpi-label">运行中</div><div class="kpi-value">{{ byStatus.running }}</div><div class="kpi-hint">可接收任务</div></div>
      <div class="kpi-card"><div class="kpi-label">空闲</div><div class="kpi-value">{{ byStatus.idle }}</div><div class="kpi-hint">可唤醒</div></div>
      <div class="kpi-card"><div class="kpi-label">离线/未配置</div><div class="kpi-value">{{ byStatus.offline + byStatus.unconfigured }}</div><div class="kpi-hint">需要检查 AstrBot</div></div>
    </div>
    <div class="row-between">
      <h2>省部运行状态</h2>
      <a-space><a-button @click="store.loadAgentsStatus">刷新状态</a-button><a-button v-if="wakeableAgents.length" type="primary" :disabled="!gatewayAlive" @click="wakeIdle">唤醒空闲 Agent</a-button></a-space>
    </div>
    <div class="card-list">
      <a-card v-for="agent in visibleAgents" :key="agent.id" class="surface-card" :bordered="false">
        <div class="row-between">
          <div class="wrap-row"><span style="font-size: 24px">{{ agent.emoji }}</span><div><b>{{ agent.label }}</b><div class="muted">{{ agent.role }} · {{ agent.id }}</div></div></div>
          <a-tag :color="statusColor(agent.status)">{{ agent.statusLabel }}</a-tag>
        </div>
        <div class="muted" style="margin-top: 8px">最近活跃：{{ agent.lastActive ? formatDashboardDateTime(agent.lastActive) : '暂无' }}</div>
        <a-button style="margin-top: 8px" size="small" :disabled="!canWake(agent)" @click="wake(agent.id)">唤醒</a-button>
      </a-card>
    </div>

    <a-card class="surface-card" :bordered="false" title="六部值守任务">
      <div class="duty-grid">
        <div v-for="dept in DEPTS" :key="dept.id" class="duty-card">
          <div class="row-between">
            <div class="wrap-row"><span class="dept-emoji">{{ dept.emoji }}</span><div><b>{{ dept.label }}</b><div class="muted">{{ dept.role }} · {{ dept.rank }}</div></div></div>
            <a-tag :color="deptTasks(dept).blocked.length ? 'error' : deptTasks(dept).active.length ? 'processing' : 'default'">{{ deptTasks(dept).active.length }} 活跃</a-tag>
          </div>
          <div class="muted duty-model">模型：{{ officialModel(dept.id) || '-' }} · 最近活跃：{{ officialLastActive(dept.id) || '-' }}</div>
          <div v-if="deptTasks(dept).active.length" class="duty-task-list">
            <div v-for="task in deptTasks(dept).active.slice(0, 3)" :key="task.id" class="duty-task" @click="store.modalTaskId = task.id">
              <span>{{ task.id }}</span>
              <b>{{ task.title }}</b>
              <a-tag v-if="task.block" color="error">{{ task.block }}</a-tag>
            </div>
          </div>
          <a-empty v-else description="暂无活跃任务" />
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { api, type AgentStatusInfo, type Task } from '../api';
import { formatDashboardDateTime } from '../time';
import { DEPTS, isArchived, isEdict, useDashboardStore } from '../stores/dashboard';
const store = useDashboardStore();
onMounted(() => { store.loadAgentsStatus(); store.loadOfficials(); });
const data = computed(() => store.agentsStatusData);
const gatewayAlive = computed(() => !!data.value?.gateway?.alive);
const gatewayLabel = computed(() => data.value?.gateway?.alive ? '在线' : data.value ? '异常' : '检测中');
const visibleAgents = computed(() => (data.value?.agents || []).filter((agent) => agent.id !== 'main'));
const byStatus = computed(() => {
  const base = { running: 0, idle: 0, offline: 0, unconfigured: 0 };
  for (const agent of visibleAgents.value) base[agent.status] += 1;
  return base;
});
const wakeableAgents = computed(() => visibleAgents.value.filter(canWake));
function statusColor(status: string) { return status === 'running' ? 'success' : status === 'idle' ? 'processing' : status === 'offline' ? 'error' : 'default'; }
function canWake(agent: AgentStatusInfo) { return gatewayAlive.value && !['running', 'unconfigured'].includes(agent.status); }
async function wake(agentId: string) { const r = await api.agentWake(agentId); store.toast(r.ok ? '唤醒请求已发送' : r.error || '唤醒失败', r.ok ? 'ok' : 'err'); store.loadAgentsStatus(); }
async function wakeIdle() { for (const agent of wakeableAgents.value) await api.agentWake(agent.id); store.toast('批量唤醒已发送', 'ok'); store.loadAgentsStatus(); }
function deptTasks(dept: typeof DEPTS[number]) {
  const active = store.tasks.filter((task) => isEdict(task) && !isArchived(task) && !['Done', 'Next', 'Cancelled'].includes(task.state) && (task.org === dept.label || task.org === dept.id));
  return { active, blocked: active.filter((task: Task) => task.state === 'Blocked' || !!task.block) };
}
function officialModel(id: string) { const official = store.officialsData?.officials.find((item) => item.id === id); return official?.model_short || official?.model; }
function officialLastActive(id: string) { const official = store.officialsData?.officials.find((item) => item.id === id); return official?.last_active ? formatDashboardDateTime(official.last_active, { showSeconds: false }) : ''; }
</script>

<style scoped>
.duty-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 8px;
}

.duty-card {
  min-width: 0;
  padding: 10px;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.dept-emoji {
  font-size: 24px;
}

.duty-model {
  margin: 6px 0;
  overflow-wrap: anywhere;
}

.duty-task-list {
  display: grid;
  gap: 6px;
}

.duty-task {
  display: grid;
  gap: 3px;
  padding: 7px;
  border-radius: 10px;
  cursor: pointer;
  overflow-wrap: anywhere;
}

.duty-task:hover {
  background: var(--app-surface);
}
</style>
