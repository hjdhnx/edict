<template>
  <div class="panel-grid skills-panel">
    <a-card class="surface-card" :bordered="false">
      <template #title>技能配置</template>
      <template #extra>
        <a-space>
          <a-segmented v-model:value="activeSection" :options="sectionOptions" />
          <a-button v-if="activeSection === 'local'" type="primary" @click="showLocalAdd = true">新增本地技能</a-button>
          <a-button v-else type="primary" @click="showRemoteAdd = true">导入远程技能</a-button>
        </a-space>
      </template>

      <div v-if="activeSection === 'local'" class="card-list">
        <a-card v-for="agent in store.agentConfig?.agents || []" :key="agent.id" class="surface-card agent-card" :bordered="false">
          <div class="row-between agent-head">
            <div class="wrap-row">
              <span class="agent-emoji">{{ agent.emoji || '🏛️' }}</span>
              <div>
                <b>{{ agent.label }}</b>
                <div class="muted">{{ agent.id }} · {{ agent.role }} · {{ agent.skills?.length || 0 }} 个技能</div>
              </div>
            </div>
          </div>
          <a-list style="margin-top: 8px" size="small" :data-source="agent.skills || []">
            <template #renderItem="{ item }">
              <a-list-item class="skill-row" @click="openSkill(agent.id, item.name)">
                <a-list-item-meta :title="item.name" :description="item.description || item.path" />
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </div>

      <div v-else class="remote-section">
        <div class="row-between remote-toolbar">
          <div class="muted">远程技能会下载到本地 Agent 技能目录，并保留来源以便后续更新。</div>
          <a-button @click="loadRemote">刷新远程技能</a-button>
        </div>
        <a-table :pagination="false" size="small" :data-source="remoteSkills" :columns="columns" row-key="localPath">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === 'valid' ? 'success' : 'error'">{{ record.status }}</a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space>
                <a-button size="small" @click="updateRemote(record.agentId, record.skillName)">更新</a-button>
                <a-popconfirm title="确认移除这个远程技能记录？" ok-text="移除" cancel-text="取消" @confirm="removeRemote(record.agentId, record.skillName)">
                  <a-button size="small" danger>移除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>
    </a-card>

    <a-modal v-model:open="showLocalAdd" title="新增本地技能" :confirm-loading="savingLocal" ok-text="保存" cancel-text="取消" @ok="addLocal">
      <a-form layout="vertical">
        <a-form-item label="Agent" required><a-select v-model:value="localForm.agentId" :options="agentOptions" /></a-form-item>
        <a-form-item label="Skill 名称" required><a-input v-model:value="localForm.skillName" placeholder="例如：incident-review" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="localForm.description" :rows="3" /></a-form-item>
        <a-form-item label="触发方式"><a-textarea v-model:value="localForm.trigger" :rows="3" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="showRemoteAdd" width="760px" title="导入远程技能" :confirm-loading="savingRemote" ok-text="导入" cancel-text="取消" @ok="addRemote">
      <a-form layout="vertical">
        <a-form-item label="Agent" required><a-select v-model:value="remoteForm.agentId" :options="agentOptions" /></a-form-item>
        <a-form-item label="Skill 名称" required><a-input v-model:value="remoteForm.skillName" /></a-form-item>
        <a-form-item label="Source URL" required><a-input v-model:value="remoteForm.sourceUrl" placeholder="https://raw.githubusercontent.com/.../SKILL.md" /></a-form-item>
        <a-form-item label="描述"><a-textarea v-model:value="remoteForm.description" :rows="3" /></a-form-item>
      </a-form>
      <div class="preset-area">
        <div class="section-title">内置远程技能仓库快选</div>
        <div v-for="repo in communitySources" :key="repo.name" class="preset-repo">
          <div>
            <b>{{ repo.emoji }} {{ repo.name }}</b>
            <div class="muted">{{ repo.description }} · ★ {{ repo.stars }}</div>
          </div>
          <div class="wrap-row preset-buttons">
            <a-button
              v-for="skill in repo.skills"
              :key="skill.name"
              size="small"
              :loading="importingPreset === presetKey(skill)"
              :disabled="isPresetInstalled(skill)"
              @click="quickImportPreset(skill)"
            >
              {{ isPresetInstalled(skill) ? `${skill.name} 已导入` : `导入 ${skill.name}` }}
            </a-button>
          </div>
        </div>
      </div>
    </a-modal>

    <a-modal v-model:open="showContent" width="760px" :title="skillTitle" :footer="null">
      <div class="code-block">{{ skillContent }}</div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { api, type RemoteSkillItem } from '../api';
import { useDashboardStore } from '../stores/dashboard';

interface PresetSkill {
  name: string;
  url: string;
  description: string;
}

