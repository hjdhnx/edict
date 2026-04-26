<template>
  <div class="panel-grid court-panel">
    <a-card v-if="!sessionId" class="surface-card" :bordered="false" title="朝堂议政">
      <div class="form-grid">
        <a-textarea v-model:value="topic" :rows="3" placeholder="输入议题，或选择下方预设议题" />

        <div>
          <div class="section-title">预设议题</div>
          <div class="wrap-row topic-list">
            <a-button v-for="item in presetTopics" :key="item" size="small" @click="topic = item">{{ item }}</a-button>
          </div>
        </div>

        <div>
          <div class="row-between section-head">
            <div>
              <div class="section-title">参议官员</div>
              <div class="muted">至少 2 位，最多 8 位；点击卡片切换选择。</div>
            </div>
            <a-tag>{{ selectedOfficials.length }}/8</a-tag>
          </div>
          <div class="official-grid">
            <button
              v-for="dept in DEPTS"
              :key="dept.id"
              type="button"
              :class="['official-card', { selected: selectedOfficials.includes(dept.id) }]"
              @click="toggleOfficial(dept.id)"
            >
              <span class="official-emoji">{{ dept.emoji }}</span>
              <span class="official-info">
                <b>{{ dept.label }}</b>
                <small>{{ dept.role }} · {{ dept.rank }}</small>
              </span>
            </button>
          </div>
        </div>

        <a-button type="primary" size="large" :loading="loading" :disabled="!canStart" @click="start">开议</a-button>
      </div>
    </a-card>

    <template v-else>
      <a-card class="surface-card court-header" :bordered="false">
        <div class="row-between court-control">
          <div>
            <div class="muted">{{ sessionPhase === 'concluded' ? '已形成结论' : '议政进行中' }}</div>
            <h2>{{ topic }}</h2>
            <div class="wrap-row">
              <a-tag color="processing">第 {{ round }} 轮</a-tag>
              <a-tag>{{ sessionOfficials.length }} 位官员</a-tag>
              <a-tag v-if="advancing">众臣正在议论…</a-tag>
            </div>
          </div>
          <a-space wrap>
            <a-button :loading="advancing" :disabled="sessionPhase !== 'active'" @click="advance()">推进一轮</a-button>
            <a-button :type="autoAdvance ? 'primary' : 'default'" :disabled="sessionPhase !== 'active'" @click="toggleAutoAdvance">
              {{ autoAdvance ? '停止自动推进' : '自动推进' }}
            </a-button>
            <a-button :loading="concluding" :disabled="sessionPhase !== 'active'" @click="conclude">形成结论</a-button>
            <a-button danger @click="reset">退朝重置</a-button>
          </a-space>
        </div>
      </a-card>

      <div class="court-layout">
        <a-card class="surface-card court-stage" :bordered="false" title="朝堂站位">
          <div class="throne">👑<span>皇帝</span></div>
          <div class="seat-grid">
            <div
              v-for="official in sessionOfficials"
              :key="official.id"
              :class="['seat-card', { speaking: official.id === latestOfficialId }]"
            >
              <div class="seat-emoji">{{ official.emoji || nameEmoji(official.name) }}</div>
              <b>{{ cleanOfficialName(official.name) }}</b>
              <small>{{ official.role || '参议官员' }}</small>
              <a-tag v-if="emotionFor(official.id)" size="small">{{ emotionFor(official.id) }}</a-tag>
            </div>
          </div>
        </a-card>

        <a-card class="surface-card message-card" :bordered="false" title="议政记录">
          <div v-if="displayMessages.length" class="message-list">
            <div v-for="(msg, index) in displayMessages" :key="index" :class="['court-message', messageClass(msg)]">
              <div class="message-speaker">{{ messageSpeaker(msg) }}</div>
              <div class="message-content">{{ msg.content }}</div>
              <div v-if="msg.emotion || msg.action" class="message-meta">{{ [msg.emotion, msg.action].filter(Boolean).join(' · ') }}</div>
            </div>
          </div>
          <a-empty v-else description="众臣尚未发言" />
        </a-card>
      </div>

      <a-card class="surface-card" :bordered="false" title="皇帝发言与天命">
        <div class="command-grid">
          <a-textarea v-model:value="emperorMessage" :rows="3" placeholder="皇帝发言：让众臣回应你的补充问题" />
          <a-textarea v-model:value="decree" :rows="3" placeholder="天命：给本轮讨论加入突发约束或事件" />
        </div>
        <div class="wrap-row action-row">
          <a-button :disabled="!emperorMessage.trim() || sessionPhase !== 'active'" :loading="advancing" @click="sendEmperor">发送皇帝发言</a-button>
          <a-button :disabled="!decree.trim() || sessionPhase !== 'active'" :loading="advancing" @click="sendDecree">降下天命</a-button>
          <a-button :disabled="sessionPhase !== 'active'" @click="rollFate">掷命运骰子</a-button>
        </div>
      </a-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { api, type CourtMessage, type CourtOfficial } from '../api';
