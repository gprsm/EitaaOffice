# گزارش بازگردانی دسترسی پنل «عملیات گفتگو»

تاریخ: 2026-08-28
Run: `UX-COMMUNITY-ROLLBACK-R03`
وضعیت: `IMPLEMENTED / FULL_AUTOMATED_ACCEPTANCE / OFFLINE_PACKAGE_GREEN / GIT_PUBLICATION_PENDING`

## نتیجه

به درخواست صریح کاربر، غیرفعال‌سازی سطح «عملیات گفتگو» بر پایهٔ نقش owner/admin بازگردانی شد. مقایسهٔ مستقیم با commit پیش از R02 نشان داد رفتار قبلی فقط حذف شرط نقش نبود: پنل و ورودی‌های آن همیشه قابل‌بازشدن بودند؛ در group/channel ابزار به «اعضای گفتگو» و در personal یا بدون انتخاب گفتگو به «شماره‌های جدید» هدایت می‌شد. همین قرارداد بازگردانده شد.

فقط «مدیریت اعضا» بدون group/channel انتخاب‌شده غیرفعال است. بازکردن پنل یا ابزار گروهی عملیات واقعی اجرا نمی‌کند؛ preflight، تأیید صریح و محدودیت‌های Backend/Provider همچنان در زمان اقدام اعمال می‌شوند.

## علت فنی

R02 نقش را از metadata معتبر Eitaa به catalog منتقل می‌کرد، اما این signal برای رکوردهای قدیمی، basic group و بعضی پاسخ‌های ناقص یا stale می‌تواند `unknown` بماند. استفاده از چنین hintی برای disable کردن UI باعث false-negative شد: کاربر می‌توانست واقعاً مدیر باشد، ولی رابط پیش از رسیدن به Provider دسترسی را می‌بست.

در R03 فیلدهای `account_role` و `can_manage_community` حذف نشده‌اند و همچنان برای مشاهده‌پذیری و توسعهٔ آینده در قرارداد باقی‌اند؛ فقط از تصمیم فعال‌سازی client-side کنار گذاشته شده‌اند. این تغییر ادعای افزایش مجوز Provider یا دورزدن تأییدهای عملیات ندارد.

## تغییرهای کد

- helperهای `canManageCommunity`/`canUseCommunityOperations` و prop سراسری `communityEnabled` حذف شدند.
- دکمهٔ عملیات گفتگو در Header و Navigation و toggle آن در Composer دیگر disabled نمی‌شود.
- مسیر «ارسال و اقدام گروهی» برای group/channel روی `members` و برای personal/no-dialog روی `numbers` باز می‌شود.
- دکمهٔ «مدیریت اعضا» فقط با group/channel انتخاب‌شده فعال می‌شود.
- متن محدودکنندهٔ «مالک یا مدیر» از UI حذف شد.
- sourceهای WordPress، avatar loader/queue، scheduler، dialog permission و catalog تغییر نکردند.

## شاهد RED و GREEN

- RED مرحلهٔ حذف role gate: دو contract هدفمند مطابق انتظار شکست خوردند.
- بررسی parent پیش از R02 نشان داد پنل قبلاً همیشه باز می‌شد و personal/no-dialog به حالت numbers می‌رفت؛ contract برای بازگشت کامل دقیق‌تر شد و دوباره `2 failed` ثبت کرد.
- GREEN هدفمند نهایی=`4/4` برای toggle، مسیر Composer/Bulk، عدم وجود gate و حالت contextual مدیریت اعضا.
- TypeScript با toolchain worktree اصلی=`PASS`.
- اجرای TypeScript داخل candidate چون clone عمداً `node_modules` ندارد با `tsc not recognized` متوقف شد؛ این خطای محیطی محصول نیست و validation با toolchain read-only ریشه تکرار می‌شود.
- full Backend نخست `662/664` بود و فقط wheel قدیمی candidate و نبود build در clone را آشکار کرد. پس از بازسازی artifactها بدون تغییر کد محصول، retry=`2/2` و full نهایی=`664/664` سبز شد.
- هر ۹ runner UI سبز است؛ TypeScript=`PASS` و build تولیدی Vite با 1016 module=`PASS`. warning تاریخی chunk بزرگ nonblocking باقی است.
- همهٔ 65 فایل source/script/config UI میان root آزموده‌شده و candidate پس از نرمال‌سازی line ending دقیقاً برابر بودند؛ بنابراین toolchain root همان snapshot candidate را سنجید.
- wheel تازه با source parity سبز و SHA-256=`22825e54807f9c49f3b93256ffea9570be65a948131d920118be2e7741739e40` ساخته شد.
- package dry-run و دو archive 283فایلی بایت‌یکسان با privacy/path/hash verifier سبز شدند. fresh-install دقیق archive فقط با wheelهای محلی و `--no-index`، runtime checker، `pip check`، import ایزوله، Event Catalog=103 و چهار entrypoint را گذراند.
- رخدادهای محیطی `tsc` غایب در clone، wildcard کپی و CRLF/LF runtime patch ثبت و بدون تغییر محصول با toolchain/finalizer صحیح تکرار شدند.

## حریم خصوصی و اثر عملیاتی

هیچ login، OTP، session، پیام، دعوت/حذف عضو، WordPress، Provider mutation یا دادهٔ عملیاتی باز یا تغییر داده نشد. نام/شناسهٔ گفت‌وگوی گزارش‌شده در سند و خروجی آزمون ثبت نشده است. آزمون‌ها فقط source contract مصنوعی را خواندند و artifact کنترل‌شدهٔ build/test می‌سازند.

## تداخل‌نداشتن با کار موازی ایندکس

پیاده‌سازی و اسناد انتشار روی clone ایزولهٔ شاخهٔ `codex/message-avatar-grouping` انجام می‌شوند. root dirty، index آن و فایل‌های ایندکس‌گذاری هم‌زمان reset، checkout، stage یا commit نمی‌شوند. شناسه‌های F-070، ADR-60 و V-200 به بعد عمداً بیرون از بازهٔ نزدیک writer موازی انتخاب شدند.

## مراجع

- Finding: F-070
- Decision: ADR-60
- Validation: V-200/V-201
- فایل‌های رابط: `ui/src/App.tsx`، `ui/src/ChatHeader.tsx` و `ui/src/WorkspaceNavigation.tsx`
- آزمون‌ها: `tests/test_ui_repair.py`، `tests/test_ui3_dialog_operations.py` و `tests/test_material_ui_repair.py`
