import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/');
          if (normalized.includes('/node_modules/vue/') || normalized.includes('/node_modules/@vue/') || normalized.includes('/node_modules/pinia/')) return 'vue';
          if (normalized.includes('/node_modules/pino/')) return 'logging';
          if (normalized.includes('/node_modules/ant-design-vue/') || normalized.includes('/node_modules/@ant-design/') || normalized.includes('/node_modules/rc-') || normalized.includes('/node_modules/@rc-component/')) return 'antd';
          if (normalized.includes('/node_modules/')) return 'vendor';
          return undefined;
        },
      },
    },
  },
});
