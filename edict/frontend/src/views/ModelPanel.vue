<template>
  <div class="panel-grid model-panel">
    <a-alert :type="sourceOk ? 'success' : 'info'" show-icon :message="sourceOk ? '模型来源：AstrBot 当前配置' : '模型来源：本地/降级配置'" :description="store.agentConfig?.modelSourceMessage" />
    <div class="card-list">
      <a-card v-for="agent in store.agentConfig?.agents || []" :key="agent.id" class="surface-card" :bordered="false">
        <div class="row-between">
          <div class="wrap-row"><span style="font-size: 24px">{{ agent.emoji || '🏛️' }}</span><div><b>{{ agent.label }}</b><div class="muted">{{ agent.role }} · {{ agent.id }}</div></div></div>
          <a-tag v-if="agent.model.startsWith('astrbot-config:')" color="success">AstrBot 生效</a-tag>
        </div>
        <div class="muted" style="margin: 8px 0">当前：<b>{{ agent.model }}</b></div>
        <a-select v-model:value="selection[agent.id]" style="width: 100%">
          <a-select-option v-for="model in models" :key="model.id" :value="model.id">{{ model.label }} ({{ model.provider }}){{ model.source === 'astrbot-configs' ? ' · 当前 AstrBot' : '' }}</a-select-option>
        </a-select>
        <a-space style="margin-top: 8px">
          <a-button type="primary" :disabled="selection[agent.id] === agent.model" :loading="savingAgent === agent.id" @click="applyModel(agent.id)">应用</a-button>
          <a-button @click="selection[agent.id] = agent.model">重置</a-button>
        </a-space>
        <div v-if="status[agent.id]" class="muted inline-status">{{ status[agent.id] }}</div>
      </a-card>
    </div>
    <a-card class="surface-card" :bordered="false" title="派发渠道">
      <p class="muted">选择系统下发 Agent 任务时使用的通知渠道，保存后立即影响后续派发。</p>
      <a-space wrap>
        <a-select v-model:value="channel" style="width: 220px">
          <a-select-option value="wecom">企业微信 WeCom</a-select-option>
          <a-select-option value="telegram">Telegram</a-select-option>
          <a-select-option value="discord">Discord</a-select-option>
          <a-select-option value="slack">Slack</a-select-option>
          <a-select-option value="signal">Signal</a-select-option>
          <a-select-option value="tui">TUI (终端)</a-select-option>
        </a-select>
        <a-button type="primary" :disabled="channel === (store.agentConfig?.dispatchChannel || 'wecom')" :loading="savingChannel" @click="applyChannel">应用</a-button>
      </a-space>
      <div v-if="channelStatus" class="muted inline-status">{{ channelStatus }}</div>
    </a-card>
    <a-card class="surface-card" :bordered="false" title="变更日志">
      <a-empty v-if="!store.changeLog.length" description="暂无模型变更记录" />
      <a-timeline v-else>
        <a-timeline-item v-for="entry in [...store.changeLog].reverse().slice(0, 20)" :key="entry.at + entry.agentId">
          {{ formatDashboardDateTime(entry.at) }} · {{ entry.agentId }}：{{ entry.oldModel }} → {{ entry.newModel }} <a-tag v-if="entry.rolledBack" color="warning">已回滚</a-tag>
        </a-timeline-item>
      </a-timeline>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { api, type KnownModel } from '../api';
import { formatDashboardDateTime } from '../time';
import { useDashboardStore } from '../stores/dashboard';
const FALLBACK_MODELS: KnownModel[] = [
  { id: 'anthropic/claude-sonnet-4-6', label: 'Claude Sonnet 4.6', provider: 'Anthropic' },
  { id: 'anthropic/claude-opus-4-7', label: 'Claude Opus 4.7', provider: 'Anthropic' },
  { id: 'anthropic/claude-haiku-4-5', label: 'Claude Haiku 4.5', provider: 'Anthropic' },
  { id: 'openai/gpt-4o', label: 'GPT-4o', provider: 'OpenAI' },
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o mini', provider: 'OpenAI' },
  { id: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro', provider: 'Google' },
  { id: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash', provider: 'Google' },
  { id: 'copilot/gpt-4.1', label: 'Copilot GPT-4.1', provider: 'Copilot' },
  { id: 'copilot/claude-sonnet-4', label: 'Copilot Claude Sonnet 4', provider: 'Copilot' },
];
const store = useDashboardStore();
const selection = reactive<Record<string, string>>({});
const status = reactive<Record<string, string>>({});
const channel = ref('wecom');
const channelStatus = ref('');
const savingAgent = ref('');
const savingChannel = ref(false);
onMounted(() => store.loadAgentConfig());
watch(() => store.agentConfig, (cfg) => { if (!cfg) return; cfg.agents.forEach((a) => (selection[a.id] = a.model)); channel.value = cfg.dispatchChannel || 'wecom'; }, { immediate: true });
const sourceOk = computed(() => store.agentConfig?.modelSource === 'astrbot-configs');
const models = computed(() => store.agentConfig?.knownModels?.length ? store.agentConfig.knownModels : FALLBACK_MODELS);
async function applyModel(agentId: string) {
  savingAgent.value = agentId;
  const r = await api.setModel(agentId, selection[agentId]);
  savingAgent.value = '';
  status[agentId] = r.ok ? r.message || '模型配置已保存' : r.error || '保存失败';
  store.toast(status[agentId], r.ok ? 'ok' : 'err');
  store.loadAgentConfig();
}
async function applyChannel() {
  savingChannel.value = true;
  const r = await api.setDispatchChannel(channel.value);
  savingChannel.value = false;
  channelStatus.value = r.ok ? r.message || '派发渠道已保存' : r.error || '保存失败';
  store.toast(channelStatus.value, r.ok ? 'ok' : 'err');
  store.loadAgentConfig();
}
</script>

<style scoped>
.inline-status {
  margin-top: 7px;
  overflow-wrap: anywhere;
}

.model-panel :deep(.ant-timeline-item-content) {
  overflow-wrap: anywhere;
}
</style>
