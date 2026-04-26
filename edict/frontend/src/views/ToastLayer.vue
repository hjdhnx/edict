<template>
  <div class="toast-layer">
    <div v-for="toast in store.toasts" :key="toast.id" :class="['toast-card', toast.type]">
      {{ toast.msg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDashboardStore } from '../stores/dashboard';
const store = useDashboardStore();
</script>
