import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, the React app calls the backend through a relative /api path.
// Vite proxies those requests to the FastAPI server so there are no CORS
// issues and the same code works in production behind a single origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
