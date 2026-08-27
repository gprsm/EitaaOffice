# وضعیت پایهٔ فعلی پروژه

تاریخ مبنا: ۲۰۲۶-۰۸-۲۷
آخرین همسان‌سازی: UX-MESSAGE-AVATAR-R01؛ ادغام پیام متوالی و صف مستقل آواتار در ۲۰۲۶-۰۸-۲۷
وضعیت: `STABILIZATION_COMPLETE / USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE / NOT_PRODUCTION_RELEASE_AUTHORIZED`  
منابع شاهد جاری: V-103، V-108 تا V-162، V-169/V-170، F-039 تا F-050 و F-056؛ شناسه‌های میانی برای کار موازی ایندکس رزرو شده‌اند و در این snapshot حضور ندارند.

Milestone UX-MESSAGE-AVATAR-R01: پیام‌ها و آلبوم‌های مجاور یک فرستنده تا پنج دقیقه و در همان روز نمایشی یک Card محتوایی می‌شوند؛ متن، run عکس و فایل به ترتیب timeline حفظ می‌شوند و انتخاب/ایندکس/usage/unread/focus همهٔ member IDها را نگه می‌دارند. آواتار cache-first و account-scoped است؛ lane سریع cached-only از lane remote تک‌صف امن جداست و failure یک peer بقیه را reject یا متوقف نمی‌کند. full Backend=`659/659`، هر ۹ runner UI، TypeScript و build 1016-module سبز است. نبود photo reference بعضی Userهای گروهی محدودیت Core است و امن به initials برمی‌گردد؛ عملیات Live/Provider انجام نشد.

Milestone تثبیت 2026-08-25: G-00 یک baseline deterministic و قابل‌بازگشت از 613 فایل امن با receipt/SHA-256 ایجاد و repository ریشه را به تاریخچهٔ محلی `legacy/main` متصل کرد. هیچ stage/commit انجام نشده است. V-103 روی snapshot منتقل‌شده Backend=`587 collected / 585 passed / 2 failed` و دو contract شکستهٔ UI را ثبت کرد؛ بنابراین نتیجه‌های قدیمی `590/590` وضعیت جاری را اثبات نمی‌کنند.

Milestone G-02: Bale registration اکنون با حفظ مرجع تصمیم F-046 به‌طور صریح fail-closed است؛ هیچ factory/capability/auth step فعال ندارد و full Backend پس از اصلاح `599/599` است. این شاهد آفلاین است و هیچ Live acceptance برای Bale نمی‌سازد.

Milestone G-11: گزارش تداوم timeline قدیمی پس از G-10 نشان داد دادهٔ جاری تا ۴ شهریور موجود است، اما runtime patch تحت URL ثابت با cache یک‌سالهٔ immutable از pre-image مرورگر اجرا می‌شود. build اکنون نام patch را از hash محتوا می‌سازد و HTTP فقط asset نام‌هش‌دار را immutable می‌فرستد. RED=`3 failed / 6 passed`، targeted=`9/9`، related=`54/54`، full Backend نهایی=`658/658`، همهٔ UI runnerها/TypeScript/build، wheel parity 90/0، archive deterministic و fresh-install آفلاین سبزند. برنامه هنگام بررسی نهایی اجرا نبود؛ تأیید بصری کاربر پس از restart همچنان pending است.

Milestone G-04-A: قرارداد متأخر نمایش کامل هویت canonical در مرز مجاز محصول با آزمون مستقل سبز شد، اما دو RED کنترل‌شده باقی است: دو تست تاریخی هنوز placeholder هستند و redaction عمومی کلیدهای `phone_hint`/`display_hint` را نمی‌شناسد. اجرای هدفمند `1/3 passed` و `2/3 failed` است؛ بنابراین G-04 و F-044 باز و پروژه تا دستور G-04-B متوقف‌اند. هیچ کد محصول، دادهٔ عملیاتی یا رفتار Bale تغییر نکرد.

Milestone G-04-B: هر دو RED مرحلهٔ A بسته شدند. تست‌های masking منقضی با قراردادهای غیرخالی نمایش canonical جایگزین و کلیدهای identity hint وارد redaction مشترک شدند؛ اختصاصی `3/3` و regression مرتبط `28/28` سبز است. G-04 هنوز بسته نیست؛ G-04-C با مجوز کاربر برای جداسازی token از onboarding عمومی در جریان است.

Milestone G-04-C: token دیگر فیلد عمومی onboarding حساب نیست و validator تلفن فقط canonical E.164 می‌پذیرد. endpoint تنها `provider/phone/label` و Provider دارای `account_identity_kind=phone_e164` را به PhoneAccount می‌فرستد؛ هیچ token یا identity kind غیرتلفنی از این persistence عبور نمی‌کند. Backend هدفمند `2/2`، UI onboarding=`7/7` و regression مرتبط=`126/126` سبز است؛ هیچ مسیر Bale فعال یا account kind تازه ساخته نشد.

