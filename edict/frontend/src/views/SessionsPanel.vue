<template>
  <div>
    <a-segmented v-model:value="store.sessFilter" :options="filters" style="margin-bottom: 10px" />
    <div v-if="sessions.length" class="card-list">
      <a-card v-for="task in sessions" :key="task.id" class="surface-card task-card" :bordered="false" @click="store.modalTaskId = task.id">
        <div class="row-between">
          <div class="wrap-row">
            <a-tag color="blue">{{ deptEmoji(task.org) }} {{ task.org || '执行中' }}</a-tag>
            <a-tag :color="stateColor(task.state)">{{ stateLabel(task) }}</a-tag>
            <a-tag v-if="task.heartbeat" :color="heartbeatColor(task.heartbeat.status)">{{ task.heartbeat.label }}</a-tag>
          </div>
          <span class="muted">{{ getTaskTiming(task).durationText }}</span>
        </div>
        <div class="task-title">{{ shortId(task.id) }} · {{ task.title }}</div>
        <p class="muted">{{ latestProgress(task) || task.now || task.output || '等待进展上报' }}</p>
        <div class="row-between" v-if="task.todos?.length">
          <span class="muted">Todo {{ completedTodos(task) }}/{{ task.todos.length }}</span>
          <span class="muted">{{ todoPercent(task) }}%</span>
        </div>
        <a-progress v-if="task.todos?.length" :percent="todoPercent(task)" size="small" />
      </a-card>
    </div>
    <a-empty v-else class="surface-card empty-state" description="暂无执行中会话" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { type Task } from '../api';
import { getTaskTiming } from '../time';
import { DEPTS, isArchived, isEdict, stateLabel, useDashboardStore } from '../stores/dashboard';
const store = useDashboardStore();
const baseFilters = [{ label: '全部', value: 'all' }, { label: '执行中', value: 'doing' }, { label: '待审查', value: 'review' }, { label: '阻塞', value: 'Blocked' }];
const departmentFilters = computed(() => DEPTS.filter((dept) => store.tasks.some((task) => task.org === dept.label || task.org === dept.id)).map((dept) => ({ label: `${dept.emoji} ${dept.label}`, value: `dept:${dept.id}` })));
const filters = computed(() => [...baseFilters, ...departmentFilters.value]);
const activeStates = ['Taizi', 'Zhongshu', 'Menxia', 'Assigned', 'Doing', 'Next', 'Review', 'Blocked'];
const sessions = computed(() => store.tasks.filter((t) => {
  if (!isEdict(t) || isArchived(t) || !activeStates.includes(t.state)) return false;
  if (store.sessFilter === 'all') return true;
  if (store.sessFilter === 'doing') return ['Taizi', 'Zhongshu', 'Assigned', 'Doing', 'Next'].includes(t.state);
  if (store.sessFilter === 'review') return ['Menxia', 'Review'].includes(t.state);
  if (store.sessFilter.startsWith('dept:')) {
    const dept = DEPTS.find((item) => item.id === store.sessFilter.slice(5));
    return t.org === dept?.label || t.org === dept?.id;
  }
  return t.state === store.sessFilter;
}));
function completedTodos(task: Task) { return task.todos?.filter((t) => t.status === 'completed').length || 0; }
function todoPercent(task: Task) { const total = task.todos?.length || 0; return total ? Math.round(completedTodos(task) / total * 100) : 0; }
function latestProgress(task: Task) { const latest = [...(task.progress_log || [])].reverse().find((item) => item.content || item.text); return latest?.content || latest?.text || ''; }
function shortId(id: string) { return id.length > 12 ? `${id.slice(0, 8)}…` : id; }
function stateColor(state: string) { return state === 'Blocked' ? 'error' : ['Review', 'Menxia'].includes(state) ? 'warning' : 'processing'; }
function heartbeatColor(status: string) { return status === 'active' ? 'success' : status === 'warn' ? 'warning' : status === 'stalled' ? 'error' : 'default'; }
function deptEmoji(org: string) { return DEPTS.find((dept) => dept.label === org || dept.id === org)?.emoji || '🏛️'; }
</script>

<style scoped>
p {
  margin: 6px 0 8px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
</style>