import { DEPTS, isArchived, isEdict, useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const topic = ref('');
const selectedOfficials = ref(['zhongshu', 'menxia', 'bingbu']);
const sessionId = ref('');
const sessionOfficials = ref<CourtOfficial[]>([]);
const messages = ref<CourtMessage[]>([]);
const round = ref(0);
const sessionPhase = ref('active');
const loading = ref(false);
const advancing = ref(false);
const concluding = ref(false);
const autoAdvance = ref(false);
const emperorMessage = ref('');
const decree = ref('');
let autoTimer: ReturnType<typeof setInterval> | null = null;

const staticTopics = ['架构优化与技术债治理', '项目风险与阻塞排查', '下周执行计划', '线上 Bug 排查与稳定性提升'];
const presetTopics = computed(() => {
  const edictTopics = store.tasks
    .filter((task) => isEdict(task) && !isArchived(task))
    .slice(0, 3)
    .map((task) => `围绕旨意 ${task.id}：${task.title}`);
  return [...edictTopics, ...staticTopics];
});
const canStart = computed(() => topic.value.trim().length > 0 && selectedOfficials.value.length >= 2);
const displayMessages = computed(() => messages.value);
const latestOfficialId = computed(() => [...messages.value].reverse().find((msg) => msg.official_id)?.official_id || '');

function toggleOfficial(id: string) {
  if (selectedOfficials.value.includes(id)) {
    if (selectedOfficials.value.length <= 2) {
      store.toast('至少保留 2 位参议官员', 'err');
      return;
    }
    selectedOfficials.value = selectedOfficials.value.filter((item) => item !== id);
    return;
  }
  if (selectedOfficials.value.length >= 8) {
    store.toast('最多选择 8 位参议官员', 'err');
    return;
  }
  selectedOfficials.value = [...selectedOfficials.value, id];
}

async function start() {
  if (!canStart.value || loading.value) return;
  loading.value = true;
  const r = await api.courtDiscussStart(topic.value.trim(), selectedOfficials.value);
  loading.value = false;
  if (!r.ok) {
    store.toast(r.error || '开议失败', 'err');
    return;
  }
  sessionId.value = r.session_id || '';
  sessionOfficials.value = r.officials || selectedOfficials.value.map((id) => {
    const dept = DEPTS.find((item) => item.id === id);
    return { id, name: `${dept?.emoji || ''} ${dept?.label || id}`, emoji: dept?.emoji, role: dept?.role };
  });
  messages.value = r.messages || [];
  round.value = r.round || 0;
  sessionPhase.value = r.phase || 'active';
  if (r.scene_note) addScene(r.scene_note);
  store.toast('朝堂已开议', 'ok');
  await advance();
}

async function advance(userMessage?: string, fateDecree?: string) {
  if (!sessionId.value || advancing.value || sessionPhase.value !== 'active') return;
  advancing.value = true;
  const r = await api.courtDiscussAdvance(sessionId.value, userMessage, fateDecree);
  advancing.value = false;
  if (!r.ok) {
    store.toast(r.error || '推进失败', 'err');
    return;
  }
  if (userMessage) messages.value.push({ type: 'emperor', content: userMessage });
  if (fateDecree) messages.value.push({ type: 'decree', content: fateDecree });
  messages.value.push(...(r.new_messages || []));
  if (r.scene_note) addScene(r.scene_note);
  round.value = r.round || round.value;
}

function addScene(content: string) {
  messages.value.push({ type: 'scene', content });
}

async function sendEmperor() {
  const content = emperorMessage.value.trim();
  if (!content) return;
  emperorMessage.value = '';
  await advance(content);
}

async function sendDecree() {
  const content = decree.value.trim();
  if (!content) return;
  decree.value = '';
  await advance(undefined, content);
}

async function rollFate() {
  const r = await api.courtDiscussFate();
  if (!r.ok) {
    store.toast('命运骰子无响应', 'err');
    return;
  }
  decree.value = r.event;
  await sendDecree();
}

function toggleAutoAdvance() {
  autoAdvance.value = !autoAdvance.value;
  if (!autoAdvance.value) {
    stopAutoAdvance();
    return;
  }
  autoTimer = setInterval(() => advance(), 5000);
}

function stopAutoAdvance() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = null;
  autoAdvance.value = false;
}

async function conclude() {
  if (!sessionId.value || concluding.value) return;
  concluding.value = true;
  const r = await api.courtDiscussConclude(sessionId.value);
  concluding.value = false;
  if (!r.ok) {
    store.toast(r.error || '结论失败', 'err');
    return;
  }
  stopAutoAdvance();
  sessionPhase.value = 'concluded';
  messages.value.push({ type: 'summary', content: r.summary || '议政已结束' });
  store.toast('议政已形成结论', 'ok');
}

async function reset() {
  stopAutoAdvance();
  if (sessionId.value) await api.courtDiscussDestroy(sessionId.value);
  sessionId.value = '';
  sessionOfficials.value = [];
  messages.value = [];
  round.value = 0;
  sessionPhase.value = 'active';
  emperorMessage.value = '';
  decree.value = '';
}

