import { execSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// استقرار باندل ساخته‌شده در پرتال لاراگون (F-097)
const here = dirname(fileURLToPath(import.meta.url))
const dist = join(here, '..', 'dist')
const target = 'c:/Users/mohse/laragon/www/cultural-portal/app'

if (!existsSync(dist)) {
  console.error('dist not found — run vite build first')
  process.exit(1)
}
rmSync(target, { recursive: true, force: true })
mkdirSync(target, { recursive: true })
cpSync(dist, target, { recursive: true })
console.log('deployed SPA bundle to', target)
