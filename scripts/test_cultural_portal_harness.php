#!/usr/bin/env php
<?php
/**
 * هارنس آزمون عملکردی پرتال فرهنگی (F-095..F-097)
 *
 * اجرا:  .\.venv\... نه — این اسکریپت PHP است:
 *   c:/Users/mohse/laragon/bin/php/php-8.1.10-Win32-vs16-x64/php.exe scripts/test_cultural_portal_harness.php
 *
 * خودکفا: یک کپی موقت از پایگاه عملیاتی می‌سازد، روی همان کپی رویداد آزمون
 * ثبت و راستی‌آزمایی می‌کند و پایگاه عملیاتی را هرگز دست نمی‌زند.
 * مسیر پایگاه با env EITAA_REPORTING_DB قابل بازنویسی است (پیش‌فرض: پایگاه عملیاتی).
 */

declare(strict_types=1);

error_reporting(E_ALL);

$repoRoot = dirname(__DIR__);
$operationalDb = getenv('EITAA_REPORTING_DB') ?: ($repoRoot . '/data/reporting/reporting.sqlite3');
if (!file_exists($operationalDb)) {
    fwrite(STDERR, "operational DB not found: {$operationalDb}\n");
    exit(2);
}

// کپی موقت — همهٔ نوشته‌های آزمون روی کپی است
$tempDb = sys_get_temp_dir() . '/portal_harness_test_' . uniqid() . '.sqlite3';
copy($operationalDb, $tempDb);
foreach ([$tempDb . '-wal', $tempDb . '-shm'] as $side) {
    if (file_exists($side)) @unlink($side);
}

define('PORTAL_ROOT', 'c:/Users/mohse/laragon/www/cultural-portal');
define('APP_NAME', 'harness');
define('EITAA_BRIDGE_ROOT', $repoRoot);
define('REPORTING_SQLITE_PATH', $tempDb);
define('EXCEL_REPORTS_DIR', sys_get_temp_dir());
define('OFFICIAL_EXCEL_FILENAME', 'harness.xlsx');
define('OFFICIAL_EXCEL_PATH', EXCEL_REPORTS_DIR . '/harness.xlsx');
define('PYTHON_EXE_PATH', 'python');
define('WORDPRESS_ROOT', 'c:/Users/mohse/laragon/www');

require PORTAL_ROOT . '/includes/Helpers.php';
require PORTAL_ROOT . '/includes/EntryFormDefinitions.php';
require PORTAL_ROOT . '/includes/Database.php';
require PORTAL_ROOT . '/includes/MediaService.php';
require PORTAL_ROOT . '/includes/ReportingService.php';

$failures = 0;
$checks = 0;
function check(bool $cond, string $msg): void {
    global $failures, $checks;
    $checks++;
    echo ($cond ? "PASS" : "FAIL") . ": {$msg}\n";
    if (!$cond) $failures++;
}

// ---- ۱) تعاریف ۱۳ فرم اختصاصی و رندر آن‌ها --------------------------------
$refs = ['80401', '80402', '80403', '80501', '80406', '80601', '80202', '80403-A',
         'training_courses', 'content_production', 'counseling', 'education_services', 'external_collaboration'];
check(count(EntryFormDefinitions::all()) === 13, '۱۳ فرم اختصاصی تعریف شده است');
foreach ($refs as $ref) {
    $html = EntryFormDefinitions::renderProgramFields($ref);
    check($html !== null && str_contains($html, 'entry-section'), "رندر فرم اختصاصی {$ref}");
}

// ---- ۲) ستون‌های اختصاصی موضوعات کاربرگ بازدید (فاز ۳) --------------------
$cols = ReportingService::getSheetDimensionColumns('counseling');
check(count($cols) >= 1 && $cols[0]['metric'] === 'sessions_count', 'ستون اختصاصی مشاوره از فرم اختصاصی مشتق می‌شود');

// ---- ۳) ثبت رویداد تکریم با نگاشت دسته ← فکت ------------------------------
$eventId = ReportingService::createManualEvent([
    'program_kind'      => 'honor',
    'unit_name'         => 'دادگستری آزمون هارنس',
    'occurred_on'       => '2026-08-10',
    'occasion'          => 'آیین تکریم بازنشستگان (آزمون هارنس)',
    'occasion_class'    => 'standard',
    'notes'             => 'تست هارنس دائمی',
    'dim_honor_retirees_count' => '3',
    'dim_gift_count'           => '3',
    'txt_honoree_names'        => 'نمونه آزمون',
]);
$ev = ReportingService::getEventById($eventId);
check($ev !== null, 'رویداد آزمون روی کپی موقت ثبت شد');
$facts = ReportingService::getEventFactsByEvent([$eventId])[$eventId] ?? [];
check((float)($facts['honor_retirees_count']['value'] ?? 0) === 3.0, 'فکت دستهٔ تکریم (بازنشستگان=۳)');
check((float)($facts['gift_count']['value'] ?? 0) === 3.0, 'فکت هدایا');
check(str_contains((string)($ev['notes'] ?? ''), 'اسامی تقدیرشدگان (خلاصه): نمونه آزمون'), 'الصاق متن فرم به شرح رویداد');

