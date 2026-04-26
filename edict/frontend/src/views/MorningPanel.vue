<template>
  <div class="panel-grid morning-panel">
    <a-card class="surface-card" :bordered="false">
      <template #title>天下要闻</template>
      <template #extra>
        <a-space>
          <a-button @click="openConfig">订阅配置</a-button>
          <a-button @click="store.loadMorning">刷新</a-button>
          <a-button type="primary" :loading="refreshing" @click="refreshMorning">{{ refreshing ? `采集中 ${pollCount}/24` : '立即采集' }}</a-button>
        </a-space>
      </template>
      <div class="muted">{{ store.morningBrief?.generated_at ? `生成于 ${formatDashboardDateTime(store.morningBrief.generated_at)}` : store.morningBrief?.message || '暂无数据，请点击立即采集' }}</div>
    </a-card>

    <div v-if="categories.length" class="three-col">
      <a-card v-for="[name, items] in categories" :key="name" class="surface-card news-card" :bordered="false" :title="`${categoryIcon(name)} ${name}`">
        <a-list :data-source="items" size="small">
          <template #renderItem="{ item }">
            <a-list-item class="news-item">
              <div class="news-row">
                <div class="thumb-wrap">
                  <img v-if="isHttpImage(item.image) && !brokenImages.has(item.image || '')" class="news-thumb" :src="item.image" alt="" loading="lazy" @error="markBrokenImage(item.image)" />
                  <div v-else class="thumb-fallback">{{ categoryIcon(name) }}</div>
                </div>
                <div class="news-body">
                  <div class="wrap-row news-title-row">
                    <a :href="item.link" target="_blank" rel="noreferrer" class="news-title">{{ item.title }}</a>
                    <a-tag v-if="keywordHits(item)" color="warning">关注 {{ keywordHits(item) }}</a-tag>
                  </div>
                  <p class="news-summary">{{ item.summary || item.desc || '暂无摘要' }}</p>
                  <div class="news-meta">
                    <span>{{ item.source || name }}</span>
                    <span v-if="item.pub_date">{{ formatDashboardDateTime(item.pub_date) }}</span>
                  </div>
                </div>
              </div>
              <template #actions><a :href="item.link" target="_blank" rel="noreferrer">打开</a></template>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </div>
    <a-empty v-else class="surface-card empty-state" description="暂无天下要闻数据" />

    <a-modal v-model:open="showConfig" width="820px" title="订阅配置" :confirm-loading="saving" ok-text="保存配置" cancel-text="取消" @ok="saveConfig">
      <div class="config-form">
        <div>
          <div class="section-title">分类订阅</div>
          <div class="wrap-row">
            <a-checkable-tag v-for="cat in config.categories" :key="cat.name" :checked="cat.enabled" @change="cat.enabled = !cat.enabled">{{ cat.name }}</a-checkable-tag>
          </div>
        </div>

        <a-form layout="vertical">
          <a-form-item label="关键词"><a-textarea v-model:value="keywordText" :rows="3" placeholder="关键词，逗号分隔" /></a-form-item>
          <div class="webhook-grid">
            <a-form-item label="企业微信 webhook"><a-input v-model:value="config.wecom_webhook" placeholder="留空则不推送" /></a-form-item>
            <a-form-item label="飞书 webhook"><a-input v-model:value="config.feishu_webhook" placeholder="留空则不推送" /></a-form-item>
          </div>
        </a-form>

        <div>
          <div class="row-between custom-head">
            <div>
              <div class="section-title">自定义信息源</div>
              <div class="muted">保存后会随下一次采集一起抓取。</div>
            </div>
            <a-button @click="addFeed">添加信息源</a-button>
          </div>
          <div v-if="config.custom_feeds.length" class="feed-list">
            <div v-for="(feed, index) in config.custom_feeds" :key="index" class="feed-row">
              <a-input v-model:value="feed.name" placeholder="名称" />
              <a-input v-model:value="feed.url" placeholder="RSS/网页 URL" />
              <a-select v-model:value="feed.category" :options="categoryOptions" placeholder="分类" />
              <a-button danger @click="removeFeed(index)">删除</a-button>
            </div>
          </div>
          <a-empty v-else description="暂无自定义信息源" />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { api, type SubConfig } from '../api';
