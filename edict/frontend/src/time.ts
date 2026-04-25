type DashboardTimestamp = number | string | undefined | null;

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function hasExplicitTimezone(value: string): boolean {
  return /(?:Z|[+\-]\d{2}:?\d{2})$/i.test(value);
}

export function parseDashboardTimestamp(value: DashboardTimestamp): Date | null {
  if (value === undefined || value === null || value === '') return null;

  if (typeof value === 'number') {
    const ms = Math.abs(value) < 1e12 ? value * 1000 : value;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  const raw = String(value).trim();
  if (!raw) return null;

  if (/^\d+(\.\d+)?$/.test(raw)) {
    return parseDashboardTimestamp(Number(raw));
  }

  const d = new Date(raw);
  if (!Number.isNaN(d.getTime())) return d;

  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(raw) && !hasExplicitTimezone(raw)) {
    const local = new Date(raw.replace(' ', 'T'));
    return Number.isNaN(local.getTime()) ? null : local;
  }

  return null;
}

export function formatDashboardTime(
  value: number | string | undefined | null,
  { showSeconds = true }: { showSeconds?: boolean } = {}
): string {
  const d = parseDashboardTimestamp(value);
  if (!d) return '';
  const hh = pad2(d.getHours());
  const mm = pad2(d.getMinutes());
  if (!showSeconds) return `${hh}:${mm}`;
  return `${hh}:${mm}:${pad2(d.getSeconds())}`;
}

export function formatDashboardDateTime(
  value: DashboardTimestamp,
  { showSeconds = true }: { showSeconds?: boolean } = {}
): string {
  const d = parseDashboardTimestamp(value);
  if (!d) return '';
  const date = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  const time = formatDashboardTime(d.getTime(), { showSeconds });
  return `${date} ${time}`;
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '';
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return `${total}秒`;
  if (total < 3600) return `${Math.floor(total / 60)}分${pad2(total % 60)}秒`;
  if (total < 86400) return `${Math.floor(total / 3600)}小时${Math.floor((total % 3600) / 60)}分`;
  return `${Math.floor(total / 86400)}天${Math.floor((total % 86400) / 3600)}小时`;
}

export function pickFlowTimestamp(
  entry: { at?: DashboardTimestamp; ts?: DashboardTimestamp } | undefined | null
): DashboardTimestamp {
  return entry?.at ?? entry?.ts ?? null;
}

interface TimingFlowEntry {
  at?: DashboardTimestamp;
  ts?: DashboardTimestamp;
  to?: string;
}

interface TimingTask {
  state?: string;
  createdAt?: DashboardTimestamp;
  created_at?: DashboardTimestamp;
  updatedAt?: DashboardTimestamp;
  updated_at?: DashboardTimestamp;
  flow_log?: TimingFlowEntry[];
  report?: { captured_at?: DashboardTimestamp } | null;
}

export function getTaskTiming(task: TimingTask, now: DashboardTimestamp = Date.now()) {
  const flowLog = task.flow_log || [];
  const startAt =
    parseDashboardTimestamp(task.createdAt) ||
    parseDashboardTimestamp(task.created_at) ||
    parseDashboardTimestamp(pickFlowTimestamp(flowLog[0]));
  const isTerminal = ['Done', 'Cancelled'].includes(task.state || '');
  const terminalFlow = [...flowLog].reverse().find((f) => ['Done', 'Cancelled'].includes(f.to || ''));
  const lastFlow = flowLog.length ? flowLog[flowLog.length - 1] : undefined;
  const endAt = isTerminal
    ? (
      parseDashboardTimestamp(pickFlowTimestamp(terminalFlow)) ||
      parseDashboardTimestamp(pickFlowTimestamp(lastFlow)) ||
      parseDashboardTimestamp(task.report?.captured_at) ||
      parseDashboardTimestamp(task.updatedAt) ||
      parseDashboardTimestamp(task.updated_at)
    )
    : parseDashboardTimestamp(now);
  const elapsedSec = startAt && endAt ? Math.max(0, Math.floor((endAt.getTime() - startAt.getTime()) / 1000)) : null;
  return {
    startAt,
    endAt,
    elapsedSec,
    durationText: formatDurationSeconds(elapsedSec),
    isTerminal,
  };
}