// ---- ۴) مراسم با ردهٔ مناسبت ----------------------------------------------
$ev2 = ReportingService::createManualEvent([
    'program_kind'   => 'ceremony',
    'unit_name'      => 'دادگستری آزمون هارنس',
    'occurred_on'    => '2026-08-11',
    'occasion'       => 'مراسم آزمون ملی',
    'occasion_class' => 'national',
    'dim_culture_pack_count' => '25',
]);
$row = ReportingService::getEventById($ev2);
check(($row['occasion_class'] ?? '') === 'national', 'ردهٔ مناسبت national ذخیره می‌شود');
$facts2 = ReportingService::getEventFactsByEvent([$ev2])[$ev2] ?? [];
check((float)($facts2['culture_pack_count']['value'] ?? 0) === 25.0, 'فکت بستهٔ فرهنگی');

// ---- ۴-ب) سنجه‌های تفکیکی کاربرگ سفر استانی (نماز و تولید محتوا) -----------
$evPrayer = ReportingService::createManualEvent([
    'program_kind' => 'prayer',
    'unit_name'    => 'دادگستری آزمون هارنس',
    'occurred_on'  => '2026-08-12',
    'occasion'     => 'طرح خادمیاری و جشن نومکلفان',
    'dim_prayer_congregation_count' => '45',
    'dim_khademiari_mosque_count'   => '4',
    'dim_khademiari_honoree_count'  => '8',
    'dim_nominee_count'             => '15',
]);
$prayerFacts = ReportingService::getEventFactsByEvent([$evPrayer])[$evPrayer] ?? [];
check((float)($prayerFacts['prayer_congregation_count']['value'] ?? 0) === 45.0, 'فکت سنجه نماز جماعت کاربرگ سفر استانی');
check((float)($prayerFacts['khademiari_mosque_count']['value'] ?? 0) === 4.0, 'فکت طرح خادمیاری (نمازخانه‌ها)');
check((float)($prayerFacts['nominee_count']['value'] ?? 0) === 15.0, 'فکت جشن نومکلفان (نومکلفین)');

// ---- ۵) فیلتر ردهٔ مراسم در پرس‌وجوی رویدادها (فاز ۳) ---------------------
$relig = ReportingService::getEvents(['occasion_class' => 'religious'], 5, 0);
check(empty(array_filter($relig, fn($r) => $r['occasion_class'] !== 'religious')), 'فیلتر occasion_class=religious در getEvents');

// ---- ۶) مستندات ابلاغی سند رسمی ------------------------------------------
$tripMandates = ReportingService::getMandates('80401');
check(count($tripMandates) >= 1 && str_contains($tripMandates[0]['title'], 'دستورالعمل اجرایی برگزاری اردوهای فرهنگی زیارتی'), 'مستند ابلاغی اردو از سند رسمی');
check(count(ReportingService::getMandates('counseling')) >= 1, 'مستند ابلاغی موضوع مشاوره (کاربرگ بازدید)');
check(count(ReportingService::getMandates()) >= 15, 'رجیستری اسناد بالادستی کامل (>=15)');
$newMandate = ReportingService::createMandate([
    'program_code' => '80402', 'kind' => 'guideline', 'title' => 'سند آزمون هارنس',
]);
check(ReportingService::deleteMandate($newMandate), 'ثبت/حذف مستند ابلاغی روی کپی');

// ---- ۷) جریان ویرایش: upsert/حذف فکت با updateEvent (فاز ۱ دستور) ---------
ReportingService::updateEvent($eventId, [
    'dim_honor_retirees_count' => '7',   // تغییر مقدار موجود
    'dim_gift_count' => '0',             // حذف فکت
    'dim_honor_legends_count' => '2',    // افزودن فکت تازه
    'occasion_class' => 'national',      // مراسم نیست ولی ستون آزاد است
]);
$factsUpd = ReportingService::getEventFactsByEvent([$eventId])[$eventId] ?? [];
check((float)($factsUpd['honor_retirees_count']['value'] ?? 0) === 7.0, 'ویرایش: فکت موجود به ۷ به‌روزرسانی شد');
check(!isset($factsUpd['gift_count']), 'ویرایش: فکت صفر حذف شد');
check((float)($factsUpd['honor_legends_count']['value'] ?? 0) === 2.0, 'ویرایش: فکت تازه افزوده شد');
$rowUpd = ReportingService::getEventById($eventId);
check(($rowUpd['occasion_class'] ?? '') === 'national', 'ویرایش: ردهٔ مناسبت به‌روزرسانی شد');
ReportingService::updateEvent($ev2, ['occasion_class' => 'religious']);
$rowUpd2 = ReportingService::getEventById($ev2);
check(($rowUpd2['occasion_class'] ?? '') === 'religious', 'ویرایش مراسم: ردهٔ national به religious تغییر کرد');
// اعتبارسنجی: مقدار نامعتبر رد می‌شود
ReportingService::updateEvent($ev2, ['occasion_class' => 'bogus']);
$rowUpd3 = ReportingService::getEventById($ev2);
check(($rowUpd3['occasion_class'] ?? '') === 'religious', 'ویرایش: مقدار نامعتبر رده نادیده گرفته شد');

// ---- پاکسازی کپی موقت -----------------------------------------------------
@unlink($tempDb);
@unlink($tempDb . '-wal');
@unlink($tempDb . '-shm');

echo $failures === 0
    ? "\nALL HARNESS CHECKS PASSED ({$checks}/{$checks})\n"
    : "\n{$failures} CHECK(S) FAILED of {$checks}\n";
exit($failures === 0 ? 0 : 1);
