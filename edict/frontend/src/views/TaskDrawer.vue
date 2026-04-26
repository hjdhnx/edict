<template>
  <a-drawer :open="!!task" width="min(900px, 100vw)" placement="right" :title="task?.title" @close="store.modalTaskId = null">
    <template v-if="task">
      <a-space wrap style="margin-bottom: 10px">
        <a-tag color="blue">{{ task.id }}</a-tag>
        <a-tag>{{ stateLabel(task) }}</a-tag>
        <a-tag>{{ task.org || '未分派' }}</a-tag>
        <a-tag v-if="task.heartbeat" :color="heartbeatColor(task.heartbeat.status)">{{ task.heartbeat.label }}</a-tag>
        <a-tag v-if="timing.durationText">{{ timing.isTerminal ? '总耗时' : '已用时' }} {{ timing.durationText }}</a-tag>
        <a-tag v-if="task.review_round">审查第 {{ task.review_round }} 轮</a-tag>
      </a-space>

      <div class="pipe-line" style="margin-bottom: 18px">
        <span v-for="stage in getPipeStatus(task)" :key="stage.key" :class="['pipe-node', stage.status]">{{ stage.icon }} {{ stage.dept }} · {{ stage.action }}</span>
      </div>

      <a-card class="surface-card" :bordered="false" title="当前进展">
        <p>{{ task.now || task.output || '暂无进展说明' }}</p>
        <a-descriptions size="small" :column="1">
          <a-descriptions-item label="验收标准">{{ task.ac || '-' }}</a-descriptions-item>
          <a-descriptions-item label="阻塞原因">{{ task.block || '-' }}</a-descriptions-item>
          <a-descriptions-item label="预计完成">{{ formattedEta }}</a-descriptions-item>
        </a-descriptions>
        <a-space wrap>
          <a-button danger @click="actionWithReason('stop', '叫停原因')">叫停</a-button>
          <a-button danger @click="actionWithReason('cancel', '取消原因')">取消</a-button>
          <a-button v-if="['Blocked', 'Cancelled'].includes(task.state)" type="primary" @click="actionWithReason('resume', '恢复说明', '恢复执行')">恢复</a-button>
          <a-button v-if="['Review', 'Menxia'].includes(task.state)" type="primary" @click="review('approve')">批准</a-button>
          <a-button v-if="['Review', 'Menxia'].includes(task.state)" @click="review('reject')">封驳修订</a-button>
          <a-button @click="advance">推进</a-button>
        </a-space>
      </a-card>

      <div v-if="activityData" class="kpi-grid drawer-kpis">
        <div class="kpi-card"><div class="kpi-label">总耗时</div><div class="kpi-value">{{ activityData.totalDuration || timing.durationText || '-' }}</div><div class="kpi-hint">任务活动统计</div></div>
        <div class="kpi-card"><div class="kpi-label">Todo</div><div class="kpi-value">{{ activityData.todosSummary?.percent ?? todoPercent }}%</div><div class="kpi-hint">{{ activityData.todosSummary?.completed ?? completedTodos }}/{{ activityData.todosSummary?.total ?? (task.todos?.length || 0) }} 已完成</div></div>
        <div class="kpi-card"><div class="kpi-label">Token</div><div class="kpi-value">{{ activityData.resourceSummary?.totalTokens ?? '-' }}</div><div class="kpi-hint">资源消耗</div></div>
        <div class="kpi-card"><div class="kpi-label">成本</div><div class="kpi-value">{{ activityData.resourceSummary?.totalCost !== undefined ? `¥${activityData.resourceSummary.totalCost.toFixed(2)}` : '-' }}</div><div class="kpi-hint">估算成本</div></div>
      </div>

      <div class="two-col" style="margin-top: 10px">
        <a-card class="surface-card" :bordered="false" title="Todo 清单">
          <a-empty v-if="!task.todos?.length" description="暂无 todo" />
          <a-list v-else :data-source="task.todos" size="small">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :title="item.title" :description="item.detail" />
                <a-tag :color="item.status === 'completed' ? 'success' : item.status === 'in-progress' ? 'processing' : 'default'">{{ item.status }}</a-tag>
              </a-list-item>
            </template>
          </a-list>
        </a-card>

        <a-card class="surface-card" :bordered="false" title="调度状态">
          <a-skeleton v-if="loadingExtra" active />
          <template v-else>
            <p class="muted">{{ scheduler?.enabled === false ? '调度器未启用' : '调度器运行中' }}</p>
            <a-descriptions size="small" :column="1">
              <a-descriptions-item label="重试次数">{{ scheduler?.retryCount ?? '-' }}</a-descriptions-item>
              <a-descriptions-item label="升级等级">{{ scheduler?.escalationLevel ?? '-' }}</a-descriptions-item>
              <a-descriptions-item label="停滞时间">{{ formatDurationSeconds(schedulerData?.stalledSec) || '-' }}</a-descriptions-item>
              <a-descriptions-item label="停滞阈值">{{ formatDurationSeconds(scheduler?.stallThresholdSec) || '-' }}</a-descriptions-item>
              <a-descriptions-item label="最近进展">{{ formatDashboardDateTime(scheduler?.lastProgressAt) || '-' }}</a-descriptions-item>
              <a-descriptions-item label="最近派发">{{ formatDashboardDateTime(scheduler?.lastDispatchAt) || '-' }}</a-descriptions-item>
              <a-descriptions-item label="派发对象">{{ scheduler?.lastDispatchAgent || '-' }}</a-descriptions-item>
              <a-descriptions-item label="派发状态">{{ scheduler?.lastDispatchStatus || '-' }}</a-descriptions-item>
              <a-descriptions-item label="自动回滚">{{ scheduler?.autoRollback ? '启用' : '未启用' }}</a-descriptions-item>
            </a-descriptions>
            <a-space wrap>
              <a-button size="small" @click="scanScheduler">立即扫描</a-button>
              <a-button size="small" @click="sched('retry')">重试</a-button>
              <a-button size="small" @click="sched('escalate')">升级</a-button>
              <a-button size="small" danger @click="sched('rollback')">回滚</a-button>
            </a-space>
          </template>
        </a-card>
      </div>

      <a-card v-if="activityData?.phaseDurations?.length" class="surface-card" :bordered="false" title="阶段耗时" style="margin-top: 10px">
        <div class="phase-list">
          <div v-for="phase in activityData.phaseDurations" :key="phase.phase" class="phase-row">
            <div class="row-between"><b>{{ phase.phase }}</b><span class="muted">{{ phase.durationText }}{{ phase.ongoing ? ' · 进行中' : '' }}</span></div>
            <a-progress :percent="phasePercent(phase.durationSec)" size="small" />
          </div>
        </div>
      </a-card>

      <a-card class="surface-card" :bordered="false" title="流转记录" style="margin-top: 10px">
        <a-timeline>
          <a-timeline-item v-for="(flow, index) in task.flow_log || []" :key="index">
            <b>{{ flow.from || '系统' }}</b> → <b>{{ flow.to }}</b>
            <div class="muted">{{ formatDashboardDateTime(flow.at || flow.ts) }} · {{ flow.reason || flow.remark || '流转' }}</div>
          </a-timeline-item>
        </a-timeline>
      </a-card>

      <a-card class="surface-card" :bordered="false" title="完成产物" style="margin-top: 10px">
        <template v-if="task.report">
          <a-descriptions size="small" :column="1">
            <a-descriptions-item label="摘要">{{ task.report.summary || '-' }}</a-descriptions-item>
            <a-descriptions-item label="路径">{{ task.report.path || '-' }}</a-descriptions-item>
            <a-descriptions-item label="链接"><a v-if="task.report.url" :href="task.report.url" target="_blank" rel="noreferrer">{{ task.report.url }}</a><span v-else>-</span></a-descriptions-item>
            <a-descriptions-item label="截断">{{ task.report.truncated ? '内容过长，已截断' : '否' }}</a-descriptions-item>
          </a-descriptions>
          <div v-if="task.report.body" class="code-block">{{ task.report.body }}</div>
        </template>
        <div v-else class="code-block">{{ task.output || '暂无产物' }}</div>
      </a-card>

      <a-card class="surface-card" :bordered="false" title="实时活动" style="margin-top: 10px">
        <a-skeleton v-if="loadingExtra" active />
        <a-timeline v-else-if="activity.length">
          <a-timeline-item v-for="(entry, index) in activity" :key="index">
            <b>{{ activityTitle(entry) }}</b>
            <div class="muted">{{ formatDashboardDateTime(entry.at) }}</div>
            <div class="activity-text">{{ activityBody(entry) }}</div>
            <div v-if="entry.tools?.length" class="tool-list">
              <a-tag v-for="tool in entry.tools" :key="tool.name">{{ tool.name }}</a-tag>
            </div>
            <div v-if="entry.diff" class="code-block activity-code">{{ JSON.stringify(entry.diff, null, 2) }}</div>
            <div v-if="entry.exitCode !== undefined && entry.exitCode !== null" class="muted">退出码：{{ entry.exitCode }}</div>
          </a-timeline-item>
        </a-timeline>
        <a-empty v-else description="暂无实时活动" />
      </a-card>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { api, type ActivityEntry, type SchedulerStateData, type TaskActivityData } from '../api';
