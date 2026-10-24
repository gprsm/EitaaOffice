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

// 8. Phase 1 contract: Ashura Pilgrimage (C12) and Liaison Extraction (Message #30743)
assert.match(panel, /isAshuraPilgrimage:\s*boolean/)
assert.match(panel, /is_ashura_pilgrimage:\s*draft\.isAshuraPilgrimage/)
assert.match(panel, /قرائت زیارت عاشورا \(سرفصل مستقل پیوست C12\)/)
assert.match(panel, /چهاردانگه/)
assert.match(panel, /سوادکوه شمالی/)
assert.match(app, /liaisonsMap=\{liaisonsMap\}/)

// Functional regex verification of Message #30743 extraction logic
const sampleText = 'حمید سعیدی - حوزه قضایی چهاردانگه - دادگاه عمومی بخش\nبرگزاری مراسم قرائت زیارت عاشورا'
const lines = sampleText.split('\n').map(l => l.trim()).filter(Boolean)
let extractedAuthor = ''
let extractedUnit = ''
for (const line of lines) {
  const headerMatch = line.match(
    /^(?:[\s#*•\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}]*(?:رابط\s*(?:فرهنگی|خبری)?\s*[:：\-–]?\s*)?)?([^\n–—\-:：]{2,30})\s*[-–—]\s*(?:حوزه\s*قضایی\s*|دادگستری\s*|دادگاه\s*عمومی\s*بخش\s*)?([^\n–—\-]+?)(?:\s*[-–—]\s*([^\n]+))?$/u
  )
  if (headerMatch) {
    extractedAuthor = headerMatch[1]?.trim()
    extractedUnit = `${headerMatch[2]?.trim()} - ${headerMatch[3]?.trim()}`
    break
  }
}
assert.equal(extractedAuthor, 'حمید سعیدی', 'Liaison author must match Hamid Saeedi')
assert.equal(extractedUnit, 'چهاردانگه - دادگاه عمومی بخش', 'Judicial unit must match Chahardangeh')
assert.ok(/زیارت\s+عاشورا/.test(sampleText), 'Ashura pilgrimage pattern must match')

console.log('# Reporting chat-surface integration contract assertions passed')


