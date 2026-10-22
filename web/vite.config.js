import { defineConfig, searchForWorkspaceRoot } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // The worker visit form reuses the mobile app's risk model (mobile/app/services + mobile/app/ml),
  // which references React Native's __DEV__ global.
  define: {
    __DEV__: JSON.stringify(mode === 'development'),
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    fs: {
      allow: [searchForWorkspaceRoot(process.cwd()), '../mobile/app/services', '../mobile/app/ml'],
    },
  },
}));
