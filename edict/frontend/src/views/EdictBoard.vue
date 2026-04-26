<template>
  <div>
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">活跃旨意</div><div class="kpi-value">{{ activeTasks.length }}</div><div class="kpi-hint">不含归档与完成</div></div>
      <div class="kpi-card"><div class="kpi-label">执行中</div><div class="kpi-value">{{ doingCount }}</div><div class="kpi-hint">六部正在办理</div></div>
      <div class="kpi-card"><div class="kpi-label">待审查</div><div class="kpi-value">{{ reviewCount }}</div><div class="kpi-hint">等待尚书省汇总</div></div>
      <div class="kpi-card"><div class="kpi-label">已完成</div><div class="kpi-value">{{ doneCount }}</div><div class="kpi-hint">可在奏折阁查看</div></div>
    </div>

    <a-card class="surface-card" :bordered="false">
      <template #title>新下旨意</template>
      <div class="form-grid">
        <a-textarea v-model:value="newTitle" :rows="3" placeholder="请输入要交办的任务、调查或开发需求" @keydown.enter.exact.prevent="createTask" />
        <div class="wrap-row">
          <a-select v-model:value="targetDept" style="width: 180px">
            <a-select-option value="">自动分派</a-select-option>
            <a-select-option value="bingbu">兵部</a-select-option>
            <a-select-option value="gongbu">工部</a-select-option>
            <a-select-option value="hubu">户部</a-select-option>
            <a-select-option value="libu">礼部</a-select-option>
            <a-select-option value="xingbu">刑部</a-select-option>
            <a-select-option value="menxia">门下省</a-select-option>
            <a-select-option value="zhongshu">中书省</a-select-option>
          </a-select>
          <a-select v-model:value="priority" style="width: 140px">
            <a-select-option value="normal">普通</a-select-option>
            <a-select-option value="high">加急</a-select-option>
            <a-select-option value="low">低优先级</a-select-option>
          </a-select>
          <a-button type="primary" :loading="creating" @click="createTask">下旨</a-button>
        </div>
      </div>
    </a-card>

    <div class="row-between" style="margin: 12px 0 8px">
      <a-segmented v-model:value="store.edictFilter" :options="filterOptions" />
      <div class="wrap-row">
        <a-button @click="scanScheduler">扫描阻塞</a-button>
        <a-button v-if="doneUnarchivedCount" @click="archiveAllDone">归档已完成/取消</a-button>
      </div>
    </div>

    <div v-if="filteredTasks.length" class="card-list">
      <a-card v-for="task in filteredTasks" :key="task.id" class="surface-card task-card" :bordered="false" @click="store.modalTaskId = task.id">
        <div class="pipe-line">
          <span v-for="stage in getPipeStatus(task)" :key="stage.key" :class="['pipe-node', stage.status]">{{ stage.icon }} {{ stage.dept }}</span>
        </div>
        <div class="row-between task-meta-line">
          <span class="muted">{{ task.id }}</span>
          <span class="muted">{{ currentStageText(task) }}</span>
        </div>
        <div class="task-title">{{ task.title }}</div>
        <p v-if="task.now" class="muted task-now">{{ task.now }}</p>
        <div class="wrap-row">
          <a-tag :color="stateColor(task.state)">{{ stateLabel(task) }}</a-tag>
          <a-tag>{{ task.org || '未分派' }}</a-tag>
          <a-tag v-if="task.review_round">第 {{ task.review_round }} 轮审查</a-tag>
          <a-tag v-if="task.block" color="error">{{ task.block }}</a-tag>
          <a-tag v-if="task.heartbeat" :color="heartbeatColor(task.heartbeat.status)">{{ task.heartbeat.label }}</a-tag>
        </div>
        <a-progress v-if="task.todos?.length" style="margin-top: 8px" :percent="todoPercent(task)" size="small" />
        <div class="row-between" style="margin-top: 8px">
          <span class="muted">{{ timing(task).durationText ? `${timing(task).isTerminal ? '总耗时' : '已用时'} ${timing(task).durationText}` : etaText(task) }}</span>
          <a-space @click.stop>
            <a-button v-if="!['Done', 'Cancelled'].includes(task.state)" size="small" danger @click="taskAction(task.id, 'stop')">叫停</a-button>
            <a-button v-if="!['Done', 'Cancelled'].includes(task.state)" size="small" danger @click="taskAction(task.id, 'cancel')">取消</a-button>
            <a-button size="small" @click="archiveTask(task, !task.archived)">{{ task.archived ? '取消归档' : '归档' }}</a-button>
            <a-button v-if="['Blocked', 'Cancelled'].includes(task.state)" size="small" type="primary" @click="taskAction(task.id, 'resume')">恢复</a-button>
          </a-space>
        </div>
      </a-card>
    </div>
    <a-empty v-else class="surface-card empty-state" description="暂无符合条件的旨意" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { Modal } from 'ant-design-vue';