import { formatDashboardDateTime, formatDurationSeconds, getTaskTiming } from '../time';
import { getPipeStatus, stateLabel, useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const loadingExtra = ref(false);
const activity = ref<ActivityEntry[]>([]);
const activityData = ref<TaskActivityData | null>(null);
const schedulerData = ref<SchedulerStateData | null>(null);
const task = computed(() => store.tasks.find((item) => item.id === store.modalTaskId));
const timing = computed(() => (task.value ? getTaskTiming(task.value) : { durationText: '', isTerminal: false }));
const formattedEta = computed(() => formatDashboardDateTime(task.value?.eta) || '-');
const scheduler = computed(() => schedulerData.value?.scheduler);
const completedTodos = computed(() => task.value?.todos?.filter((todo) => todo.status === 'completed').length || 0);
const todoPercent = computed(() => {
  const total = task.value?.todos?.length || 0;
  return total ? Math.round((completedTodos.value / total) * 100) : 0;
});
let refreshTimer: ReturnType<typeof setInterval> | null = null;

watch(() => store.modalTaskId, async (id) => {
  clearRefreshTimer();
  activity.value = [];
  activityData.value = null;
  schedulerData.value = null;
  if (!id) return;
  await loadExtra(id);
  refreshTimer = setInterval(() => {
    if (store.modalTaskId) loadExtra(store.modalTaskId, true);
  }, 4000);
}, { immediate: true });

async function loadExtra(id: string, silent = false) {
  if (!silent) loadingExtra.value = true;
  try {
    const [act, sched] = await Promise.all([api.taskActivity(id), api.schedulerState(id)]);
    activityData.value = act;
    activity.value = act.activity || [];
    schedulerData.value = sched;
  } finally {
    loadingExtra.value = false;
  }
}

function clearRefreshTimer() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = null;
}

