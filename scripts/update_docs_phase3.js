const fs = require('fs');
const date = '2026-08-21';

// 1. Report
const reportPath = 'docs/reports/features/PHASE_3_HEADER_COMPOSER_ICONS_REPORT_' + date + '.md';
const reportContent = `# گزارش فاز ۳ — بهبودهای Header، جلوگیری از باز شدن ناخواسته Composer و آیکون اختصاصی

تاریخ: ${date}
وضعیت: \`COMPLETED / FULL_AUTOMATED_VERIFIED\`

در این فاز سه تغییر عمده در رابط کاربری انجام شد:

## ۳.۱. جستجوی جمع‌شوندهٔ Header (Overlay Search)
جستجوی ثابت پیام از هدر حذف شد و به شکل یک دکمهٔ ذره‌بین درآمده است. با کلیک روی آن، یک \`HeaderMessageSearch\` شامل نوار جستجوی تمام‌عرض (Overlay) نمایش داده می‌شود. کلیک در بیرون، فشردن Escape، و یا اسکرول لیست پیام‌ها، بدون از بین بردن متن تایپ‌شده، نوار را می‌بندد.

## ۳.۲. عدم بازگشایی خودکار Composer برای پیام‌های استفاده‌شده
در گذشته، انتخاب یک پیام که قبلاً در پست‌ها استفاده شده بود، باعث باز شدن فوری \`Composer\` و نمایش سوابق می‌شد. این رفتار مزاحم حذف شد. اکنون:
- انتخاب پیام‌های استفاده‌شده \`Composer\` را باز نمی‌کند.
- کامپوننت مستقلِ \`UsageInfoDialog\` برای نمایش سوابق توسعه داده شد.

## ۳.۳. آیکون وردپرس
آیکون موقت \`PublicRounded\` (کره زمین) از سراسر اپلیکیشن جمع‌آوری شد و کامپوننت \`WordPressIcon\` شامل SVG اختصاصی جایگزین آن گردید.

## Validation
- \`npm run check\` و تایپ‌اسکریپت: بدون خطا.
- افزودن ۳ آزمون RED در \`run-phase9-workspace-tests.mjs\` و پاس شدن کامل (15/15).
`;
fs.writeFileSync(reportPath, reportContent);

// 2. FINDINGS_REGISTER.md
const findingsPath = 'docs/project-memory/FINDINGS_REGISTER.md';
let findings = fs.readFileSync(findingsPath, 'utf8');
findings += `
### F-034 — Phase 3: Header Search Overlay, independent UsageInfoDialog, and WordPressIcon

- وضعیت: \`CLOSED / FIXED / FULL_AUTOMATED_VERIFIED\`
- تاریخ: ${date}
- شدت: تجربه‌کاربری / رابط‌کاربری
- اقدام: توسعه HeaderMessageSearch، جداسازی UsageInfoDialog از Composer و تعویض سراسری PublicRounded.
- شاهد: تست‌های 3.1, 3.2 و 3.3 در \`run-phase9-workspace-tests.mjs\` همگی PASSED.
- گزارش: \`../reports/features/PHASE_3_HEADER_COMPOSER_ICONS_REPORT_${date}.md\`
`;
fs.writeFileSync(findingsPath, findings);

// 3. VALIDATION_LEDGER.md
const validationPath = 'docs/project-memory/VALIDATION_LEDGER.md';
let validation = fs.readFileSync(validationPath, 'utf8');
validation += `
## ${date} - Phase 3 (Header Search, Composer Fix, WP Icon)

- **هدف:** اجرای کامل فاز ۳ شامل ۳ ریزفاز.
- **تغییرات:** افزودن HeaderMessageSearch، UsageInfoDialog، WordPressIcon.
- **نتیجه:**
  - TypeScript \`check\`: **موفق**
  - UI Unit Tests: **موفق (15/15)**
- **وضعیت نهایی:** \`GREEN / PRODUCTION_READY\`
`;
fs.writeFileSync(validationPath, validation);

// 4. CURRENT_SYSTEM_BASELINE.md
const baselinePath = 'docs/project-memory/CURRENT_SYSTEM_BASELINE.md';
let baseline = fs.readFileSync(baselinePath, 'utf8');
baseline = baseline.replace(
  '- [ ] فاز ۳ (هدر، جستجو، و آیکون‌ها)',
  '- [x] فاز ۳ (هدر، جستجو، و آیکون‌ها)'
);
fs.writeFileSync(baselinePath, baseline);