interface CommunitySource {
  name: string;
  emoji: string;
  stars: string;
  description: string;
  skills: PresetSkill[];
}

const store = useDashboardStore();
const activeSection = ref<'local' | 'remote'>('local');
const sectionOptions = [{ label: '本地技能', value: 'local' }, { label: '远程技能', value: 'remote' }];
const showLocalAdd = ref(false);
const showRemoteAdd = ref(false);
const showContent = ref(false);
const savingLocal = ref(false);
const savingRemote = ref(false);
const importingPreset = ref('');
const skillTitle = ref('');
const skillContent = ref('');
const remoteSkills = ref<RemoteSkillItem[]>([]);
const localForm = reactive({ agentId: 'bingbu', skillName: '', description: '', trigger: '' });
const remoteForm = reactive({ agentId: 'bingbu', skillName: '', sourceUrl: '', description: '' });

const columns = [
  { title: '技能', dataIndex: 'skillName' },
  { title: 'Agent', dataIndex: 'agentId' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '来源', dataIndex: 'sourceUrl', ellipsis: true },
  { title: '操作', key: 'action' },
];

const communitySources: CommunitySource[] = [
  {
    name: 'obra/superpowers',
    emoji: '⚡',
    stars: '66.9k',
    description: '完整开发工作流技能集',
    skills: [
      preset('brainstorming', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md', '结构化头脑风暴与方案发散。'),
      preset('test-driven-development', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/test-driven-development/SKILL.md', '测试驱动开发工作流。'),
      preset('systematic-debugging', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/systematic-debugging/SKILL.md', '系统化定位复杂问题。'),
      preset('subagent-driven-development', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/subagent-driven-development/SKILL.md', '用子 Agent 拆分并行开发任务。'),
      preset('writing-plans', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/writing-plans/SKILL.md', '把大任务拆成可执行计划。'),
      preset('executing-plans', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/executing-plans/SKILL.md', '按计划推进并验证实现。'),
      preset('requesting-code-review', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/requesting-code-review/SKILL.md', '请求独立代码审查。'),
      preset('root-cause-tracing', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/root-cause-tracing/SKILL.md', '追踪问题根因。'),
      preset('verification-before-completion', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/verification-before-completion/SKILL.md', '完成前进行验证。'),
      preset('dispatching-parallel-agents', 'https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/dispatching-parallel-agents/SKILL.md', '并行派发多个 Agent。'),
    ],
  },
  {
    name: 'anthropics/skills',
    emoji: '🏛️',
    stars: '官方',
    description: 'Anthropic 官方技能库',
    skills: [
      preset('docx', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/SKILL.md', 'Word 文档处理。'),
      preset('pdf', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md', 'PDF 文档处理。'),
      preset('xlsx', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/xlsx/SKILL.md', 'Excel 表格处理。'),
      preset('pptx', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/pptx/SKILL.md', 'PowerPoint 演示文稿处理。'),
      preset('mcp-builder', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/mcp-builder/SKILL.md', '构建 MCP 服务。'),
      preset('frontend-design', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md', '专业前端设计与交互打磨。'),
      preset('web-artifacts-builder', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/web-artifacts-builder/SKILL.md', '构建 Web artifacts。'),
      preset('webapp-testing', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing/SKILL.md', 'Web 应用浏览器验证与回归测试。'),
      preset('algorithmic-art', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/algorithmic-art/SKILL.md', '算法艺术创作。'),
      preset('canvas-design', 'https://raw.githubusercontent.com/anthropics/skills/main/skills/canvas-design/SKILL.md', 'Canvas 视觉设计。'),
    ],
  },
  {
    name: 'ComposioHQ/awesome-claude-skills',
    emoji: '🌐',
    stars: '39.2k',
    description: '100+ 社区精选技能',
    skills: [
      preset('github-integration', 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/github-integration/SKILL.md', 'GitHub 集成工作流。'),
      preset('data-analysis', 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/data-analysis/SKILL.md', '数据分析工作流。'),
      preset('code-review', 'https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/code-review/SKILL.md', '代码审查工作流。'),
    ],
  },
];

const agentOptions = computed(() => (store.agentConfig?.agents || []).map((agent) => ({ label: `${agent.emoji || '🏛️'} ${agent.label} (${agent.id})`, value: agent.id })));

onMounted(() => {
  store.loadAgentConfig();
  loadRemote();
});

watch(agentOptions, (options) => {
  const fallback = options[0]?.value;
  if (!fallback) return;
  if (!options.some((item) => item.value === localForm.agentId)) localForm.agentId = fallback;
  if (!options.some((item) => item.value === remoteForm.agentId)) remoteForm.agentId = fallback;
}, { immediate: true });

function preset(name: string, url: string, description: string): PresetSkill {
  return { name, url, description };
}

async function loadRemote() {
  const r = await api.remoteSkillsList();
  remoteSkills.value = r.remoteSkills || [];
}

async function openSkill(agentId: string, skillName: string) {
  const r = await api.skillContent(agentId, skillName);
  skillTitle.value = `${agentId}/${skillName}`;
  skillContent.value = r.content || r.error || '无内容';
  showContent.value = true;
}

async function addLocal() {
  if (!localForm.agentId || !localForm.skillName.trim()) {
    store.toast('请选择 Agent 并填写技能名称', 'err');
    return;
  }
  savingLocal.value = true;
  const r = await api.addSkill(localForm.agentId, localForm.skillName.trim(), localForm.description, localForm.trigger);
  savingLocal.value = false;
  store.toast(r.ok ? '本地技能已保存' : r.error || '保存失败', r.ok ? 'ok' : 'err');
  if (!r.ok) return;
  showLocalAdd.value = false;
  localForm.skillName = '';
  localForm.description = '';
  localForm.trigger = '';
  await store.loadAgentConfig();
}

function presetKey(skill: PresetSkill) {
  return `${remoteForm.agentId}:${skill.name}`;
}

function isPresetInstalled(skill: PresetSkill) {
  return remoteSkills.value.some((item) => item.agentId === remoteForm.agentId && item.skillName === skill.name);
}

function applyPreset(skill: PresetSkill) {
  remoteForm.skillName = skill.name;
  remoteForm.sourceUrl = skill.url;
  remoteForm.description = skill.description;
}

async function quickImportPreset(skill: PresetSkill) {
  if (!remoteForm.agentId) {
    store.toast('请选择 Agent', 'err');
    return;
  }
  applyPreset(skill);
  importingPreset.value = presetKey(skill);
  savingRemote.value = true;
  const r = await api.addRemoteSkill(remoteForm.agentId, skill.name, skill.url, skill.description);
  savingRemote.value = false;
  importingPreset.value = '';
  store.toast(r.ok ? '远程技能已导入' : r.error || '导入失败', r.ok ? 'ok' : 'err');
  if (!r.ok) return;
  remoteForm.skillName = '';
  remoteForm.sourceUrl = '';
  remoteForm.description = '';
  await Promise.all([store.loadAgentConfig(), loadRemote()]);
}

async function addRemote() {
  if (!remoteForm.agentId || !remoteForm.skillName.trim() || !remoteForm.sourceUrl.trim()) {
    store.toast('请选择 Agent，并填写技能名称和 Source URL', 'err');
    return;
  }
  savingRemote.value = true;
  const r = await api.addRemoteSkill(remoteForm.agentId, remoteForm.skillName.trim(), remoteForm.sourceUrl.trim(), remoteForm.description);
  savingRemote.value = false;
  store.toast(r.ok ? '远程技能已导入' : r.error || '导入失败', r.ok ? 'ok' : 'err');
  if (!r.ok) return;
  showRemoteAdd.value = false;
  remoteForm.skillName = '';
  remoteForm.sourceUrl = '';
  remoteForm.description = '';
  await Promise.all([store.loadAgentConfig(), loadRemote()]);
}

async function updateRemote(agentId: string, skillName: string) {
  const r = await api.updateRemoteSkill(agentId, skillName);
  store.toast(r.ok ? '技能已更新' : r.error || '更新失败', r.ok ? 'ok' : 'err');
  await Promise.all([store.loadAgentConfig(), loadRemote()]);
}

async function removeRemote(agentId: string, skillName: string) {
  const r = await api.removeRemoteSkill(agentId, skillName);
  store.toast(r.ok ? '技能已移除' : r.error || '移除失败', r.ok ? 'ok' : 'err');
  await Promise.all([store.loadAgentConfig(), loadRemote()]);
}
</script>

<style scoped>
.skills-panel :deep(.ant-card-extra) {
  max-width: 100%;
}

.agent-head {
  gap: 8px;
}

.agent-emoji {
  font-size: 24px;
}

.skill-row {
  cursor: pointer;
  border-radius: 10px;
}

.skill-row:hover {
  background: var(--app-surface-strong);
}

.remote-section {
  display: grid;
  gap: 10px;
}

.remote-toolbar {
  gap: 8px;
}

.section-title {
  margin: 10px 0 7px;
  font-weight: 700;
}

.preset-area {
  padding-top: 6px;
  border-top: 1px solid var(--app-border);
}

.preset-repo {
  display: grid;
  gap: 7px;
  padding: 9px;
  margin-bottom: 8px;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 11px;
  overflow-wrap: anywhere;
}

.preset-buttons {
  gap: 6px;
}
</style>