import { api, type Task } from '../api';
import { formatDashboardDateTime, getTaskTiming } from '../time';
import { getPipeStatus, isArchived, isEdict, stateLabel, useDashboardStore } from '../stores/dashboard';

const STATE_ORDER: Record<string, number> = { Blocked: 0, Review: 1, Menxia: 2, Doing: 3, Assigned: 4, Zhongshu: 5, Taizi: 6, Next: 7, Done: 8, Cancelled: 9 };
const store = useDashboardStore();
const newTitle = ref('');
const targetDept = ref('');
const priority = ref('normal');
const creating = ref(false);
const filterOptions = [
  { label: '活跃', value: 'active' },
  { label: '已归档', value: 'archived' },
  { label: '全部', value: 'all' },
];

const edicts = computed(() => store.tasks.filter(isEdict));
const activeTasks = computed(() => edicts.value.filter((t) => !isArchived(t) && !['Done', 'Cancelled'].includes(t.state)));
const doingCount = computed(() => edicts.value.filter((t) => t.state === 'Doing').length);
const reviewCount = computed(() => edicts.value.filter((t) => ['Review', 'Menxia'].includes(t.state)).length);
const doneCount = computed(() => edicts.value.filter((t) => t.state === 'Done').length);
const doneUnarchivedCount = computed(() => edicts.value.filter((t) => !isArchived(t) && ['Done', 'Cancelled'].includes(t.state)).length);
const filteredTasks = computed(() => edicts.value
  .filter((task) => store.edictFilter === 'all' || (store.edictFilter === 'archived' ? isArchived(task) : !isArchived(task)))
  .sort((a, b) => (STATE_ORDER[a.state] ?? 50) - (STATE_ORDER[b.state] ?? 50) || String(b.updatedAt || b.updated_at || '').localeCompare(String(a.updatedAt || a.updated_at || ''))));

function etaText(task: Task) {
  return formatDashboardDateTime(task.eta) || '-';
}

function stateColor(state: string) {
  if (state === 'Done') return 'success';
  if (state === 'Blocked' || state === 'Cancelled') return 'error';
  if (state === 'Review' || state === 'Menxia') return 'warning';
  return 'processing';
}
function heartbeatColor(status: string) {
  if (status === 'active') return 'success';
  if (status === 'warn') return 'warning';
  if (status === 'stalled') return 'error';
  return 'default';
}
function todoPercent(task: Task) {
  const total = task.todos?.length || 0;
  if (!total) return 0;
  return Math.round((task.todos.filter((todo) => todo.status === 'completed').length / total) * 100);
}
function timing(task: Task) {
  return getTaskTiming(task);
}
function currentStageText(task: Task) {
  const current = getPipeStatus(task).find((stage) => stage.status === 'active');
  return current ? `${current.dept} · ${current.action}` : stateLabel(task);
}
async function createTask() {
  if (!newTitle.value.trim()) return;
  creating.value = true;
  const result = await api.createTask({ title: newTitle.value.trim(), org: '皇上', targetDept: targetDept.value || undefined, priority: priority.value });
  creating.value = false;
  if (result.ok) {
    store.toast('旨意已创建', 'ok');
    newTitle.value = '';
    await store.loadAll();
    if (result.taskId) store.modalTaskId = result.taskId;
  } else store.toast(result.error || '创建失败', 'err');
}
async function archiveTask(task: Task, archived: boolean) {
  const result = await api.archiveTask(task.id, archived);
  if (result.ok) {
    store.toast(archived ? '已归档' : '已取消归档', 'ok');
    store.loadAll();
  } else store.toast(result.error || '操作失败', 'err');
}
async function archiveAllDone() {
  Modal.confirm({ title: '归档所有已完成/取消旨意？', okText: '归档', cancelText: '取消', onOk: async () => { const r = await api.archiveAllDone(); store.toast(r.ok ? `已归档 ${r.count || 0} 条` : r.error || '归档失败', r.ok ? 'ok' : 'err'); store.loadAll(); } });
}
async function scanScheduler() {
  const r = await api.schedulerScan();
  store.toast(r.ok ? `扫描完成：${r.count || 0} 个动作` : r.error || '扫描失败', r.ok ? 'ok' : 'err');
  store.loadAll();
}
async function taskAction(taskId: string, action: string) {
  const reason = window.prompt(action === 'resume' ? '恢复说明' : action === 'stop' ? '叫停原因' : '取消原因', action === 'resume' ? '恢复执行' : '前端操作');
  if (reason === null) return;
  const r = await api.taskAction(taskId, action, reason || '前端操作');
  store.toast(r.ok ? '操作已提交' : r.error || '操作失败', r.ok ? 'ok' : 'err');
  store.loadAll();
}
</script>

<style scoped>
.task-meta-line {
  margin-top: 8px;
  font-size: 11px;
  gap: 8px;
}

.task-now {
  margin: 5px 0 7px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
</style>
