import path from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vite';
import { createPortalViteConfig } from '../vite.shared.ts';

const appDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(() => createPortalViteConfig(appDir));