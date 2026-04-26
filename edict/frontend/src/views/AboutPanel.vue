<template>
  <div class="panel-grid about-panel">
    <a-card class="surface-card about-hero" :bordered="false">
      <div class="row-between about-hero-row">
        <div class="about-hero-copy">
          <div class="page-eyebrow">Edict · AI Agent 协作中枢</div>
          <h2>{{ ABOUT_HERO.title }}</h2>
          <p class="about-subtitle">{{ ABOUT_HERO.subtitle }}</p>
          <p class="muted about-description">{{ ABOUT_HERO.description }}</p>
        </div>
        <div class="about-version">
          <div class="kpi-label">当前版本</div>
          <div class="kpi-value">{{ versionLabel }}</div>
          <div class="kpi-hint">本地总控台 · 可信内网优先</div>
        </div>
      </div>
    </a-card>

    <div class="kpi-grid">
      <div v-for="metric in ABOUT_METRICS" :key="metric.label" class="kpi-card">
        <div class="kpi-label">{{ metric.label }}</div>
        <div class="kpi-value metric-value">{{ metric.value }}</div>
        <div class="kpi-hint">{{ metric.hint }}</div>
      </div>
    </div>

    <a-card class="surface-card" :bordered="false" title="任务治理流">
      <div class="about-flow">
        <div v-for="step in ABOUT_FLOW" :key="`${step.role}-${step.phase}`" class="about-flow-node">
          <span class="flow-icon">{{ step.icon }}</span>
          <div>
            <b>{{ step.role }} · {{ step.phase }}</b>
            <div class="muted">{{ step.action }}</div>
          </div>
        </div>
      </div>
    </a-card>

    <div class="three-col">
      <a-card v-for="section in ABOUT_SECTIONS" :key="section.title" class="surface-card about-section" :bordered="false">
        <div class="wrap-row section-head">
          <span class="section-icon">{{ section.icon }}</span>
          <div>
            <b>{{ section.title }}</b>
            <div class="muted">{{ section.subtitle }}</div>
          </div>
        </div>
        <ul class="about-list">
          <li v-for="point in section.points" :key="point">{{ point }}</li>
        </ul>
      </a-card>
    </div>

    <a-card class="surface-card" :bordered="false" title="用法速记">
      <div class="two-col">
        <div v-for="tip in ABOUT_USAGE_TIPS" :key="tip" class="about-tip">{{ tip }}</div>
      </div>
    </a-card>

    <a-alert
      class="about-alert"
      type="warning"
      show-icon
      message="使用边界"
      description="Edict 适合作为本地或可信内网的 AI Agent 工单系统。若要对外开放，请先补齐认证、权限、密钥脱敏、限流、备份和监控。"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ABOUT_FLOW, ABOUT_HERO, ABOUT_METRICS, ABOUT_SECTIONS, ABOUT_USAGE_TIPS } from '../aboutContent';
import { useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const versionLabel = computed(() => store.liveStatus?.version?.label || 'V1.0.1 20260426');
</script>

<style scoped>
.about-panel {
  min-width: 0;
}

.about-hero-row {
  align-items: stretch;
}

.about-hero-copy {
  min-width: 0;
  max-width: 980px;
}

.about-hero h2 {
  margin: 2px 0 4px;
  font-size: 24px;
  line-height: 1.15;
  letter-spacing: -.04em;
}

.about-subtitle {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 750;
  color: var(--app-text);
  overflow-wrap: anywhere;
}

.about-description {
  margin: 0;
  max-width: 860px;
  overflow-wrap: anywhere;
}

.about-version {
  flex: 0 0 220px;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface-strong);
}

.metric-value {
  font-size: 21px;
}

.about-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.about-flow-node {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: min(100%, 190px);
  flex: 1 1 190px;
  padding: 8px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface-2);
  overflow-wrap: anywhere;
}

.flow-icon,
.section-icon {
  font-size: 22px;
  line-height: 1;
}

.section-head {
  align-items: flex-start;
  margin-bottom: 6px;
}

.about-list {
  margin: 0;
  padding-left: 18px;
  color: var(--app-muted);
  display: grid;
  gap: 5px;
}

.about-list li {
  overflow-wrap: anywhere;
}

.about-tip {
  min-width: 0;
  padding: 9px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface-2);
  overflow-wrap: anywhere;
}

.about-alert {
  border-radius: 12px;
}

@media (max-width: 820px) {
  .about-hero-row {
    display: grid;
  }

  .about-version {
    flex-basis: auto;
    width: 100%;
  }
}

@media (max-width: 560px) {
  .about-hero h2 {
    font-size: 20px;
  }

  .about-subtitle {
    font-size: 14px;
  }

  .about-flow-node {
    flex-basis: 100%;
  }
}
</style>
