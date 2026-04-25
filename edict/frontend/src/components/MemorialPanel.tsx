import { useState } from 'react';
import { useStore, isEdict, STATE_LABEL } from '../store';
import { formatDashboardDateTime } from '../time';
import type { Task, FlowEntry, TaskReport } from '../api';

function getTaskReport(t: Task): TaskReport | null {
  if (t.report && (t.report.summary || t.report.path || t.report.url || t.report.body)) return t.report;
  if (t.output && t.output !== '-') return { summary: t.output };
  return null;
}

function appendReportMarkdown(md: string, report: TaskReport | null): string {
  if (!report) return md;
  md += `## 奏折产出\n\n`;
  if (report.summary) md += `### 摘要\n\n${report.summary}\n\n`;
  if (report.url) md += `### 链接\n\n${report.url}\n\n`;
  if (report.path) md += `### 文件位置\n\n\`${report.path}\`\n\n`;
  if (report.body) {
    md += `### 正文预览\n\n${report.body}\n\n`;
    if (report.truncated) md += `_正文已截断，仅展示预览。_\n\n`;
  }
  return md;
}

function ReportBlock({ report }: { report: TaskReport | null }) {
  if (!report) return null;
  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)' }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>奏折产出</div>
      {report.summary && <div style={{ fontSize: 12, lineHeight: 1.6, marginBottom: 10 }}>{report.summary}</div>}
      {(report.path || report.url) && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>产物位置</div>
          {report.url ? (
            <a href={report.url} target="_blank" rel="noreferrer" style={{ fontSize: 11, wordBreak: 'break-all' }}>{report.url}</a>
          ) : (
            <code style={{ fontSize: 11, wordBreak: 'break-all', userSelect: 'text' }}>{report.path}</code>
          )}
        </div>
      )}
      {report.body && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4 }}>
            正文预览{report.truncated ? '（已截断）' : ''}
          </div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 260, overflow: 'auto', background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 8, padding: 10, fontSize: 11, lineHeight: 1.55 }}>{report.body}</pre>
        </div>
      )}
    </div>
  );
}