import { formatDashboardDateTime } from '../time';
import { useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const refreshing = ref(false);
const saving = ref(false);
const showConfig = ref(false);
const keywordText = ref('');
const pollCount = ref(0);
const brokenImages = ref(new Set<string>());
let refreshTimer: ReturnType<typeof setInterval> | null = null;
const config = reactive<SubConfig>({ categories: [], keywords: [], custom_feeds: [], wecom_webhook: '', feishu_webhook: '' });

onMounted(() => store.loadMorning());
onUnmounted(() => clearRefreshTimer());

watch(() => store.subConfig, (value) => {
  if (!value) return;
  Object.assign(config, JSON.parse(JSON.stringify({ ...value, custom_feeds: value.custom_feeds || [] })));
  keywordText.value = (value.keywords || []).join(',');
}, { immediate: true });

const enabled = computed(() => new Set((config.categories || []).filter((c) => c.enabled).map((c) => c.name)));
const keywords = computed(() => (config.keywords || []).map((item) => item.trim()).filter(Boolean));
const categories = computed(() => Object.entries(store.morningBrief?.categories || {})
  .filter(([name, items]) => (!enabled.value.size || enabled.value.has(name)) && items.length)
  .map(([name, items]) => [name, [...items].sort((a, b) => keywordHits(b) - keywordHits(a))] as const));
const categoryOptions = computed(() => (config.categories || []).map((cat) => ({ label: cat.name, value: cat.name })));

function keywordHits(item: { title?: string; summary?: string; desc?: string }) {
  const text = `${item.title || ''} ${item.summary || ''} ${item.desc || ''}`.toLowerCase();
  return keywords.value.filter((keyword) => text.includes(keyword.toLowerCase())).length;
}

function categoryIcon(name: string) {
  return name.includes('AI') ? '🤖' : name.includes('军事') ? '🛡️' : name.includes('经济') ? '📈' : '📰';
}

function isHttpImage(image?: string) {
  return !!image && /^https?:\/\//i.test(image);
}

function markBrokenImage(image?: string) {
  if (!image) return;
  brokenImages.value = new Set([...brokenImages.value, image]);
}

function openConfig() {
  showConfig.value = true;
  if (!store.subConfig) store.loadSubConfig();
}

function addFeed() {
  config.custom_feeds.push({ name: '', url: '', category: config.categories[0]?.name || '综合' });
}

function removeFeed(index: number) {
  config.custom_feeds.splice(index, 1);
}

function clearRefreshTimer() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = null;
}

async function refreshMorning() {
  if (refreshing.value) return;
  const previousGeneratedAt = store.morningBrief?.generated_at || '';
  refreshing.value = true;
  pollCount.value = 0;
  clearRefreshTimer();
  const r = await api.refreshMorning();
  store.toast(r.ok ? r.message || '采集已触发' : r.error || '采集失败', r.ok ? 'ok' : 'err');
  if (!r.ok) {
    refreshing.value = false;
    return;
  }
  refreshTimer = setInterval(async () => {
    pollCount.value += 1;
    await store.loadMorning();
    const nextGeneratedAt = store.morningBrief?.generated_at || '';
    const updated = !!nextGeneratedAt && nextGeneratedAt !== previousGeneratedAt;
    if (updated || pollCount.value >= 24) {
      clearRefreshTimer();
      refreshing.value = false;
      store.toast(updated ? '天下要闻已更新' : '采集仍在进行，请稍后刷新查看', updated ? 'ok' : 'err');
    }
  }, 5000);
}

async function saveConfig() {
  saving.value = true;
  const payload: SubConfig = {
    categories: config.categories || [],
    keywords: keywordText.value.split(/[，,]/).map((x) => x.trim()).filter(Boolean),
    custom_feeds: (config.custom_feeds || []).filter((feed) => feed.name.trim() && feed.url.trim()),
    wecom_webhook: config.wecom_webhook || '',
    feishu_webhook: config.feishu_webhook || '',
    enabled: config.enabled ?? true,
  };
  const r = await api.saveMorningConfig(payload);
  saving.value = false;
  store.toast(r.ok ? '配置已保存' : r.error || '保存失败', r.ok ? 'ok' : 'err');
  if (!r.ok) return;
  showConfig.value = false;
  await store.loadMorning();
}
</script>

<style scoped>
.morning-panel :deep(.ant-card-extra) {
  max-width: 100%;
}

.news-card :deep(.ant-list-item) {
  align-items: flex-start;
}

.news-item {
  gap: 6px;
}

.news-row {
  display: flex;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.thumb-wrap {
  flex: 0 0 76px;
  width: 76px;
  height: 54px;
  overflow: hidden;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 10px;
}

.news-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-fallback {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  font-size: 22px;
}

.news-body {
  min-width: 0;
}

.news-title {
  display: block;
  color: var(--app-text);
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.news-summary {
  margin: 4px 0;
  color: var(--app-muted);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.news-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  color: var(--app-muted);
  font-size: 11px;
}

.config-form {
  display: grid;
  gap: 12px;
}

.section-title {
  margin-bottom: 6px;
  font-weight: 700;
}

.webhook-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.custom-head {
  margin-bottom: 8px;
  gap: 8px;
}

.feed-list {
  display: grid;
  gap: 7px;
}

.feed-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr) minmax(120px, .7fr) auto;
  gap: 6px;
}

@media (max-width: 820px) {
  .webhook-grid,
  .feed-row {
    grid-template-columns: 1fr;
  }

  .news-row {
    gap: 7px;
  }

  .thumb-wrap {
    flex-basis: 64px;
    width: 64px;
    height: 48px;
  }
}
</style>
