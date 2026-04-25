function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function hasExplicitTimezone(value: string): boolean {
  return /(?:Z|[+\-]\d{2}:?\d{2})$/i.test(value);
}

export function parseDashboardTimestamp(value: number | string | undefined | null): Date | null {
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
  value: number | string | undefined | null,
  { showSeconds = true }: { showSeconds?: boolean } = {}
): string {
  const d = parseDashboardTimestamp(value);
  if (!d) return '';
  const date = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  const time = formatDashboardTime(d.getTime(), { showSeconds });
  return `${date} ${time}`;
}