Milestone G-04-D: privacy scan مستقل چهار کانال ابتدا `5/5 RED` و پس از hardening `5/5 GREEN` شد. Runtime/Diagnostic متن ناشناخته و تو‌در‌تو را pattern-scan می‌کنند؛ Audit پیش از persistence و هنگام query/export redaction دارد؛ Support Bundle و scanner تلفن canonical جهانی را پوشش می‌دهند. سه regression مرتبط `53/53`، `2/2` و `50/50` سبزند. G-04 هنوز تا full regression/finalization مرحلهٔ E باز است.

Milestone G-04-E: معیارهای A تا D و هش‌های snapshot بدون drift ممیزی شدند. full Backend نخست `618/620` با دو timeout Process Worker بود؛ همان دو تست در isolation=`2/2` و full rerun تازه=`620/620` سبز شدند. TypeScript، Observability و UI onboarding=`7/7` نیز سبزند. G-04 کامل و F-044 بسته است؛ G-05 تا دستور کاربر شروع نمی‌شود و پروژه هنوز `NOT_RELEASE_READY` است.

Milestone G-05: auto-index thread ساعتیِ بدون stop/join و swallowing خاموش حذف شد. scheduler تا قرارداد مستقل feature/config به‌صورت safe-default خاموش و با event cataloged/correlated اعلام می‌شود؛ پنج مسیر manual index حفظ‌اند. RED=`3/4`، targeted=`5/5`، adversarial/observability=`11/11`، broad=`143/143` و full Backend=`625/625` است؛ TypeScript/Observability نیز سبزند. G-05 کامل و F-043 بسته است.

Milestone G-06: drift تنها قرارداد Phase 10 از جست‌وجوی تعریف محلی به import/export واقعی `helpers.tsx` اصلاح شد و guard سراسری، تست خالی و skip/xfail بی‌دلیل را رد می‌کند. همهٔ ۹ runner UI، TypeScript و build محلی سبزند؛ broad Backend=`307/307` و full Backend=`628/628` با skip صفر است. حوزهٔ تست F-042 بسته، ولی خود Finding برای package allowlist در G-07 باز و پروژه همچنان `NOT_RELEASE_READY` است.

Milestone G-07: packager UTF-16/blacklist با allowlist deterministic، manifest/receipt، privacy/traversal/hash verifier و dry-run جایگزین شد. stale wheel و سه dependency صرفاً Bale-client از release حذف شدند؛ fail-closed Bale slot حفظ است. wheel آن checkpoint 90 فایل/صفر drift و archive 282 فایل داشت؛ fresh venv آفلاین و full Backend=`643/643` سبز بود. در پایان همان milestone، G-08/G-09 باز بودند؛ G-08 اکنون بسته است.

Milestone G-08-B: اسکنر Runtime log دیگر به یک account id ثابت محدود نیست؛ application و تمام account scopeهای مستقیم با rotation عددی را کشف می‌کند و فقط scope ترتیبی/path-free گزارش می‌دهد. JSON/UTF-8/read/missing/symlink و یافتهٔ حساس fail-closed هستند؛ targeted=`2/2` و related=`18/18` سبز است. این شاهد کاملاً مصنوعی است و هیچ log واقعی اسکن نشده؛ G-08 برای C تا E باز است.

Milestone G-08-C: background عمومی با operation lifecycle متوازن و correlation منتقل‌شده ثبت می‌شود. manual content-index، read-receipt best-effort، lease renewal غیرمنتظره و مرزهای startup/shutdown/auth-close event صریح و safe دارند؛ Catalog از 92 به 102 رسید. RED=`4/4`، GREEN=`4/4` و related=`98/98` است. هیچ عملیات Provider یا Live انجام نشد؛ G-08-D/E باز است.

Milestone G-08-D: RuntimeLogger failure را مهار/شمارش و health path-free ارائه می‌کند؛ retention فقط numeric rotationهای Application/Worker را با حفاظت current می‌زداید و disk health عددی است. Support Bundle JSONL ناقص را امن عادی و scanner نام‌ها را opaque می‌کند. Catalog=103، G08=`13/13` و related=`78/78`؛ تمام حذف‌ها/فایل‌ها مصنوعی و G-08-E باز است.

Milestone G-08-E: full نخست `655/656` فقط به‌علت wheel شش فایل عقب بود. wheel آفلاین دوبار با SHA یکسان و parity 90/0 drift بازسازی شد؛ package+G08=`28/28` و full rerun=`656/656` با skip صفر، TypeScript و UI Observability سبز است. G-08/F-048 بسته؛ archive/fresh-install تجمیعی G-09 و پذیرش نهایی باز است.

Milestone G-09: dry-run 282فایلی بدون write، دو archive نهایی بایت‌یکسان با SHA=`6ff12e2b...` و privacy finding صفر، extract 283فایلی، wheel parity 90/0 drift و fresh venv کاملاً آفلاین سبز شدند. archiveهای B پس از همسوسازی Architecture تاریخی شدند و artifact نهایی E دوباره ساخته/نصب شد. full Backend نهایی=`656/656` با skip صفر، هر ۹ runner UI، TypeScript و build 1015-module سبزند. کاربر در 2026-08-26 پذیرش G-09 را صریحاً ثبت کرد؛ code-sign/Windows visual/real-user installer هنوز بیرونی‌اند و Production release مجاز اعلام نمی‌شود.