export default function MemorialPanel() {
  const liveStatus = useStore((s) => s.liveStatus);
  const [filter, setFilter] = useState('all');
  const [detailTask, setDetailTask] = useState<Task | null>(null);
  const toast = useStore((s) => s.toast);

  const tasks = liveStatus?.tasks || [];
  let mems = tasks.filter((t) => isEdict(t) && ['Done', 'Cancelled'].includes(t.state));
  if (filter !== 'all') mems = mems.filter((t) => t.state === filter);

  const exportMemorial = (t: Task) => {
    const fl = t.flow_log || [];
    let md = `# 📜 奏折 · ${t.title}\n\n`;
    md += `- **任务编号**: ${t.id}\n`;
    md += `- **状态**: ${t.state}\n`;
    md += `- **负责部门**: ${t.org}\n`;
    if (fl.length) {
      const startAt = formatDashboardDateTime(fl[0].at) || '未知';
      const endAt = formatDashboardDateTime(fl[fl.length - 1].at) || '未知';
      md += `- **开始时间**: ${startAt}\n`;
      md += `- **完成时间**: ${endAt}\n`;
    }
    md += `\n## 流转记录\n\n`;
    for (const f of fl) {
      md += `- **${f.from}** → **${f.to}**  \n  ${f.remark}  \n  _${formatDashboardDateTime(f.at) || '未知'}_\n\n`;
    }
    md = appendReportMarkdown(md, getTaskReport(t));
    navigator.clipboard.writeText(md).then(
      () => toast('✅ 奏折已复制为 Markdown', 'ok'),
      () => toast('复制失败', 'err')
    );
  };

  return (
    <div>
      {/* Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>筛选：</span>
        {[
          { key: 'all', label: '全部' },
          { key: 'Done', label: '✅ 已完成' },
          { key: 'Cancelled', label: '🚫 已取消' },
        ].map((f) => (
          <span
            key={f.key}
            className={`sess-filter${filter === f.key ? ' active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </span>
        ))}
      </div>

      {/* List */}
      <div className="mem-list">
        {!mems.length ? (
          <div className="mem-empty">暂无奏折 — 任务完成后自动生成</div>
        ) : (
          mems.map((t) => {
            const fl = t.flow_log || [];
            const depts = [...new Set(fl.map((f) => f.from).concat(fl.map((f) => f.to)).filter((x) => x && x !== '皇上'))];
            const firstAt = fl.length ? formatDashboardDateTime(fl[0].at) : '';
            const lastAt = fl.length ? formatDashboardDateTime(fl[fl.length - 1].at) : '';
            const stIcon = t.state === 'Done' ? '✅' : '🚫';
            return (
              <div className="mem-card" key={t.id} onClick={() => setDetailTask(t)}>
                <div className="mem-icon">📜</div>
                <div className="mem-info">
                  <div className="mem-title">
                    {stIcon} {t.title || t.id}
                  </div>
                  <div className="mem-sub">
                    {t.id} · {t.org || ''} · 流转 {fl.length} 步
                  </div>
                  <div className="mem-tags">
                    {depts.slice(0, 5).map((d) => (
                      <span className="mem-tag" key={d}>{d}</span>
                    ))}
                  </div>
                </div>
                <div className="mem-right">
                  <span className="mem-date">{firstAt}</span>
                  {lastAt !== firstAt && <span className="mem-date">{lastAt}</span>}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Detail Modal */}
      {detailTask && (
        <MemorialDetailModal task={detailTask} onClose={() => setDetailTask(null)} onExport={exportMemorial} />
      )}
    </div>
  );
}

function MemorialDetailModal({
  task: t,
  onClose,
  onExport,
}: {
  task: Task;
  onClose: () => void;
  onExport: (t: Task) => void;
}) {
  const fl = t.flow_log || [];
  const st = t.state || 'Unknown';
  const stIcon = st === 'Done' ? '✅' : st === 'Cancelled' ? '🚫' : '🔄';
  const depts = [...new Set(fl.map((f) => f.from).concat(fl.map((f) => f.to)).filter((x) => x && x !== '皇上'))];

  // Reconstruct phases
  const originLog: FlowEntry[] = [];
  const planLog: FlowEntry[] = [];
  const reviewLog: FlowEntry[] = [];
  const execLog: FlowEntry[] = [];
  const resultLog: FlowEntry[] = [];
  for (const f of fl) {
    if (f.from === '皇上') originLog.push(f);
    else if (f.to === '中书省' || f.from === '中书省') planLog.push(f);
    else if (f.to === '门下省' || f.from === '门下省') reviewLog.push(f);
    else if (f.remark && (f.remark.includes('完成') || f.remark.includes('回奏'))) resultLog.push(f);
    else execLog.push(f);
  }

  const renderPhase = (title: string, icon: string, items: FlowEntry[]) => {
    if (!items.length) return null;
    return (
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
          {icon} {title}
        </div>
        <div className="md-timeline">
          {items.map((f, i) => {
            const dotCls = f.remark?.includes('✅') ? 'green' : f.remark?.includes('驳') ? 'red' : '';
            return (
              <div className="md-tl-item" key={i}>
                <div className={`md-tl-dot ${dotCls}`} />
                <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                  <span className="md-tl-from">{f.from}</span>
                  <span className="md-tl-to">→ {f.to}</span>
                </div>
                <div className="md-tl-remark">{f.remark}</div>
                <div className="md-tl-time">{formatDashboardDateTime(f.at)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="modal-bg open" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <div className="modal-body">
          <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>{t.id}</div>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>{stIcon} {t.title || t.id}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
            <span className={`tag st-${st}`}>{STATE_LABEL[st] || st}</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{t.org}</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>流转 {fl.length} 步</span>
            {depts.map((d) => (
              <span className="mem-tag" key={d}>{d}</span>
            ))}
          </div>

          {t.now && (
            <div style={{ background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: 'var(--muted)' }}>
              {t.now}
            </div>
          )}

          {renderPhase('圣旨原文', '👑', originLog)}
          {renderPhase('中书规划', '📋', planLog)}
          {renderPhase('门下审议', '🔍', reviewLog)}
          {renderPhase('六部执行', '⚔️', execLog)}
          {renderPhase('汇总回奏', '📨', resultLog)}

          {/* 进展记录 — 展示 agent 工作过程和结果 */}
          {(() => {
            const plog = t.progress_log || [];
            if (!plog.length) return null;
            return (
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>📝 执行记录</div>
                <div className="md-timeline">
                  {plog.map((p: any, i: number) => (
                    <div className="md-tl-item" key={i}>
                      <div className="md-tl-dot" />
                      <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.5 }}>{p.content || p.text || ''}</div>
                      <div className="md-tl-time">{formatDashboardDateTime(p.ts || p.at)}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          <ReportBlock report={getTaskReport(t)} />

          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
            <button className="btn btn-g" onClick={() => onExport(t)} style={{ fontSize: 12, padding: '6px 16px' }}>
              📋 复制奏折
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
