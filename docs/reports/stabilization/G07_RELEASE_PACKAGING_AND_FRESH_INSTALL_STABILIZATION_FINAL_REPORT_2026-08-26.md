# گزارش نهایی G-07 — بسته‌بندی و fresh-install

تاریخ: 2026-08-26  
Run: `STAB-G07-R01`  
Ledger: `V-132` تا `V-136`  
وضعیت: `G-07 COMPLETE / F-042 CLOSED / OFFLINE_AUTOMATED_ACCEPTED`

## مسیر اصلاح

A ثابت کرد `package_clean.py` هم UTF-16/NUL و غیرقابل import است و هم blacklist آن scratch/probe را وارد ZIP می‌کند. B آن را با allowlist، manifest/receipt، dry-run، secret scan و verifier deterministic جایگزین کرد. C collision/tamper/atomic guard و reproducibility بایتی را پذیرفت.

D stale بودن wheel را با missing=57/mismatch=20 کشف کرد. builder آفلاین canonical شد؛ fresh venv نخست سه dependency مفقود نشان داد که فقط متعلق به `application/bale_client` قرنطینه‌شده بودند. client از release/wheel و dependencyهای صرفاً آن از metadata حذف شدند، اما fail-closed Bale slot حفظ شد. wheel نهایی 90 فایل و صفر drift دارد و fresh venv آفلاین runtime checker، `pip check` و imports را می‌گذراند.

## پذیرش نهایی

- package/Bale guard=`20/20` و regression مرتبط=`102/102`.
- full Backend در اجرای نخست=`643/643` با skip صفر؛ collect-only=643.
- TypeScript و UI/Electron Observability سبز؛ build جاری G-06-C به‌علت نبود UI change تکرار نشد.
- wheel Bridge deterministic و SHA=`de9dd96f2ae76b5443eef8767fa0997afd19a29652e4a96d97b92da08dfa40cf`.
- دو archive نهایی پس از هم‌سویی اسناد هرکدام 282 فایل+manifest دارند و بایت‌یکسان‌اند: SHA-256=`729a3d613f8e941c7b973af2e6433fb387b1f97fee2b4e07e72d196b79e2cb57` و content-set=`1b7cc61fac50c3b581aaa6c577f6a64589ff921370d80bf0e75c12ee43e4170c`. verifier هر دو 282، forbidden/collision صفر، manifest-last و receipt match سبز است.

## مرز پذیرش

G-07 و F-042 بسته‌اند، اما code-sign، Installer EXE، نصب واقعی کاربر، Provider/Live و انتشار انجام نشده است. پروژه تا G-08/G-09 `NOT_RELEASE_READY` می‌ماند. پس از پنج دقیقه نبود پیام توقف، G-08-A طبق دستور کاربر آغاز می‌شود.