Milestone Git publish: قواعد ignore امن برای جلوگیری از ورود temp/cache و اسکریپت‌های یک‌بارمصرف به GitHub افزوده شد. نامزد نهایی نسبت به مبنای GitHub شامل 426 فایل و فاقد temp/cache، دادهٔ عملیاتی، DB، کپی پژوهشی Bale و scratch script است. چون `.gitignore` عضو release allowlist است، دو archive canonical نهایی با SHA=`481ed1be...` و content-set=`43c67c2e...` ساخته شدند؛ diff محتوایی با archive میانی فقط `.gitignore`، privacy finding صفر و wheel/source بدون drift است. این تغییر کد محصول یا پذیرش G-09 را عوض نمی‌کند.

Milestone G-10: ممیزی فقط‌خواندنی و ماسک‌شده نشان داد sync و SQLite گروه منتخب جاری‌اند، اما runtime patch موقعیت مطالعه، درخواست صفحهٔ نخست پیام‌ها را با checkpoint قدیمی بازنویسی می‌کرد و پیام‌های تازه را از پنجرهٔ UI بیرون می‌گذاشت. قرارداد RED با `1 failed / 5 passed` ثبت و بازنویسی `before_id/limit` حذف شد؛ fetch اکنون request اصلی را دست‌نخورده می‌فرستد. regression هدفمند=`11/11`، full Backend=`657/657`، هر ۹ runner UI، TypeScript و build 1015-module سبزند. archive نهایی 282 فایل، privacy finding صفر و SHA=`077d316d...` دارد. تأیید بصری مستقیم به‌علت خرابی زیرساخت Computer Use اجرا نشد؛ هیچ پیام، login، OTP، Bale یا write عملیاتی انجام نشد.

## فصل ۱ — وضعیت فازها

| بخش | وضعیت | توضیح |
|---|---|---|
| Phase 10-A | `LIVE_ACCEPTED` | Backup preflight واقعی پذیرفته شده است. |
| Phase 10-B | `LIVE_ACCEPTED` | AppUser، ورود واقعی ایتا، نشست، UI و فعال‌سازی محلی پذیرفته شده‌اند. |
| Phase 10-C | `FAKE_VERIFIED` و Contract accepted | استقرار محیط‌مستقل، Web proxy contract، جداسازی و WordPress اختیاری پذیرفته شده‌اند. |
| Phase 10-D | `LIVE_ACCEPTED`/copy rehearsal | Backup/restore روی کپی، Support Bundle و عملیات restart ایزوله پذیرفته شده‌اند. |
| Phase 10 نهایی | `LIVE_ACCEPTED` | گزارش نهایی پذیرش موجود است. |
| Phase 11-0 | `IMPLEMENTED / FAKE_VERIFIED` | Onboarding چندحسابی ایتا، UI و API امن، race/idempotency/isolation و ثبت رخداد پذیرفته شده‌اند؛ Pilot واقعی حساب دوم اجرا نشده است. |
| Phase 11-A | `HISTORICAL_DISCOVERY / LATER_CONTRACT_F-046` | Discovery اولیه clientهای غیررسمی را ممیزی کرد؛ تصمیم متأخر کاربر در F-046 قرارداد توسعهٔ Bale را معتبر اعلام کرده است. این تثبیت توسعهٔ تازه یا عملیات Live انجام نمی‌دهد. |
| Phase 11-B0 | `FOUNDATION_IMPLEMENTED / BALE_FAIL_CLOSED_G-02_VERIFIED` | Provider Extension API v1 حفظ شد؛ Bale state=`implemented` است اما configured/runtime/onboarding همگی false، factoryها غایب و capability خالی‌اند. |
| Phase 11-B1 | `IMPLEMENTED / FAKE_VERIFIED` | Registry پایدار، Coordinator v6، Contact v3، Audit عمومی، Fake سوم، Capability service و guard مسیرهای provider-backed تکمیل شده‌اند؛ full regression 540/540 است. |
| Phase 11-B2 | `IMPLEMENTED / CONTRACT_FAKE_VERIFIED / NOT_LIVE` | هر شش عملیات Dialog/History/Text Send/Media/Contacts از orchestrator عمومی عبور می‌کنند؛ Eitaa in-process و Process Child RPC محدود و account-fenced هستند. mutation receiptهای schema v7 پس از restart پایدار می‌مانند و replay/owner/payload را می‌بندند. Full Backend برابر 561/561 است. |
| Phase 11-C | `CONTRACT_DECISION_PRESERVED / RUNTIME_FAIL_CLOSED` | مرجع F-046 در manifest باقی است، اما implementation contract-verified یا Live نیست و runtime قابل ساخت نیست. عملیات Live نیازمند تأیید همان لحظه است. |
| Phase 11-D | `EITAA_LOCAL_UI_ACCEPTED / BALE_DISABLED_HONESTLY` | UI و read/live-sync حساب موجود ایتا پذیرفته شده‌اند؛ descriptor و fixture بله آن را غیرقابل‌اجرا و با reason امن نمایش می‌دهند. |

## فصل ۲ — مدل کاربران و حساب‌ها

