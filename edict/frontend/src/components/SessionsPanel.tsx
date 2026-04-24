import { useStore, isEdict, STATE_LABEL, DEPTS } from '../store';
import type { Task, TodoItem, ActivityEntry } from '../api';
import { useState } from 'react';

const ACTIVE_STATES = ['Taizi', 'Zhongshu', 'Menxia', 'Assigned', 'Doing', 'Next', 'Review', 'Blocked'];

function getAgentEmoji(org: string): string {
  const d = DEPTS.find((d) => d.label === org);
  return d?.emoji || '🏛️';
}

function getAgentId(org: string): string {
  const d = DEPTS.find((d) => d.label === org);
  return d?.id || org;
}

function getProgressSummary(t: Task): string {
  const plog = t.progress_log || [];
  if (!plog.length) return '';
  const last = plog[plog.length - 1];
  const txt = (last.content || last.text || '').replace(/\n/g, ' ').trim();
  if (!txt) return '';
  return txt.length > 80 ? txt.substring(0, 80) + '...' : txt;
}

function getTodoProgress(t: Task): { done: number; total: number; pct: number } {
  const todos = t.todos || [];
  if (!todos.length) return { done: 0, total: 0, pct: 0 };
  const done = todos.filter((x) => x.status === 'completed').length;
  return { done, total: todos.length, pct: Math.round((done / todos.length) * 100) };
}

export default function SessionsPanel() {
  const liveStatus = useStore((s) => s.liveStatus);
  const sessFilter = useStore((s) => s.sessFilter);
  const setSessFilter = useStore((s) => s.setSessFilter);
  const [detailTask, setDetailTask] = useState<Task | null>(null);

  const tasks = liveStatus?.tasks || [];
  // 显示活跃的旨意任务（非 Done/Cancelled/归档）
  const activeEdicts = tasks.filter(
    (t) => isEdict(t) && !t.archived && ACTIVE_STATES.includes(t.state),
  );

  let filtered = activeEdicts;
  if (sessFilter === 'all') filtered = activeEdicts;
  else if (sessFilter === 'active') filtered = activeEdicts.filter((t) => ['Doing', 'Review', 'Assigned', 'Next'].includes(t.state));
  else filtered = activeEdicts.filter((t) => getAgentId(t.org || '') === sessFilter);

  // 按活跃 agent 分组筛选项
  const agentIds = [...new Set(activeEdicts.map((t) => getAgentId(t.org || '')))];
  const labelMap: Record<string, string> = {};
  const emojiMap: Record<string, string> = {};
  DEPTS.forEach((d) => {
    labelMap[d.id] = d.label;
    emojiMap[d.id] = d.emoji;
  });

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'all', label: `全部 (${activeEdicts.length})` },
          { key: 'active', label: '执行中' },
          ...agentIds.slice(0, 8).map((id) => ({ key: id, label: `${emojiMap[id] || ''} ${labelMap[id] || id}` })),
        ].map((f) => (
          <span
            key={f.key}
            className={`sess-filter${sessFilter === f.key ? ' active' : ''}`}
            onClick={() => setSessFilter(f.key)}
          >
            {f.label}
          </span>
        ))}
      </div>

      {/* Grid */}
      <div className="sess-grid">
        {!filtered.length ? (
          <div style={{ fontSize: 13, color: 'var(--muted)', padding: 24, textAlign: 'center', gridColumn: '1/-1' }}>
            暂无活跃旨意 — 下达新旨意后将在此显示执行进度
          </div>
        ) : (
          filtered.map((t) => {
            const agent = getAgentId(t.org || '');
            const emoji = getAgentEmoji(t.org || '');
            const agLabel = t.org || agent;
            const st = t.state || 'Unknown';
            const stLabel = STATE_LABEL[st] || st;
            const progress = getProgressSummary(t);
            const todoProg = getTodoProgress(t);
            const hb = t.heartbeat || { status: 'unknown' as const, label: '' };
            const hbDot = hb.status === 'active' ? '🟢' : hb.status === 'warn' ? '🟡' : hb.status === 'stalled' ? '🔴' : '⚪';

            return (
              <div className="sess-card" key={t.id} onClick={() => setDetailTask(t)}>
                <div className="sc-top">
                  <span className="sc-emoji">{emoji}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className="sc-agent">{agLabel}</span>
                      <span style={{ fontSize: 10, color: 'var(--muted)', background: 'var(--panel2)', padding: '2px 6px', borderRadius: 4 }}>
                        {t.id.substring(0, 8)}
                      </span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span title={hb.label || ''}>{hbDot}</span>
                    <span className={`tag st-${st}`} style={{ fontSize: 10 }}>{stLabel}</span>
                  </div>
                </div>
                <div className="sc-title">{t.title || t.id}</div>
                {progress && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5, marginBottom: 8, borderLeft: '2px solid var(--line)', paddingLeft: 8, maxHeight: 40, overflow: 'hidden' }}>
                    {progress}
                  </div>
                )}
                {todoProg.total > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 3 }}>
                      <span>子任务 {todoProg.done}/{todoProg.total}</span>
                      <span>{todoProg.pct}%</span>
                    </div>
                    <div style={{ background: 'var(--line)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
                      <div style={{ background: 'var(--acc)', height: '100%', width: `${todoProg.pct}%`, borderRadius: 3, transition: 'width 0.3s' }} />
                    </div>
                  </div>
                )}
                <div className="sc-meta">
                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                    {t.now ? t.now.substring(0, 40) : ''}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Detail Modal */}
      {detailTask && (
        <TaskDetailModal task={detailTask} onClose={() => setDetailTask(null)} />
      )}
    </div>
  );
}

