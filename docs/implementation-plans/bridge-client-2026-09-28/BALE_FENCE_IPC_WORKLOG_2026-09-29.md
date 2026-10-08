# لاگ کار زنده — attempt fence و کران IPC مخاطبین (F-099)

این فایل لاگِ از پیشرفتِ کار است؛ پس از هر گام معنادار به‌روز می‌شود تا در صورت قطعی نشست، ادامهٔ کار از نقطهٔ دقیق قطع ممکن باشد. وضعیت پایه: دستور اصلاحی `BALE_ACCEPTANCE_REPAIR_2026-09-29.md` (بخش «ادامهٔ ضروری پس از V-246»)، شاخهٔ `codex/bale-web-client-instructions`، درخت dirty عمدی، HEAD 41dc87a2.

## گام‌ها

- [2026-09-29T00:00] آغاز نشست ادامه‌دهنده. مأموریت: (۱) attempt fence — release فعلی شناسهٔ تلاش نمی‌گیرد، cleanup دیررس تلاش قدیمی ادعای تلاش تازه را آزاد می‌کند (پروب `BALE_ACCEPTANCE_FENCE_PROBE_2026-09-29.py` در DB ایزوله RED)؛ (۲) مسیر Child→backend کل مخاطبین را در یک فریم IPC می‌فرستد؛ دفترچهٔ ۲۰۰۰ مخاطبی با نام ۵۱۲حرفی body حداقل 1,134,907 بایت > سقف frame 1,048,576؛ صفحه‌بندی ۵۰۱تایی این حالت را نمی‌پوشاند؛ (۳) رفع دو خطای whitespace انتهای فایل: `src/eitaa_bridge/application/agent_gateway.py:711` و `tests/test_bale_main_product.py:775` (new blank line at EOF). محدودیت‌ها: بدون reset/checkout/clean، بدون Live (نیازمند اجازهٔ همان لحظه)، F-099 باز می‌ماند تا شواهد کامل.

## وضعیت گام‌ها

| # | گام | وضعیت |
|---|---|---|
| 1 | خواندن مستندات پایه (project-memory، baseline، انتهای FINDINGS/LEDGER) | انجام شد |
| 2 | بازتولید RED پروب fence (DB ایزوله) | انجام شد |
| 3 | طراحی و پیاده‌سازی attempt fence (schema migration 13 + token + match اتمیک در release/complete + نقاط فراخوانی orchestration) | انجام شد |
| 4 | سبز کردن پروب fence بدون تضعیف | انجام شد (GREEN) |
| 5 | بازتولید RED سرریز فریم IPC با دفترچهٔ بزرگ (> 1 MiB) | انجام شد |
| 6 | اعمال cursor/limit در Child→backend؛ پاسخ bounded + next_cursor واقعی؛ متد contains | انجام شد |
| 7 | آزمون‌های مستقل canonical (fence: text/media/remove، restart، terminal؛ IPC: ۲۰۰۰ مخاطب، فریم کراندار، صفحهٔ آخر) | انجام شد (۳ آزمون تازه در test_bale_main_product.py) |
| 8 | رفع خطاهای whitespace (تأیید با git diff --check) | انجام شد (exit 0) |
| 9 | gateهای کامل (full pytest، UI check/observability، memory integrity، wheel parity) | انجام شد (۱۱۲ تست بله سبز، ویل بازسازی‌شده، UI سبز) |
| 10 | ثبت Ledger با شناسهٔ V-247 + به‌روزرسانی FINDINGS F-099 | انجام شد |

## یادداشت‌های فنی (برای ادامه پس از قطعی)

- `ProviderOperationReceiptStore` در `src/eitaa_bridge/infrastructure/coordinator/receipts.py`: claim در مسیر re-claim (ردیف in_progress با `safe_reason_code='claim_released'`) فقط deadline را به‌روز می‌کند و reason را NULL می‌کند؛ release فقط با actor/fingerprint/service تطبیق می‌کند → cleanup دیررس A پس از claim تازهٔ B همان ردیف را آزاد می‌کند. ستونی برای نسل/تلاش وجود ندارد.
- COORDINATOR_SCHEMA_VERSION = 12 (schema.py:7). مهاجرت 12→13 برای ستون نسل تلاش لازم است؛ الگوی مهاجرت در schema.py (بخش‌های SCHEMA_V*_CHECKSUM و migration runs).
- نقاط فراخوانی receipt: provider_orchestration.py سطرهای 347 (release)، 605/630/690 (claim/complete مسیر اول)، 897/922/977 (مسیر دوم)، 1050/1061/1098 (مسیر سوم). Protocol در سطر 110.
- پروب fence: claim A → release(بدون توکن) → claim B → release دیررس A (باید False) → claim C (باید False). API تازه باید توکن نسل پایدار از claim بدهد و release/complete match اتمیک کنند؛ پروب برای عبور از API تازه باید توکن تلاش قدیمی را در cleanup دیررس بدهد (این به‌روزرسانی پروب تضعیف نیست؛ سناریو حفظ می‌شود).
- سقف فریم IPC: 1,048,576 بایت (۱MiB). بدنهٔ ۲۰۰۰ مخاطب با نام ۵۱۲حرفی ≈ 1,134,907 بایت > سقف.
- قواعد: venv با `./.venv/Scripts/python.exe`؛ خروجی pytest با `--junitxml` به مسیر ویندوزی؛ heredoc بلند ممنوع؛ رجیسترها append-only؛ V-id تازه فقط پس از بررسی local و origin/Bale.

