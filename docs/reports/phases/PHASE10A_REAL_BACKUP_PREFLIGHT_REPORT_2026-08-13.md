# گزارش مستقل Phase 10-A — Preflight و Backup واقعی

تاریخ اجرا: ۲۰۲۶-۰۸-۱۳  
وضعیت: **تکمیل، آزموده و پذیرفته شد**

## توقف کنترل‌شده

- `runtime/backend-state.json` وجود نداشت.
- هیچ Process متعلق به Backend/Electron/Worker پروژه فعال نبود.
- در Portهای 8765، 8787، 8000، 8080، 3000 و 5173 Listener وجود نداشت.
- تنها Process مشابه Node متعلق به runtime داخلی Codex بود و متوقف نشد.
- بنابراین نصب پیش از Backup در وضعیت متوقف قرار داشت و Process نامرتبطی Kill نشد.

## مبنای داده

| فایل | اندازه | SHA-256 پیش و پس از عملیات |
|---|---:|---|
| `bridge.json` | 934 | `D95DC7717EF26CDD08451894679441C8F23ACECCC9FF50885DEC2501786EED89` |
| `.eitaa_session.json` | 491 | `8A80D9210145EE76B42B67B85B8A32757BEA150208AE41819B9867784802D39A` |
| `data/eitaa_messages.sqlite3` | 14692352 | `42C1701A494DB8AB4FC4094BC47867DC3AF2CF9429B1988754A2802068AAE194` |
| `data/contacts.sqlite3` | 253952 | `0400295D89A7DE212C70BC995CF5BA77F3ABEDFFA7D90AD95AA2D6FE646446C2` |
| `data/coordinator/coordinator.sqlite3` | 348160 | `C5A5306813EEA71FA53EF072AA43DB7A240EB41BBE0C512B67EE7B1916B4D5DA` |

حدود ۱۹٫۵ گیگابایت فضای آزاد در شروع وجود داشت.

## Backup دائمی

مسیر:

```text
backups/phase10-rollout/eitaa-bridge-backup-20260813-161104-845868.zip
```

نتیجه:

```text
archive_bytes=158955655
archive_sha256=9688ECE0F77B348D2DA0D245AADE70198727B6D08955D0F1D1159226FD31D124
manifest_file_count=4114
manifest_total_bytes=182295740
format=eitaa-bridge-runtime-backup-v1
include_media=true
include_logs=false
verified=true
```

Backup حاوی دادهٔ حساس نصب است و نباید خارج از نگه‌داری امن پروژه کپی یا منتشر شود.

## Restore و Migration rehearsal با همان Backup

همان آرشیو دائمی روی یک Root موقت Restore شد؛ آرشیو دیگری جایگزین آن نشد.

```text
restore_hashes_match=true
source_unchanged=true
contact_schema_before=1
contact_schema_after_on_copy=2
contact_count_before=574
contact_count_after_on_copy=574
category_count_before=3
category_count_after_on_copy=3
contact_recovery_backup_verified=true
```

تمام پوشه‌های موقت rehearsal پاک شدند و شمار باقی‌مانده صفر است.

## آزمون مستقل 10-A

- Backup/Restore/Coordinator/Contacts: **۳۲/۳۲ موفق**.
- Compile اسکریپت‌های Backup/Restore/Rehearsal: موفق.
- `git diff --check`: موفق.
- Hash پنج فایل مبنا پس از عملیات دقیقاً بدون تغییر باقی ماند.

## دروازهٔ خروج

Backup واقعی قابل بازیابی، hash-verified و روی کپی تمرین شده است. شرایط ورود به 10-B برقرار است. برنامه همچنان متوقف و Feature Flagها همچنان خاموش‌اند.
