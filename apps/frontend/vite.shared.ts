import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import type { UserConfig } from 'vite';

// apps/frontend/vite.shared.ts → repo root is two levels up
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const sharedSrc = path.resolve(repoRoot, 'packages/shared/src');

export function createPortalViteConfig(appDir: string): UserConfig {
  const envDir = fs.existsSync(path.resolve(appDir, '.env'))
    ? appDir
    : fs.existsSync(path.resolve(repoRoot, '.env'))
      ? repoRoot
      : appDir;

  return {
    envDir,
    plugins: [
      react(),
      tailwindcss(),
      {
        name: 'copy-unbundled-src-assets',
        apply: 'build',
        closeBundle(error?: Error): void {
          if (error) return;
          const distDir = path.resolve(appDir, 'dist');
          const srcAssets = path.resolve(sharedSrc, 'assets');
          const distAssets = path.resolve(distDir, 'src/assets');
          if (fs.existsSync(distDir) && fs.existsSync(srcAssets)) {
            fs.cpSync(srcAssets, distAssets, { recursive: true, force: true });
          }
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(appDir, 'src'),
        '@taragold/shared': sharedSrc,
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
}