function heartbeatColor(status: string) {
  if (status === 'active') return 'success';
  if (status === 'warn') return 'warning';
  if (status === 'stalled') return 'error';
  return 'default';
}

async function actionWithReason(name: string, label: string, fallback = '前端操作') {
  if (!task.value) return;
  const reason = window.prompt(label, fallback);
  if (reason === null) return;
  const r = await api.taskAction(task.value.id, name, reason || fallback);
  store.toast(r.ok ? '操作已提交' : r.error || '操作失败', r.ok ? 'ok' : 'err');
  await store.loadAll();
}

async function review(name: 'approve' | 'reject') {
  if (!task.value) return;
  const comment = window.prompt(name === 'approve' ? '批准意见' : '封驳原因', name === 'approve' ? '准奏' : '退回修订');
  if (comment === null) return;
  const r = await api.reviewAction(task.value.id, name, comment);
  store.toast(r.ok ? '审查已提交' : r.error || '审查失败', r.ok ? 'ok' : 'err');
  await store.loadAll();
}

async function advance() {
  if (!task.value) return;
  const comment = window.prompt('推进说明', '前端推进');
  if (comment === null) return;
  const r = await api.advanceState(task.value.id, comment);
  store.toast(r.ok ? '已推进' : r.error || '推进失败', r.ok ? 'ok' : 'err');
  await store.loadAll();
}

async function sched(name: 'retry' | 'escalate' | 'rollback') {
  if (!task.value) return;
  const reason = window.prompt('调度操作说明', '前端调度操作');
  if (reason === null) return;
  const fn = name === 'retry' ? api.schedulerRetry : name === 'escalate' ? api.schedulerEscalate : api.schedulerRollback;
  const r = await fn(task.value.id, reason);
  store.toast(r.ok ? '调度操作已提交' : r.error || '调度失败', r.ok ? 'ok' : 'err');
  await Promise.all([store.loadAll(), loadExtra(task.value.id, true)]);
}

async function scanScheduler() {
  const r = await api.schedulerScan();
  store.toast(r.ok ? `扫描完成：${r.count || 0} 个动作` : r.error || '扫描失败', r.ok ? 'ok' : 'err');
  if (task.value) await Promise.all([store.loadAll(), loadExtra(task.value.id, true)]);
}

function phasePercent(seconds: number) {
  const max = Math.max(...(activityData.value?.phaseDurations || []).map((item) => item.durationSec), 1);
  return Math.max(3, Math.round((seconds / max) * 100));
}

function activityTitle(entry: ActivityEntry) {
  if (entry.agent) return `${entry.agent} · ${entry.kind}`;
  if (entry.tool) return `${entry.kind} · ${entry.tool}`;
  return entry.kind || '活动';
}

function activityBody(entry: ActivityEntry) {
  if (entry.text) return entry.text;
  if (entry.thinking) return entry.thinking;
  if (entry.output) return entry.output;
  if (entry.remark) return entry.remark;
  if (entry.from || entry.to) return `${entry.from || '系统'} → ${entry.to || ''}`;
  if (entry.items?.length) return entry.items.map((item) => `${item.status} · ${item.title}`).join('\n');
  return '无详细内容';
}

onUnmounted(() => clearRefreshTimer());
</script>

<style scoped>
.drawer-kpis {
  margin-top: 10px;
}

.phase-list {
  display: grid;
  gap: 8px;
}

.phase-row {
  display: grid;
  gap: 4px;
}

.activity-text {
  margin-top: 3px;
  white-space: pre-wrap;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.tool-list {
  margin-top: 5px;
}

.activity-code {
  margin-top: 6px;
  max-height: 180px;
  overflow: auto;
}
</style>