function nameEmoji(name: string) {
  return name.match(/^\p{Emoji}/u)?.[0] || '🏛️';
}

function cleanOfficialName(name: string | undefined) {
  return (name || '官员').replace(/^\p{Emoji}\s*/u, '');
}

function messageSpeaker(msg: CourtMessage) {
  if (msg.type === 'emperor') return '👑 皇帝';
  if (msg.type === 'decree') return '⚡ 天命';
  if (msg.type === 'scene') return '📖 场景';
  if (msg.type === 'summary') return '📜 结论';
  return msg.name || msg.official_name || '官员';
}

function messageClass(msg: CourtMessage) {
  return msg.type || 'official';
}

function emotionFor(id: string) {
  return [...messages.value].reverse().find((msg) => msg.official_id === id)?.emotion || '';
}

onUnmounted(() => stopAutoAdvance());
</script>

<style scoped>
.court-panel {
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.court-panel h2 {
  margin: 2px 0 6px;
  font-size: 18px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.section-title {
  margin-bottom: 5px;
  font-weight: 700;
}

.section-head {
  margin-bottom: 8px;
}

.form-grid {
  min-width: 0;
}

.form-grid > * {
  min-width: 0;
  max-width: 100%;
}

.topic-list {
  gap: 6px;
  max-width: 100%;
}

.topic-list :deep(.ant-btn) {
  max-width: 100%;
  height: auto;
  min-height: 24px;
  white-space: normal;
  text-align: left;
}

.topic-list :deep(.ant-btn > span) {
  white-space: normal;
  overflow-wrap: anywhere;
}

.court-panel :deep(.ant-input) {
  max-width: 100%;
}

.official-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  gap: 8px;
  min-width: 0;
}

.official-card {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding: 9px;
  text-align: left;
  color: var(--app-text);
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all .2s ease;
}

.official-card:hover,
.official-card.selected {
  border-color: #3b82f6;
  box-shadow: 0 8px 18px rgba(37, 99, 235, .12);
  transform: translateY(-1px);
}

.official-card.selected {
  background: rgba(59, 130, 246, .12);
}

.official-emoji,
.seat-emoji {
  font-size: 24px;
}

.official-info {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.official-info b,
.official-info small,
.seat-card b,
.seat-card small,
.message-speaker,
.message-content,
.message-meta {
  min-width: 0;
  overflow-wrap: anywhere;
}

.official-info small,
.seat-card small,
.message-meta {
  color: var(--app-muted);
}

.court-control {
  gap: 10px;
  align-items: flex-start;
  min-width: 0;
}

.court-control > div {
  min-width: 0;
}

.court-layout {
  display: grid;
  grid-template-columns: minmax(240px, .75fr) minmax(300px, 1.25fr);
  gap: 10px;
  min-width: 0;
  max-width: 100%;
}

.court-stage,
.message-card {
  min-width: 0;
  max-width: 100%;
}

.throne {
  display: grid;
  justify-items: center;
  gap: 4px;
  margin: 2px auto 10px;
  padding: 10px;
  max-width: 150px;
  background: linear-gradient(135deg, rgba(245, 158, 11, .22), rgba(239, 68, 68, .14));
  border: 1px solid rgba(245, 158, 11, .28);
  border-radius: 14px;
  font-size: 28px;
  font-weight: 700;
}

.throne span {
  font-size: 12px;
}

.seat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 8px;
  min-width: 0;
}

.seat-card {
  display: grid;
  justify-items: center;
  gap: 3px;
  min-width: 0;
  padding: 9px 7px;
  text-align: center;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.seat-card.speaking {
  border-color: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, .14);
}

.message-list {
  display: grid;
  gap: 8px;
  max-height: 520px;
  max-width: 100%;
  overflow: auto;
  padding-right: 3px;
}

.court-message {
  min-width: 0;
  padding: 9px 10px;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  overflow-wrap: anywhere;
}

.court-message.emperor {
  background: rgba(245, 158, 11, .12);
  border-color: rgba(245, 158, 11, .28);
}

.court-message.decree {
  background: rgba(99, 102, 241, .12);
  border-color: rgba(99, 102, 241, .28);
}

.court-message.scene,
.court-message.summary {
  background: rgba(20, 184, 166, .1);
  border-style: dashed;
}

.message-speaker {
  margin-bottom: 4px;
  font-weight: 700;
}

.message-content {
  line-height: 1.5;
  white-space: pre-wrap;
}

.command-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
}

.action-row {
  margin-top: 8px;
}

@media (max-width: 960px) {
  .court-layout,
  .command-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 560px) {
  .official-grid {
    grid-template-columns: 1fr;
  }

  .seat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .court-control :deep(.ant-space) {
    width: 100%;
  }

  .court-control :deep(.ant-space-item),
  .action-row :deep(.ant-btn) {
    max-width: 100%;
  }
}
</style>
