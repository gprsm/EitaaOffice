import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '..')

const card = fs.readFileSync(path.join(uiRoot, 'src', 'MessageContentCard.tsx'), 'utf8')
const panel = fs.readFileSync(path.join(uiRoot, 'src', 'ReportingRegistrationPanel.tsx'), 'utf8')
const app = fs.readFileSync(path.join(uiRoot, 'src', 'App.tsx'), 'utf8')
const api = fs.readFileSync(path.join(uiRoot, 'src', 'lib', 'api.ts'), 'utf8')
const fixture = fs.readFileSync(path.join(uiRoot, 'src', 'main.tsx'), 'utf8')

// 1. Message card: registered chip is text+icon (never color-only) and action button opens the panel
assert.match(card, /reportUsageByMessage\?: Record<string, ReportingWitnessStatus>/)
assert.match(card, /ثبت‌شده · /)
assert.match(card, /openReportEvent\(reportUsage\.events\[0\]\.event_id\)/)
assert.match(card, /openRegistration\(members\.map\(item => item\.id\)/)
assert.match(card, /ثبت در گزارش/)
assert.match(card, /export function authorLabel/)

// 2. Client: batched witness-status call
assert.match(api, /export async function fetchReportingWitnessStatus/)
assert.match(api, /\/api\/v3\/reporting\/witness-status\?/)

// 3. Registration panel: steps, draft autosave+restore, jalali reference engine, etag conflict surface, author and date inference
assert.match(panel, /Stepper/)
assert.match(panel, /localStorage\.setItem\(storageKey, JSON\.stringify\(draft\)\)/)
assert.match(panel, /بازیابی/)
assert.match(panel, /parseJalaliDate/)
assert.match(panel, /inferRegistrationDefaults/)
assert.match(panel, /author: string/)
assert.match(panel, /نویسنده \/ رابط/)
assert.match(panel, /مشخصات استخراج‌شده از پیام ایتا/)
assert.match(panel, /ثبت (?:پیش‌نویس و پیوند شاهدان|رویداد و ارسال جهت بررسی)/)
assert.match(panel, /existing_event_id/)

// 4. App wiring: batched fetch effect, panel render, refresh after registration, sourceMessage propagation
assert.match(app, /fetchReportingWitnessStatus\(dialog\.peer_key, ids\)/)
assert.match(app, /ReportingRegistrationPanel = lazy\(/)
assert.match(app, /sourceMessage=\{registrationPanel\.sourceMessage\}/)
assert.match(app, /setReportUsageRefresh\(value => value \+ 1\)/)

// 6. Liaison author dialog, standardized display format, and app integration
const liaisonDialog = fs.readFileSync(path.join(uiRoot, 'src', 'components', 'LiaisonAuthorDialog.tsx'), 'utf8')
assert.match(card, /حوزه قضایی \$\{matchedLiaison\.unit_display_name\}/)
assert.match(card, /رابط فرهنگی/)
assert.match(liaisonDialog, /\/api\/v3\/reporting\/liaisons\/profile/)
assert.match(liaisonDialog, /\/api\/v3\/reporting\/liaisons\/assign-author/)
assert.match(liaisonDialog, /\/api\/v3\/reporting\/liaisons\/unlink-author/)
assert.match(liaisonDialog, /ارسال پیام خصوصی به رابط/)
assert.match(app, /LiaisonAuthorDialog/)
assert.match(app, /onAuthorClick/)

// 7. Message splits and dual indicators (Macro & Micro) contract
assert.match(card, /تفکیک پیام/)
assert.match(card, /CallSplitRounded/)
assert.match(card, /fontWeight:\s*700/) // Macro indicator must be bold
assert.match(card, /fontWeight:\s*400/) // Micro indicators must NOT be bold
assert.match(card, /color="secondary"/) // Micro indicators different color
assert.match(card, /onOpenSplitDialog/)
assert.match(card, /onOpenMacroSelect/)
assert.match(card, /onOpenMicroEdit/)

// Verify indicator components existence and integration
assert.match(app, /SplitMessageDialog/)
assert.match(app, /MacroIndicatorSelectPopover/)
assert.match(app, /MicroIndicatorEditPopover/)
assert.match(app, /MicroIndicatorsManagementModal/)
assert.match(app, /buildMessageGroupLookup\(indexedMessages,\s*\{[\s\S]*detachedMessageIds/)

// Verify ReportingRegistrationPanel connects to macro and micro indicators
assert.match(panel, /macroIndicator/)
assert.match(panel, /microIndicators/)
assert.match(panel, /macro_indicator:\s*draft\.macroIndicator/)
assert.match(panel, /micro_indicators:\s*draft\.microIndicators/)

console.log('# Reporting chat-surface integration contract assertions passed')