وضعیت معماری:

```text
AppUser -> Membership -> PhoneAccount -> MessengerAccount -> Provider Runtime
```

- یک AppUser می‌تواند به چند PhoneAccount و چند MessengerAccount دسترسی داشته باشد.
- چند MessengerAccount از یک Provider مجاز است.
- Session، Worker، DB، Cache، Media، Job، Rate policy، Log و Audit هر حساب مستقل هستند.
- Context حساب از سمت سرور و پس از Membership تعیین می‌شود؛ شناسهٔ ارسالی UI به‌تنهایی مجوز نیست.
- آزمون‌های Fake/Contract/Adversarial چندکاربر و چندحساب پذیرفته شده‌اند.
- ساخت چند حساب Eitaa برای یک AppUser با owner membership اتمیک و شناسه‌های server-owned خودکار پذیرفته شده است.
- Pilot واقعی حساب دوم هنوز انجام نشده است.
- AppUser Auth و multi-session در config اجرایی فعلی روشن‌اند. self-registration فقط برای `desktop_loopback/trusted_lan_http` فعال و در reverse-proxy عمومی بسته است؛ کاربر تازه همیشه role=`user` می‌گیرد.
- حداقل رمز AppUser چهار نویسه است؛ سقف، منع control character، PBKDF2 با 600000 iteration، throttle، lockout و revoke حفظ شده‌اند.
- idle و absolute session policy فعلی هر دو یک سال‌اند و Cookie مرورگر `Max-Age=31536000` دارد؛ logout/revoke/change-password همچنان نشست را لغو می‌کنند.

## فصل ۳ — وضعیت Providerها

| Provider | مدل/Registry | Adapter واقعی | ورود واقعی | اولویت |
|---|---:|---:|---:|---:|
| Eitaa | موجود | موجود | پذیرفته شده | اول |
| Bale Personal | `implemented` + مرجع F-046؛ configured/runtime/onboarding=false | factory ندارد؛ compatibility class پیش از client/session/network رد می‌شود | انجام نشده | G-02 آفلاین `599/599` |
| Bale Bot/Arm | تصمیم تاریخی بازیابی‌شده؛ مرجع جاری F-046 | مسیر رسمی در حافظه ثبت شده، اما قابلیت تازه در دامنهٔ تثبیت نیست | انجام نشده | خارج از توسعهٔ جاری |
| Rubika | تصمیم معماری | موجود نیست | انجام نشده | آینده |
| SoroushPlus | تصمیم معماری | موجود نیست | انجام نشده | آینده |
| Telegram | قابل انطباق با معماری عمومی | موجود نیست | انجام نشده | نیازمند Discovery جداگانه |

نکته: دربارهٔ Telegram باید ابتدا نوع اتصال—Bot API یا حساب کاربری/MTProto—تعیین شود. هیچ API یا قابلیت Provider حدس زده نمی‌شود.

Discovery تاریخی 11-A تفکیک هویت Bot/Arm و Personal را ثبت کرد. قرارداد متأخر F-046 rollback نشده، اما G-02 implementation ناقص را quarantine و registration را fail-closed کرده است؛ هیچ قابلیت یا پذیرش Live از آن استنباط نمی‌شود. جزئیات در `BALE_PROVIDER_DISCOVERY.md` ثبت شده است.

## فصل ۴ — وضعیت UI حساب‌ها

یافتهٔ تثبیت‌شده:

