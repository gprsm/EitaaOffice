import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// پرتال زیر زیرمسیر آپاچی لاراگون سرو می‌شود؛ base باید مطابق آن باشد.
export default defineConfig({
  plugins: [react()],
  base: '/cultural-portal/app/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
