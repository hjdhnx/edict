<template>
  <div class="panel-grid template-panel">
    <div class="row-between"><a-segmented v-model:value="store.tplCatFilter" :options="categories" /></div>
    <div class="card-list">
      <a-card v-for="tpl in filtered" :key="tpl.id" class="surface-card" :bordered="false">
        <div class="wrap-row">
          <span style="font-size: 24px">{{ tpl.icon }}</span>
          <div>
            <b>{{ tpl.name }}</b>
            <div class="muted">{{ tpl.cat }} · {{ tpl.est }} · {{ tpl.cost }}</div>
          </div>
        </div>
        <p class="muted" style="margin-top: 7px">{{ tpl.desc }}</p>
        <div class="wrap-row"><a-tag v-for="dept in tpl.depts" :key="dept">{{ dept }}</a-tag></div>
        <a-button style="margin-top: 8px" type="primary" @click="openTemplate(tpl)">使用模板</a-button>
      </a-card>
    </div>

    <a-modal v-model:open="showForm" width="820px" :title="currentTpl ? `使用模板：${currentTpl.name}` : '使用模板'" :confirm-loading="submitting" ok-text="下旨执行" cancel-text="取消" @ok="submitTemplate">
      <template v-if="currentTpl">
        <div class="template-summary">
          <div class="template-icon">{{ currentTpl.icon }}</div>
          <div>
            <b>{{ currentTpl.name }}</b>
            <p class="muted">{{ currentTpl.desc }}</p>
            <div class="wrap-row">
              <a-tag v-for="dept in currentTpl.depts" :key="dept">{{ dept }}</a-tag>
              <a-tag>{{ currentTpl.est }}</a-tag>
              <a-tag>{{ currentTpl.cost }}</a-tag>
            </div>
          </div>
        </div>

        <a-form layout="vertical" class="template-form">
          <a-form-item v-for="param in currentTpl.params" :key="param.key" :label="`${param.label}${param.required ? ' *' : ''}`">
            <a-select v-if="param.type === 'select'" v-model:value="params[param.key]" :options="(param.options || []).map((value) => ({ label: value, value }))" />
            <a-textarea v-else-if="param.type === 'textarea'" v-model:value="params[param.key]" :rows="3" />
            <a-input v-else v-model:value="params[param.key]" />
          </a-form-item>
          <div class="template-meta-grid">
            <a-form-item label="目标部门"><a-select v-model:value="targetDept" :options="deptOptions" /></a-form-item>
            <a-form-item label="优先级"><a-select v-model:value="priority" :options="priorityOptions" /></a-form-item>
          </div>
        </a-form>

        <div class="preview-block">
          <div class="row-between">
            <b>旨意预览</b>
            <a-tag>{{ preview.length }} 字</a-tag>
          </div>
          <div class="code-block">{{ preview }}</div>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { api } from '../api';
import { DEPTS, TEMPLATES, TPL_CATS, type Template, useDashboardStore } from '../stores/dashboard';

const store = useDashboardStore();
const categories = computed(() => TPL_CATS.map((c) => ({ label: `${c.icon} ${c.name}`, value: c.name })));
const filtered = computed(() => TEMPLATES.filter((tpl) => store.tplCatFilter === '全部' || tpl.cat === store.tplCatFilter));
const showForm = ref(false);
const submitting = ref(false);
const currentTpl = ref<Template | null>(null);
const params = reactive<Record<string, string>>({});
const targetDept = ref('bingbu');
const priority = ref('normal');

const deptOptions = computed(() => DEPTS.map((dept) => ({ label: `${dept.emoji} ${dept.label}`, value: dept.id })));
const priorityOptions = [
  { label: '普通', value: 'normal' },
  { label: '较高', value: 'high' },
  { label: '紧急', value: 'urgent' },
];
const preview = computed(() => {
  if (!currentTpl.value) return '';
  return currentTpl.value.command.replace(/\{(\w+)\}/g, (_, key) => params[key] || `{${key}}`);
});

function openTemplate(tpl: Template) {
  currentTpl.value = tpl;
  Object.keys(params).forEach((key) => delete params[key]);
  tpl.params.forEach((param) => {
    params[param.key] = param.default || param.options?.[0] || '';
  });
  targetDept.value = mapDeptName(tpl.depts[0]) || 'bingbu';
  priority.value = 'normal';
  showForm.value = true;
}

function mapDeptName(name: string | undefined) {
  if (!name) return '';
  return DEPTS.find((dept) => dept.label === name || dept.id === name)?.id || '';
}

async function submitTemplate() {
  const tpl = currentTpl.value;
  if (!tpl) return;
  const missing = tpl.params.find((param) => param.required && !String(params[param.key] || '').trim());
  if (missing) {
    store.toast(`请填写必填参数：${missing.label}`, 'err');
    return;
  }

  submitting.value = true;
  try {
    const status = await api.agentsStatus().catch(() => null);
    if (status && status.gateway && !status.gateway.alive) {
      store.toast('Agent 网关当前不可用，已继续尝试下旨', 'err');
    }
    const r = await api.createTask({
      title: preview.value,
      org: '皇上',
      targetDept: targetDept.value,
      priority: priority.value,
      templateId: tpl.id,
      params: { ...params },
    });
    if (!r.ok) {
      store.toast(r.error || '下旨失败', 'err');
      return;
    }
    store.toast(r.taskId ? `已下旨：${r.taskId}` : '已下旨', 'ok');
    showForm.value = false;
    await store.loadAll();
    store.setActiveTab('edicts');
    if (r.taskId) store.modalTaskId = r.taskId;
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.template-summary {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: var(--app-surface-strong);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  overflow-wrap: anywhere;
}

.template-icon {
  font-size: 28px;
}

.template-form {
  margin-top: 10px;
}

.template-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.preview-block {
  display: grid;
  gap: 7px;
  margin-top: 2px;
}

@media (max-width: 720px) {
  .template-meta-grid {
    grid-template-columns: 1fr;
  }

  .template-summary {
    align-items: flex-start;
  }
}
</style>