- `MessengerAccountGate` فهرست حساب‌های مجاز را از API می‌خواند.
- منوی «حساب پیام‌رسان» حساب فعال را انتخاب می‌کند.
- پنل تنظیمات حساب‌های موجود را با Provider، شمارهٔ canonical کامل طبق تصمیم محصول 2026-08-21، Auth state و Worker state نمایش می‌دهد. مقدار کامل فقط در سطح مجاز محصول است و ورود آن به Log/Audit/Diagnostic/Support Bundle ممنوع باقی می‌ماند.
- شروع/توقف Worker و انتخاب حساب موجود پشتیبانی می‌شود.
- نوع Provider در UI رشته‌ای و نمایش/runnable/onboarding از descriptor سمت سرور خوانده می‌شود؛ union و شرط مستقیم Eitaa حذف شده است.
- UI برای هر حساب snapshot قابلیت را از endpoint حساب‌محور می‌خواند؛ snapshot حساب قبلی در همان رندر تعویض نیز نامعتبر است.
- Dialog/History/Media/Send/Contacts در UI فقط در وضعیت `supported` و `runtime_enabled` پیش از request فعال‌اند؛ خطای خواندن capability به‌صورت fail-closed عمل می‌کند.
- دکمه و Dialog «افزودن حساب پیام‌رسان» Provider فعال را از catalog می‌گیرد، شمارهٔ E.164 و label اختیاری را می‌پذیرد و مقدار خصوصی را پس از submit/cancel پاک می‌کند.
- `POST /api/v2/messenger-accounts` فقط فیلدهای `provider/phone/label` را می‌پذیرد؛ `token` در این مرز مردود است و فقط descriptor دارای identity kind برابر `phone_e164` وارد PhoneAccount می‌شود. شناسه‌ها، Membership و مسیرها سمت سرور ساخته می‌شوند.
- ساخت حساب تازه Worker یا اتصال شبکه را خودکار آغاز نمی‌کند. کاربر حساب را صریح Start می‌کند و سپس Auth flow مرحله‌ای موجود در scope همان MessengerAccount اجرا می‌شود.
- Eitaa onboardable است. Bale با `onboarding_enabled=false` و `provider_adapter_not_configured` صادقانه غیرفعال است؛ fixture محلی نیز همین descriptor را نشان می‌دهد. هیچ Login/OTP/Send بله در تثبیت اجرا نشد.
- تکرار/restart/race همان مالک idempotent است و مالک دیگر نمی‌تواند هویت ثبت‌شده را claim یا از پاسخ وجود آن را استنتاج کند.
- نصب فعلی فقط یک حساب واقعی ایتا در انتخاب‌گر دارد؛ بنابراین تعویض واقعی میان دو حساب هنوز پذیرش نشده است.
- صفحهٔ ورود اکنون دکمهٔ «کاربر جدید هستم» دارد و ثبت‌نام خودخدمت در شبکهٔ خصوصی، بدون امکان انتخاب نقش مدیر، انجام می‌شود.
- سطح‌های فعال React فقط از Material UI و `theme/sx` استفاده می‌کنند؛ `className` و stylesheetهای اختصاصی قدیمی از graph اجرایی حذف شده‌اند.
- مسیرهای اصلی UI به `WorkspaceNavigation`، `ConversationListPage`، `ChatHeader`، `SettingsPage`، `ContactDirectoryModal`، Gateهای Auth/Account و `MaterialToast` تفکیک شده‌اند؛ `App.tsx` orchestration state مشترک را نگه می‌دارد.
- محتوای پیام در module مستقل `MessageContentCard.tsx` و با Cardهای Material نمایش داده می‌شود؛ پیام‌ها/آلبوم‌های متوالی همان فرستنده تا پنج دقیقه یک Card هستند و ترتیب متن، عکس و فایل حفظ می‌شود. نام نویسنده در Header است، نام Contact اولویت دارد مگر عنوان عمومی `Eitaa/ایتا` باشد، و انتخاب/ایندکس/WordPress روی همهٔ اعضای گروه اعمال می‌شود.
- آواتار گفتگو cache-first، account-scoped و failure-isolated است. cache probe و remote fetch lane مستقل دارند؛ remote برای حفاظت session مشترک Eitaa سریال می‌ماند. personal با sender key ناقص از peer گفتگو استفاده می‌کند و نبود/خرابی photo reference به initials برمی‌گردد.
- صفحهٔ ورود Material در مرکز و mobile-first است و panel معرفی معماری ندارد. نشست قطعی نامعتبر به‌صورت backup-safe و audit‌شده بازیابی و درخواست کد خودکار آغاز می‌شود؛ نشست سالم هرگز با `automatic_recovery` archive نمی‌شود و OTP/رمز دوم Provider همچنان الزامی‌اند.
- نشست AppUser و نشست Provider در client lifecycle مستقل‌اند؛ invalid شدن Eitaa توکن CSRF کاربر نرم‌افزار را پاک نمی‌کند. OTP رقم فارسی/عربی، فاصله و directional mark را امن نرمال می‌کند، خطای کد اشتباه/منقضی متن قابل اقدام دارد و دریافت کد تازه بدون افشای جزئیات نشست ممکن است.
- فونت runtime رابط `IRANSans` است و وزن‌های 400/700 از دو فایل محلی موجود، مستقیماً در `MuiCssBaseline` ثبت می‌شوند؛ fallback سیستم فقط در صورت شکست فایل استفاده می‌شود.
- رابط mobile-first است: shell صریح موبایل/دسکتاپ، safe-area، `100dvh/100svh`، bottom navigation، Dialog تمام‌صفحه، فرم‌های تک‌ستونه و touch target حداقل 44px قرارداد جاری‌اند.
- در موبایل فهرست گفتگوها نمای اولیه است؛ انتخاب دستهٔ Bottom Navigation فهرست فیلترشده را باز و Composer را می‌بندد، انتخاب گفتگو فهرست را می‌بندد و Arrow بازگشت RTL در Header آن را دوباره باز می‌کند.
- Header موبایل برای حالت عادی دریافت زنده متن موفق نمایش نمی‌دهد و فقط connecting/retrying را نشان می‌دهد. دکمهٔ WordPress با touch target ۴۸px در لبهٔ چپ، هم‌تراز منوی اصلی در لبهٔ راست است.
- جهت RTL فقط در root/Theme اعمال و در Workspace به ارث برده می‌شود؛ declaration دوبارهٔ `direction: rtl` زیر Emotion RTL Cache ممنوع است. ترتیب پذیرفته‌شدهٔ دسکتاپ از راست Navigation، Conversation List و Chat است؛ در موبایل فهرست گفتگوها از راست و Composer از چپ وارد می‌شوند.
- گفتگوی باز به‌صورت خودکار با polling تطبیقی 0.75s دسکتاپ/1.25s موبایل تازه می‌شود. فهرست گفتگوها نیز در foreground تقریباً هر 2.5s دسکتاپ/4s موبایل live-sync محدود می‌گیرد؛ hidden/save-data/offline کندتر و retry bounded است. reload یا دکمهٔ دریافت پیام تازه لازم نیست.
- live-sync فهرست صفحهٔ نخست محدود را merge می‌کند و رکوردهای قدیمی خارج از آن صفحه را hidden نمی‌کند؛ همهٔ loopها account-scoped هستند. این شاهد `AUTOMATED / NOT_LIVE_PROVIDER` است و ادعای Push/WebSocket ندارد.