## لاگ رویدادها

- [2026-09-29] نشست آغاز شد؛ کار از ابتدا بازآغاز می‌شود. خوانده‌شده تا اینجا: AGENTS.md، دستور اصلاحی، گزارش بازبینی مستقل، receipts.py کامل، پروب fence، شناسایی نقاط فراخوانی و schema_version=12.
- [2026-09-29] مستندات پایه خوانده شد: project-memory/README، CURRENT_SYSTEM_BASELINE (فصل ۸ با قید V-246)، PROJECT_SPECIFICATION، رکوردهای کامل F-099 و V-244/V-245/V-246. آخرین V محلی = V-246؛ ریموت در دسترس است. لاگ کار ساخته شد (همین فایل).
- [2026-09-29] گام ۲ انجام شد: پروب fence در DB ایزوله اجرا شد → `stale_release=true, third_claimed=true, passed=false, exit=1` — RED مطابق V-246 بازتولید شد.
- [2026-09-29] یافته‌های مسیر IPC مخاطبین:
  - Child (`bale_provider_worker.py:609`): `bale.provider.contacts.query` بدون cursor/limit کل `owner.list_contacts()` را در یک response می‌گذارد. `_require_fields(payload, set())` یعنی هیچ ورودی نمی‌پذیرد.
  - Runtime (`bale_runtime.py:423`): `BaleRuntimeBackend.list_contacts()` → `_request("bale.provider.contacts.query", {}, 90)` — fetch-all روی IPC.
  - Adapter (`bale_provider_adapter.py:386`): cursor/limit را خودش با slice محلی اعمال می‌کند (بعد از IPC)؛ cursor قالب `offset:<n>` دارد؛ پیشرفت cursor با تعداد آیتم‌های فیلترشده (نه پنجرهٔ خام) — خطر duplicate.
  - Adapter در upsert_contact (سطر ۴۲۸) برای بررسی وجود مخاطب باز هم `list_contacts()` کامل می‌گیرد (در حالت Process دوباره fetch-all روی IPC).
  - Client (`bale_client/api.py:265`): `users.GetContacts` با payload خالی — پروتکل بله paging سمت سرور ندارد؛ کل دفترچه در یک RPC داخل Child برمی‌گردد.
  - پروتکل (`worker_ipc/protocol.py`): `IPC_MAX_MESSAGE_BYTES = 1,048,576`؛ `_canonical_json` فریم بزرگ‌تر را با `ipc_message_too_large` رد می‌کند؛ لیست‌های بیش از ۴۰۹۶ آیتم هم `ipc_payload_invalid` می‌شوند. پس دفترچهٔ بزرگ در حالت Process اصلاً قابل انتقال نیست.
- [2026-09-29] طراحی انتخابی R3 (پایه: «backend بله paging ندارد»): (۱) Child متد `contacts.query` را با ورودی اختیاری `cursor`/`limit` (۱..۵۰۰) بازنویسی می‌کند؛ fetch کامل فقط داخل Child می‌ماند؛ snapshot با token در Child کش می‌شود (TTL کوتاه، ابطال با add/remove)؛ هر فریم IPC ≤ یک صفحه کراندار؛ `next_cursor` واقعی قالب `bale:snap:<token>:<offset>`؛ snapshot منقضی → خطای صریح safe_code (نه پایان جعلی). (۲) متد تازه `bale.provider.contacts.contains` (user_id → bool) برای بررسی وجود در upsert؛ فریم کوچک. (۳) `BaleRuntimeBackend` متد `list_contacts_page(cursor, limit)` می‌گیرد و adapter برای backendهای دارای این متد از paging واقعی IPC استفاده می‌کند؛ در غیر این صورت (in-process بدون مرز IPC) slice محلی باقی می‌ماند ولی پیشرفت cursor با طول پنجرهٔ خام اصلاح می‌شود. (۴) cursorهای legacy `offset:` پذیرفته نمی‌شوند (قرارداد transit است؛ ذخیره‌سازی ندارد).
