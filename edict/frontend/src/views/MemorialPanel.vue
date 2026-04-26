<template>
  <div class="memorial-panel">
    <a-segmented v-model:value="filter" :options="filters" style="margin-bottom: 10px" />
    <div v-if="memorials.length" class="panel-grid">
      <a-card v-for="task in memorials" :key="task.id" class="surface-card task-card" :bordered="false" @click="store.modalTaskId = task.id">
        <div class="row-between"><a-tag :color="task.state === 'Done' ? 'success' : 'default'">{{ task.state === 'Done' ? '已办结' : '已取消' }}</a-tag><span class="muted">总耗时 {{ getTaskTiming(task).durationText || '-' }}</span></div>
        <div class="task-title">{{ task.title }}</div>
        <p class="muted">{{ task.report?.summary || task.output || '无摘要' }}</p>
        <div class="memorial-meta">
          <a-tag>{{ task.org || '未分派' }}</a-tag>
          <a-tag>流转 {{ task.flow_log?.length || 0 }} 步</a-tag>
          <a-tag v-if="task.flow_log?.[0]">始 {{ formatDashboardDateTime(task.flow_log[0].at || task.flow_log[0].ts, { showSeconds: false }) }}</a-tag>
          <a-tag>{{ formatDashboardDateTime(task.report?.captured_at || task.updatedAt || task.updated_at, { showSeconds: false }) }}</a-tag>
        </div>
        <div class="wrap-row memorial-meta">
          <a-tag v-for="dept in departments(task)" :key="dept">{{ dept }}</a-tag>
          <a-button size="small" @click.stop="copyMarkdown(task)">复制奏折</a-button>
        </div>
      </a-card>
    </div>
    <a-empty v-else class="surface-card empty-state" description="暂无奏折" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { type Task } from '../api';
import { formatDashboardDateTime, getTaskTiming } from '../time';
import { isEdict, useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const filter = ref('all');
const filters = [{ label: '全部', value: 'all' }, { label: '已办结', value: 'Done' }, { label: '已取消', value: 'Cancelled' }];
const memorials = computed(() => store.tasks.filter((t) => isEdict(t) && ['Done', 'Cancelled'].includes(t.state) && (filter.value === 'all' || t.state === filter.value)));

function departments(task: Task) {
  const values = new Set<string>();
  if (task.org) values.add(task.org);
  task.flow_log?.forEach((flow) => {
    if (flow.from) values.add(flow.from);
    if (flow.to) values.add(flow.to);
    if (flow.agent) values.add(flow.agent);
  });
  return [...values].filter(Boolean).slice(0, 6);
}

async function copyMarkdown(task: Task) {
  const timing = getTaskTiming(task);
  const flow = (task.flow_log || []).map((item, index) => `${index + 1}. ${formatDashboardDateTime(item.at || item.ts)}：${item.from || '系统'} → ${item.to || ''}（${item.reason || item.remark || '流转'}）`).join('\n') || '无';
  const progress = (task.progress_log || []).map((item, index) => `${index + 1}. ${formatDashboardDateTime(item.at || item.ts)} ${item.agent || ''}：${item.content || item.text || ''}`).join('\n') || '无';
  const report = task.report;
  const md = `# ${task.title}\n\n- ID: ${task.id}\n- 状态: ${task.state}\n- 部门: ${task.org || '-'}\n- 总耗时: ${timing.durationText || '-'}\n- 开始: ${timing.startAt ? formatDashboardDateTime(timing.startAt.getTime()) : '-'}\n- 结束: ${timing.endAt ? formatDashboardDateTime(timing.endAt.getTime()) : '-'}\n\n## 流转记录\n\n${flow}\n\n## 执行记录\n\n${progress}\n\n## 产物\n\n- 摘要: ${report?.summary || '-'}\n- 路径: ${report?.path || '-'}\n- 链接: ${report?.url || '-'}\n- 截断: ${report?.truncated ? '是' : '否'}\n\n${report?.body || task.output || ''}`;
  await navigator.clipboard.writeText(md);
  store.toast('奏折 Markdown 已复制', 'ok');
}
</script>

<style scoped>
.memorial-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 7px;
}

.memorial-panel p {
  margin: 6px 0 0;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
</style>
