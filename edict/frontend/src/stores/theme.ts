import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import { theme } from 'ant-design-vue';

const STORAGE_KEY = 'edict-theme-mode';

type ThemeMode = 'light' | 'dark';

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>((localStorage.getItem(STORAGE_KEY) as ThemeMode) || 'dark');
  const isDark = computed(() => mode.value === 'dark');
  const algorithm = computed(() => (isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm));
  const themeConfig = computed(() => ({
    algorithm: algorithm.value,
    token: {
      colorPrimary: '#2563eb',
      borderRadius: 8,
      fontSize: 13,
      fontSizeSM: 12,
      lineHeight: 1.42,
      controlHeight: 30,
      controlHeightSM: 26,
      controlPaddingHorizontal: 10,
      controlPaddingHorizontalSM: 8,
      padding: 12,
      paddingSM: 8,
      paddingXS: 6,
      margin: 12,
      marginSM: 8,
      marginXS: 6,
      fontFamily: 'Inter, "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      colorBgLayout: isDark.value ? '#0f172a' : '#f5f7fb',
      colorBgContainer: isDark.value ? '#111827' : '#ffffff',
    },
  }));

  function toggleTheme() {
    mode.value = isDark.value ? 'light' : 'dark';
  }

  watch(
    mode,
    (value) => {
      localStorage.setItem(STORAGE_KEY, value);
      document.documentElement.dataset.theme = value;
      document.documentElement.classList.toggle('dark', value === 'dark');
    },
    { immediate: true },
  );

  return { mode, isDark, themeConfig, toggleTheme };
});