function TaskDetailModal({ task: t, onClose }: { task: Task; onClose: () => void }) {
  const st = t.state || 'Unknown';
  const stLabel = STATE_LABEL[st] || st;
  const emoji = getAgentEmoji(t.org || '');
  const plog = t.progress_log || [];
  const todos = t.todos || [];
  const fl = t.flow_log || [];
  const todoProg = { done: todos.filter((x) => x.status === 'completed').length, total: todos.length };

  return (
    <div className="modal-bg open" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <div className="modal-body">
          <div style={{ fontSize: 11, color: 'var(--acc)', fontWeight: 700, letterSpacing: '.04em', marginBottom: 4 }}>{t.id}</div>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>{emoji} {t.title || t.id}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
            <span className={`tag st-${st}`}>{stLabel}</span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{t.org}</span>
            {todoProg.total > 0 && (
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                子任务 {todoProg.done}/{todoProg.total}
              </span>
            )}
          </div>

          {/* 当前进展 */}
          {t.now && (
            <div style={{ background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: 'var(--muted)' }}>
              {t.now}
            </div>
          )}

          {/* 子任务列表 */}
          {todos.length > 0 && (
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>📋 子任务</div>
              {todos.map((td: TodoItem, i: number) => {
                const icon = td.status === 'completed' ? '✅' : td.status === 'in-progress' ? '🔄' : '⬜';
                return (
                  <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--line)', fontSize: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>{icon}</span>
                      <span style={{ fontWeight: 500 }}>{td.title}</span>
                    </div>
                    {td.detail && (
                      <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4, paddingLeft: 20, lineHeight: 1.5 }}>
                        {td.detail}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 执行日志 */}
          {plog.length > 0 && (
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
                📝 执行日志 <span style={{ fontWeight: 400, color: 'var(--muted)' }}>({plog.length} 条)</span>
              </div>
              <div style={{ maxHeight: 250, overflowY: 'auto', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--panel2)' }}>
                {plog.slice().reverse().slice(0, 20).map((p, i) => {
                  const txt = (p.content || p.text || '').replace(/\n/g, ' ').trim();
                  const time = (p.ts || p.at || '').substring(0, 19).replace('T', ' ');
                  const agentEmoji = p.agent ? getAgentEmoji(p.agent) : '';
                  return (
                    <div key={i} style={{ padding: '8px 12px', borderBottom: '1px solid var(--line)', fontSize: 12, lineHeight: 1.5 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                        <span>{agentEmoji || '📝'}</span>
                        <span style={{ fontWeight: 600, fontSize: 11 }}>{p.agent || '系统'}</span>
                        <span style={{ color: 'var(--muted)', fontSize: 10, marginLeft: 'auto' }}>{time}</span>
                      </div>
                      <div style={{ color: 'var(--muted)' }}>{txt.length > 150 ? txt.substring(0, 150) + '...' : txt}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 流转记录 */}
          {fl.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
                📬 流转记录 <span style={{ fontWeight: 400, color: 'var(--muted)' }}>({fl.length} 步)</span>
              </div>
              <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--panel2)' }}>
                {fl.slice().reverse().map((f, i) => (
                  <div key={i} style={{ padding: '8px 12px', borderBottom: '1px solid var(--line)', fontSize: 12, lineHeight: 1.5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontWeight: 500 }}>{f.from}</span>
                      <span style={{ color: 'var(--muted)' }}>→</span>
                      <span style={{ fontWeight: 500 }}>{f.to}</span>
                      <span style={{ color: 'var(--muted)', fontSize: 10, marginLeft: 'auto' }}>
                        {(f.at || '').substring(11, 19)}
                      </span>
                    </div>
                    <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 2 }}>{f.remark}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {t.output && t.output !== '-' && (
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 12, wordBreak: 'break-all', borderTop: '1px solid var(--line)', paddingTop: 8 }}>
              📦 产出物: {t.output}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
