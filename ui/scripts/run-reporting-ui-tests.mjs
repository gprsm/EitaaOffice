import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '..')

const workbench = fs.readFileSync(path.join(uiRoot, 'src', 'ReportingWorkbench.tsx'), 'utf8')
const nav = fs.readFileSync(path.join(uiRoot, 'src', 'WorkspaceNavigation.tsx'), 'utf8')
const app = fs.readFileSync(path.join(uiRoot, 'src', 'App.tsx'), 'utf8')

// 1. ReportingWorkbench contract
assert.match(workbench, /export function ReportingWorkbench/)
assert.match(workbench, /صف بازبینی هوشمند/)
assert.match(workbench, /کاربرگ‌های هفت‌گانه/)
assert.match(workbench, /پیش‌نمایش تجمیع و صدور اکسل/)
assert.match(workbench, /تنظیمات رصد گفتگوها/)
assert.match(workbench, /ashura_pilgrimage/)
assert.match(workbench, /unresolved_star/)
assert.match(workbench, /allow_unresolved_star/)
assert.match(workbench, /\/api\/v2\/reporting\/candidates/)
assert.match(workbench, /\/api\/v2\/reporting\/forms/)
assert.match(workbench, /\/api\/v2\/reporting\/export/)
assert.match(workbench, /\/api\/v2\/reporting\/config/)

// 2. WorkspaceNavigation wiring
assert.match(nav, /onReporting\?: \(\) => void/)
assert.match(nav, /SummarizeRounded/)
assert.match(nav, /سامانه گزارش‌های فرهنگی ۱۴۰۵/)

// 3. App.tsx wiring
assert.match(app, /const ReportingWorkbench = lazy\(/)
assert.match(app, /const \[reportingOpen, setReportingOpen\] = useState\(false\)/)
assert.match(app, /onReporting=\{\(\) => setReportingOpen\(true\)\}/)
assert.match(app, /<Dialog open=\{reportingOpen\} fullScreen onClose=\{\(\) => setReportingOpen\(false\)\}>/)
assert.match(app, /<ReportingWorkbench onClose=\{\(\) => setReportingOpen\(false\)\} \/>/)

console.log('# Reporting UI and Navigation integration contract assertions passed')