### Trigger ابطال این یافته

تغییر در یکی از موارد زیر نیازمند به‌روزرسانی این فصل است:

- `ui/src/MessengerAccountGate.tsx`
- `ui/src/AccessManagementPanel.tsx`
- محل استفاده از Account controls در `ui/src/App.tsx`
- Routeهای `/api/v2/messenger-accounts`
- Schema یا Service ساخت PhoneAccount/MessengerAccount

تا قبل از این تغییرها، بررسی زندهٔ دوبارهٔ همین سؤال لازم نیست.

## فصل ۵ — وضعیت استقرار و عملیات

- پروفایل‌های `desktop_loopback`، `trusted_lan_http` و `web_reverse_proxy` از یکدیگر جدا هستند.
- Port/Host/IP سیستم توسعه قرارداد ثابت محصول نیست.
- Port 443 به TLS termination/Reverse Proxy نیاز دارد و HTTP ساده محسوب نمی‌شود.
- پورت داخلی Backend اکنون فقط از بخش Material UI «تنظیمات ← شبکه و وب» تغییر می‌کند. سرویس پیش از write قرارداد deployment را اعتبارسنجی و Host/Origin داخلی را هماهنگ می‌کند؛ mutation فقط برای مدیر، با CSRF و تأیید صریح است و پس از ذخیره restart لازم است.
- در `web_reverse_proxy` پورت عمومی HTTPS و Host/Origin عمومی تغییر نمی‌کنند؛ UI نیاز هماهنگی upstream لارگون/Proxy با پورت داخلی تازه را اعلام می‌کند. هیچ restart، bind، Firewall یا Proxy mutation خودکار انجام نمی‌شود.
- Health، readiness، drain و shutdown قراردادهای جدا دارند.
- Support Bundle، redaction و scanner پذیرفته شده‌اند.
- G-04-D با دادهٔ کاملاً ساختگی ثابت کرد Runtime Log، Audit، Diagnostic و Support Bundle شمارهٔ canonical جهانی و Bearer را حتی زیر کلید ناشناخته/تو‌در‌تو حفظ نمی‌کنند؛ scanner نیز همان الگوی جهانی را fail-closed تشخیص می‌دهد.
- Startup حساب پیش‌فرض، PID زنده را به‌تنهایی دلیل مالکیت Worker نمی‌داند. executable سیستم‌عامل نیز سنجیده می‌شود؛ PID reuse قطعی به‌صورت audit‌شده بازیابی و هویت غیرقابل‌بررسی fail-closed می‌ماند.
- Electron در اجرای source، Python module جاری workspace را به entry-point executable قدیمی ترجیح می‌دهد. نسخهٔ Backend از `VERSION.txt` canonical سنجیده می‌شود؛ بنابراین artifact یا constant قدیمی نباید Backend سالم با Health 200 را متوقف کند.
- پذیرش زندهٔ ۲۰۲۶-۰۸-۲۰ ورود ایتا و `dialogs/live-sync`/`messages/sync`/`messages/list` را با پاسخ‌های موفق تأیید کرد. ارسال/دعوت در این شاهد انجام نشد.
- هیچ تغییر Firewall، Proxy، Certificate یا انتشار واقعی در این مبنا انجام نشده است.

## فصل ۶ — منابع مرجع

