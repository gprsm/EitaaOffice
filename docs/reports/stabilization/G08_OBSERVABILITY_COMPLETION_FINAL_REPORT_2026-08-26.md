# گزارش نهایی G-08 — تکمیل Observability و پوشش لاگ

تاریخ: 2026-08-26  
Run: `STAB-G08-R01`  
وضعیت: `COMPLETE / F-048 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`  
Release state: `NOT_RELEASE_READY / G-09 PENDING`

## نتیجهٔ کلان

G-08 اسکنر تک‌حساب، failureهای خاموش background/manual، نبود health نوشتن logger و retention/disk-health ناقص را در پنج checkpoint مستقل بست. همهٔ آزمون‌ها و فایل‌ها مصنوعی بودند؛ log/config/account/runtime/diagnostics واقعی اسکن یا prune نشدند.

## A تا D

- A: چهار RED canonical برای scanner، malformed JSONL، logger write failure و retention/disk ثبت شد (`4/4 failed`).
- B: application و تمام account scopeهای مستقیم با rotation عددی کشف و با scope ترتیبی بدون path/id/value گزارش می‌شوند؛ targeted=`2/2` و related=`18/18`.
- C: background عمومی lifecycle متوازن/correlated، content-index/read-receipt/lease و startup/shutdown/auth-close event امن دارند؛ Catalog `92→102`، GREEN=`4/4` و related=`98/98`.
- D: handler failure counter، health endpoint، current-safe retention، disk summary، JSONL normalization و opaque Support scanner تکمیل شد؛ Catalog=103، G08=`13/13` و related=`78/78`.

جزئیات شکست‌های fixture/scope بدون حذف تاریخچه در V-137 تا V-140 و گزارش‌های A تا D ثبت شده‌اند.

## E — پذیرش نهایی

full Backend نخست `655/656` بود. تنها شکست guard wheel/source parity بود: wheel پایان G-07 شش فایل محصول G-08 را نداشت (`missing=0 / mismatched=6 / extra=0`). pre-image wheel با SHA=`de9dd96f...` در artifacts حفظ شد؛ builder stdlib پذیرفته‌شدهٔ G-07 دو wheel مستقل بایت‌یکسان با SHA زیر ساخت:

`9408596d15576c8f46cf07ba6d4595ad2b049c2ea71785b17eb4e54033b70e70`

parity نهایی: 90 source file، missing/mismatched/extra همگی صفر. package+G08=`28/28` و full Backend دوم=`656/656 passed` با failure/error/skip صفر است. collection مستقل 656 را تأیید کرد. TypeScript و UI/Electron observability نیز exit code صفر دارند.

## وضعیت اسناد و بسته‌بندی

Baseline، Specification، Findings، Audit، Logging contract، ADR، Plan، Handoff و Release Manifest با G-08 هم‌سو شدند. wheel جاری هم‌تراز است؛ اما archive نهایی G-07 پس از تغییرهای source/docs G-08 تاریخی محسوب می‌شود. تولید archive نهایی تازه، verifier/dry-run و fresh-install تجمیعی به G-09 تعلق دارد؛ بنابراین این گزارش release readiness اعلام نمی‌کند.

## مرزها و Triggerها

- هیچ Provider network، Eitaa/Bale login/OTP/session/send، WordPress، نصب، publish، Firewall/Proxy/Port یا Git mutation انجام نشد.
- OBS-008 یعنی Web metrics/alert وابسته به deployment، آگاهانه `DEFERRED` باقی می‌ماند و blocker Desktop محلی G-08 نیست.
- تغییر scanner discovery/report، RuntimeLogger/health، retention، Event Catalog/background lifecycle، Support Bundle، wheel/source یا افزودن thread/account channel تازه Trigger تکرار G-08 است.

