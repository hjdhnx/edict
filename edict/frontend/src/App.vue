<template>
  <a-config-provider :theme="themeStore.themeConfig" :locale="zhCN" component-size="small">
    <div class="app-shell">
      <aside :class="['app-sidebar', { open: mobileNavOpen, collapsed: sidebarCollapsed }]">
        <div class="brand-block">
          <div class="brand-mark">E</div>
          <div class="brand-copy">
            <div class="brand-title">三省六部总控台</div>
            <div class="brand-sub">Edict · AI Agent 协作中枢</div>
          </div>
        </div>
        <a-button class="sidebar-collapse-btn" type="text" :title="sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '›' : '‹' }}
        </a-button>
        <a-menu
          class="side-menu"
          mode="inline"
          :selected-keys="[store.activeTab]"
          :inline-collapsed="sidebarCollapsed"
          @click="handleMenuClick"
        >
          <a-menu-item v-for="tab in TAB_DEFS" :key="tab.key" :title="tab.label">
            <span class="menu-icon">{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
            <a-badge v-if="tabBadge(tab.key)" class="menu-badge" :count="tabBadge(tab.key)" />
          </a-menu-item>
        </a-menu>
      </aside>

      <div class="mobile-mask" v-if="mobileNavOpen" @click="mobileNavOpen = false" />

      <main class="app-main">
        <header class="topbar">
          <div class="topbar-left">
            <a-button class="mobile-menu-btn" type="text" @click="mobileNavOpen = true">
              <MenuOutlined />
            </a-button>
            <div class="topbar-title">
              <div class="page-eyebrow">三省六部总控台 · {{ activeTabMeta?.icon }} {{ activeTabMeta?.label }}</div>
              <h1>{{ pageTitle }}</h1>
              <div class="version-line">{{ versionLabel }}</div>
            </div>
          </div>
          <div class="topbar-actions">
            <a-tag :color="syncOk ? 'success' : syncOk === false ? 'error' : 'processing'">
              {{ syncOk ? '同步正常' : syncOk === false ? '服务器未启动' : '连接中' }}
            </a-tag>
            <a-statistic class="mini-stat" title="活跃旨意" :value="store.activeEdicts.length" />
            <a-button @click="store.loadAll">刷新 · {{ store.countdown }}s</a-button>
            <a-switch
              :checked="themeStore.isDark"
              checked-children="夜"
              un-checked-children="昼"
              @change="themeStore.toggleTheme"
            />
          </div>
        </header>

        <section class="content-area">
          <EdictBoard v-if="store.activeTab === 'edicts'" />
          <CourtPanel v-else-if="store.activeTab === 'court'" />
          <MonitorPanel v-else-if="store.activeTab === 'monitor'" />
          <OfficialsPanel v-else-if="store.activeTab === 'officials'" />
          <ModelPanel v-else-if="store.activeTab === 'models'" />
          <SkillsPanel v-else-if="store.activeTab === 'skills'" />
          <SessionsPanel v-else-if="store.activeTab === 'sessions'" />
          <MemorialPanel v-else-if="store.activeTab === 'memorials'" />
          <TemplatePanel v-else-if="store.activeTab === 'templates'" />
          <MorningPanel v-else-if="store.activeTab === 'morning'" />
          <AboutPanel v-else-if="store.activeTab === 'about'" />
        </section>
      </main>

      <TaskDrawer />
      <ToastLayer />
    </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref } from 'vue';
import { MenuOutlined } from '@ant-design/icons-vue';
import zhCN from 'ant-design-vue/es/locale/zh_CN';
import { TAB_DEFS, type TabKey, isArchived, isEdict, useDashboardStore } from './stores/dashboard';
import { useThemeStore } from './stores/theme';

const EdictBoard = defineAsyncComponent(() => import('./views/EdictBoard.vue'));
const CourtPanel = defineAsyncComponent(() => import('./views/CourtPanel.vue'));
const MonitorPanel = defineAsyncComponent(() => import('./views/MonitorPanel.vue'));
const OfficialsPanel = defineAsyncComponent(() => import('./views/OfficialsPanel.vue'));
const ModelPanel = defineAsyncComponent(() => import('./views/ModelPanel.vue'));
const SkillsPanel = defineAsyncComponent(() => import('./views/SkillsPanel.vue'));
const SessionsPanel = defineAsyncComponent(() => import('./views/SessionsPanel.vue'));
const MemorialPanel = defineAsyncComponent(() => import('./views/MemorialPanel.vue'));
const TemplatePanel = defineAsyncComponent(() => import('./views/TemplatePanel.vue'));
const MorningPanel = defineAsyncComponent(() => import('./views/MorningPanel.vue'));
const AboutPanel = defineAsyncComponent(() => import('./views/AboutPanel.vue'));
const TaskDrawer = defineAsyncComponent(() => import('./views/TaskDrawer.vue'));
const ToastLayer = defineAsyncComponent(() => import('./views/ToastLayer.vue'));

const store = useDashboardStore();
const themeStore = useThemeStore();
const mobileNavOpen = ref(false);
const sidebarCollapsed = ref(false);

const activeTabMeta = computed(() => TAB_DEFS.find((tab) => tab.key === store.activeTab));
const versionLabel = computed(() => store.liveStatus?.version?.label || 'V1.0.1 20260426');
const pageTitle = computed(() => {
  const map: Record<TabKey, string> = {
    edicts: '旨意运行总览',
    court: '朝堂议政',
    monitor: '省部调度监控',
    officials: '官员绩效与活跃度',
    models: '模型与派发配置',
    skills: 'Agent 技能中心',
    sessions: '执行进度追踪',
    memorials: '奏折归档库',
    templates: '常用旨意模板',
    morning: '天下要闻',
    about: '关于 Edict',
  };
  return map[store.activeTab];
});
const syncOk = computed(() => store.liveStatus?.syncStatus?.ok);

function tabBadge(key: string): number | string {
  const tasks = store.tasks;
  const edicts = tasks.filter(isEdict);
  if (key === 'edicts') return edicts.filter((t) => !isArchived(t)).length;
  if (key === 'sessions') return tasks.filter((t) => isEdict(t) && !isArchived(t) && ['Taizi', 'Zhongshu', 'Menxia', 'Assigned', 'Doing', 'Next', 'Review', 'Blocked'].includes(t.state)).length;
  if (key === 'memorials') return edicts.filter((t) => ['Done', 'Cancelled'].includes(t.state)).length;
  if (key === 'monitor') return `${edicts.filter((t) => t.state !== 'Done' && t.state !== 'Next').length}活跃`;
  return '';
}

function handleMenuClick(info: { key: string | number }) {
  selectTab(info.key as TabKey);
}

function selectTab(key: TabKey) {
  store.setActiveTab(key);
  mobileNavOpen.value = false;
}

onMounted(() => {
  store.startPolling();
  store.startRealtime();
});

onUnmounted(() => {
  store.stopRealtime();
  store.stopPolling();
});
</script>