- `ARCHITECTURE_DECISIONS.md`
- `../reports/phases/PHASE10_FINAL_ACCEPTANCE_REPORT_2026-08-13.md`
- `../reports/phases/PHASE10B_LOCAL_ACTIVATION_REPORT_2026-08-13.md`
- `../reports/phases/PHASE10C3_MULTI_USER_ISOLATION_ACCEPTANCE_REPORT_2026-08-13.md`
- `../reports/phases/PHASE10D_OPERATIONAL_ACCEPTANCE_REPORT_2026-08-13.md`
- `../reports/phases/PHASE7_PROCESS_ISOLATION_FINAL_REPORT_2026-08-11.md`
- `../reports/phases/PHASE8_FINAL_REPORT_2026-08-11.md`
- `../reports/phases/PHASE9_FINAL_REPORT_2026-08-12.md`
- `../reports/phases/PHASE11_0_MULTI_ACCOUNT_ONBOARDING_FOUNDATION_REPORT_2026-08-13.md`
- `../reports/phases/PHASE11B_PROVIDER_EXTENSION_FOUNDATION_REPORT_2026-08-13.md`
- `../reports/phases/PHASE11B1_MULTI_PROVIDER_CORE_REPORT_2026-08-13.md`
- `../reports/phases/PHASE11B2_PROVIDER_NEUTRAL_APPLICATION_ORCHESTRATION_REPORT_2026-08-17.md`
- `../reports/phases/PHASE11B2_PROCESS_RPC_MEDIA_CONTACT_PERSISTENCE_REPORT_2026-08-20.md`
- `../reports/blockers/PHASE11_EXTERNAL_ACCEPTANCE_BLOCKERS_2026-08-20.md`
- `../reports/features/MATERIAL_MOBILE_SELF_REGISTRATION_LIVE_SYNC_REPORT_2026-08-20.md`
- `../reports/features/BACKEND_STARTUP_PID_REUSE_RECOVERY_REPORT_2026-08-20.md`
- `../reports/features/MATERIAL_MESSAGE_CARD_AUTOMATIC_SESSION_RECOVERY_REPORT_2026-08-20.md`
- `../reports/features/LIVE_STARTUP_IRANSANS_AUTH_ACCEPTANCE_REPORT_2026-08-20.md`
- `../reports/features/RTL_LAYOUT_REGRESSION_REPAIR_REPORT_2026-08-20.md`
- `../reports/features/CENTRALIZED_DEPLOYMENT_PORT_SETTINGS_REPORT_2026-08-20.md`
- `../reports/features/MOBILE_CONVERSATION_NAVIGATION_MICROPHASE_2_1_REPORT_2026-08-20.md`
- `../reports/features/MOBILE_HEADER_MICROPHASE_2_2_REPORT_2026-08-20.md`

## فصل ۷ — Observability جاری

- Event schema نسخهٔ 1 و Event Catalog مرکزی با ۱۰۳ رخداد، شامل lifecycle امن Application/Background/Content Index، Onboarding، Provider activation، Registry/Capability، replay/interruption idempotency و health/maintenance پیاده شده است.

## فصل ۹ — مبنای چندProvider پس از تکمیل محلی 11-B2

- schema جاری Coordinator نسخهٔ 7 و Contact Store نسخهٔ 3 است؛ v7 جدول receipt عمومی و privacy-safe برای mutationهای Provider را می‌افزاید و ارتقای مستقیم v6→v7 آزموده شده است.
- `provider_registrations` منبع پایدار metadata امن است و composition root در startup آن را افزایشی reconcile می‌کند؛ Provider حذف‌شده از کد به‌طور خودکار از تاریخچه پاک نمی‌شود.
- endpoint `GET /api/v2/messenger-accounts/{id}/capabilities` پس از کنترل Membership، تصمیم حساب‌محور و امن Capability را برمی‌گرداند.
- مسیرهای Dialog/History/Send/Media/Contacts در حالت multi-session پیش از runtime با Capability guard کنترل می‌شوند.
- Fake سوم runtime/adapter آفلاین دارد، از catalog محصول پنهان است و فقط تست‌ها آن را opt-in persist می‌کنند.
- orchestrator عمومی ترتیب `AppUser -> Membership -> account context -> capability -> deadline -> adapter -> bounded result` را یک‌جا اجرا و exception ناشناخته را sanitize می‌کند.
- شش مسیر v2 عمومی Dialog/History/Text Send/Media read/Contact list/upsert افزوده شده‌اند؛ payload فیلدهای زائد یا context/capability ساختهٔ client را رد می‌کند و دو mutation به `confirm=true` و idempotency key صریح نیاز دارند.
- Eitaa compatibility adapter ترجمهٔ وضعیت موجود را خارج از orchestrator نگه می‌دارد؛ Fake سوم نیز از همین orchestrator عبور کرده است.
- Process Runtime فقط methodهای typed allowlisted را می‌پذیرد؛ fence حساب/generation، field allowlist و result mapping دوباره در Parent سنجیده می‌شوند. media cache path در Child می‌ماند و Parent فقط chunkهای Base64 محدود و پیوسته را broker می‌کند.
- receiptهای `messages.send_text` و `contacts.upsert` به actor و fingerprint درخواست bind هستند؛ replay پس از restart Provider را دوباره فراخوانی نمی‌کند و claim منقضی‌شده بدون retry به حالت `uncertain` می‌رود. متن پیام، identity، idempotency key و fingerprint وارد log نمی‌شوند و payload خام در DB ذخیره نمی‌شود.
- این نوبت پایگاه عملیاتی، Session، Config و سرویس درحال اجرا را migrate/restart نکرد؛ migration فقط روی پایگاه‌های موقت و کپی تست شد.
- Application، Provider Worker و Electron Desktop JSONL با source/result/reason/correlation ثبت می‌کنند.
- correlation از Renderer تا Electron/HTTP/Application حفظ می‌شود.
- React Error Boundary و global error/rejection handlers فعال‌اند و payload خصوصی ارسال نمی‌کنند.
- client diagnostic route و IPC هر دو allowlist و rate limit دارند.
- raw query/fragment و شناسه‌های حساس route در Desktop log ثبت نمی‌شوند.
- آخرین full suite سبز Backend برای snapshot G-11 برابر `658/658` و skip صفر است. TypeScript، همهٔ ۹ runner UI، UI/Electron Observability و build محلی 1015-module نیز سبزند. نتیجه‌های `590/590` تا `657/657` شواهد تاریخی مراحل قبلی‌اند.
- G-03 کامل و F-041 بسته است: clean-install Legacy/multi-session، bootstrap خالی، challenge binding و adversarial/restart، startup تکراری و installer config-copy rehearsal همگی آفلاین سبزند؛ Backend نهایی `610/610` است. این closure فقط G-03 است و release readiness عمومی را اعلام نمی‌کند.
- G-04-B دو RED مرحلهٔ A را بسته است: تست خالی باقی نمانده و identity hintها در observability redacted می‌شوند. جداسازی token در C و Support Bundle scan در D نیز بسته‌اند.
- G-04-C جداسازی token را بسته است: public onboarding فقط هویت تلفنی E.164 دارد و Phase 11 onboarding سبز است. اسکن جامع چهار کانال privacy نیز در G-04-D بسته شد.
- G-04-E full regression و معیارهای خروج را سبز کرد؛ G-04 کامل و F-044 بسته است. گزارش نهایی در `../reports/stabilization/G04_IDENTITY_PRIVACY_STABILIZATION_FINAL_REPORT_2026-08-26.md` ثبت شده است.
- G-05 scheduler ناقص auto-index را fail-closed حذف، manual index را حفظ و F-043 را با full Backend=`625/625` بست. گزارش نهایی در `../reports/stabilization/G05_AUTO_INDEX_LIFECYCLE_STABILIZATION_FINAL_REPORT_2026-08-26.md` است.
- G-06 test drift Phase 10 را بست، guard empty/skip را افزود و full Backend=`628/628`، همهٔ UI contractها، TypeScript و build را سبز کرد. گزارش نهایی در `../reports/stabilization/G06_TEST_CONTRACT_AND_REGRESSION_STABILIZATION_FINAL_REPORT_2026-08-26.md` است.
- G-07 allowlist/manifest، wheel parity و fresh-install را بست و F-042 را با full Backend=`643/643` خاتمه داد. گزارش نهایی در `../reports/stabilization/G07_RELEASE_PACKAGING_AND_FRESH_INSTALL_STABILIZATION_FINAL_REPORT_2026-08-26.md` است.
- G-08 scanner چندحسابی، lifecycle/background، logger health، retention/disk و Support Bundle را بست و F-048 را با full Backend=`656/656` خاتمه داد. گزارش نهایی در `../reports/stabilization/G08_OBSERVABILITY_COMPLETION_FINAL_REPORT_2026-08-26.md` است.
- G-09 archive نهایی deterministic، fresh-install آفلاین، full Backend/UI/build و handoff را پذیرفت و کاربر در V-148 closure را صریحاً تأیید کرد. گزارش نهایی در `../reports/stabilization/G09_FINAL_ACCEPTANCE_AND_HANDOFF_REPORT_2026-08-26.md` است؛ طبقه‌بندی snapshot=`USER_ACCEPTED / OFFLINE_RELEASE_CANDIDATE` است.
- G-10 بازنویسی checkpoint روی request آخرین پیام‌ها را حذف کرد، اما browser delivery آن به‌علت URL ثابت/immutable کهنه باقی ماند؛ گزارش G-10 با G-11 تصحیح شده است.
- G-11 cache-busting محتوایی runtime patch و policy تفکیک‌شدهٔ static asset را تکمیل و F-050 را در سطح کد/آزمون/بسته بست. گزارش نهایی در `../reports/stabilization/G11_RUNTIME_PATCH_CACHE_BUSTING_REPAIR_REPORT_2026-08-27.md` است؛ `USER_VISUAL_RECHECK_PENDING` باقی می‌ماند.
- ادامهٔ Live متوقف است: حساب دوم Eitaa و هر عملیات Bale به تأیید همان لحظه نیاز دارند. code-sign، Windows visual، real-user installer و Git commit/tag نیز دروازهٔ مستقل‌اند و Production release مجاز اعلام نشده است.
- retention/disk health محلی در دامنهٔ مصنوعی G-08 بسته است؛ Web metrics همچنان deployment-dependent و deferred است.

Trigger ابطال: تغییر فایل‌های diagnostics، API dispatch/HTTP header، Electron main/preload/observability یا React root/error boundary.

## فصل ۸ — مرجع ساختار و مستندات

- ورودی Agent: `../../AGENTS.md`.
- درگاه مستندات: `../README.md`.
- مشخصات پروژه: `../PROJECT_SPECIFICATION.md`.
- ساختار: `../PROJECT_STRUCTURE.md`.
- قرارداد logging: `../LOGGING_AND_OBSERVABILITY.md`.
- نقشهٔ فایل/نماد: `../project-map/PROJECT_FILE_MAP.md` و `../project-map/SYMBOL_INDEX.json`.
- فهرست گزارش‌ها: `../REPORTS_INDEX.md`.
- گزارش انتقال: `../DOCUMENT_ORGANIZATION_2026-08-13.md`.

اسناد گزارش تاریخی اکنون در `docs/reports/` دسته‌بندی شده‌اند؛ بازگشت گزارش‌ها به ریشه یا حذف cache/runtime بخشی از این Baseline نیست.
