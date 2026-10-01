# وضعیت پایهٔ فعلی پروژه

تاریخ مبنا: ۲۰۲۶-۰۸-۲۷
آخرین همسان‌سازی: SERVER-FULL-RESET در ۲۰۲۶-۰۹-۲۶
وضعیت: `PRODUCTION_DEPLOYED / SERVER_CLEAN_ONBOARDING / LIVE_EITAA_DIALOG_ACCEPTANCE_PENDING`
منابع شاهد جاری: V-103، V-108 تا V-212، F-039 تا F-082 و گزارش‌های تثبیت/ویژگی؛ شواهد Phase 7 تا 11 پیش از V-103 تاریخی و وابسته به Trigger خود هستند.

اصلاح انتخاب دسترسی سرویس (2026-10-01، F-104/V-267): رنگ ثابت theme تفاوت Chip انتخاب‌شده و انتخاب‌نشده را پنهان می‌کرد. فرم صدور اکنون برای scope، Provider و حساب از Checkbox کنترل‌شده استفاده می‌کند. ماندگاری انتخاب پس از تغییر focus، تغییر با صفحه‌کلید و منع صدور بدون حساب در مرورگرِ رابط ساخته‌شده تأیید شدند؛ هیچ credential تازه یا پیام واقعی در این بررسی ساخته نشد.

قید جاری V-252 (2026-09-30، F-099): دو نقص جست‌وجوی فراگیر Child و تکمیل نسل دوم بدون توکن اصلاح و مستقل بازآزمایی شدند. full Backend روی درخت نهایی ۱۰۴۸ پاس/۱ skip، UI check/observability/build، wheel parity و پروب‌های بله سبزند؛ پذیرش قطعی همچنان به ممیز/مالک واگذار است. جست‌وجو cursor/limit و سقف بایتی IPC دارد؛ تکمیل نسل دوم به توکن همان تلاش نیاز دارد. پاسخ خام GetContacts/SearchContacts در WebSocket پیش از کنترل ۱۶ MiB به‌طور کامل دریافت می‌شود؛ سقف دریافت transport و رفتار Live هنوز تأیید نشده‌اند. [دستور اصلاحی دوم](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_FOLLOWUP_2026-09-30.md) مرجع معیارهاست. B6 Live جداگانه در انتظار ورودی/تأیید همان‌لحظه است.

Milestone BALE-PRODUCT-REVIEW (2026-09-28، F-093/V-230): wiring بله در runtime/worker/API/M2M/UI اصلی پیاده و اسلات contract_verified با runtime/onboarding=true فعال است. نقص محتوای رسانه در Child اصلاح و stream کران‌دار شد؛ restart کل برنامه/replay، چندحسابی/چندکاربری و mutation آفلاین آزموده‌اند. وضعیت جاری OFFLINE_IMPLEMENTED / B4_BROWSER_BLOCKED / B6_LIVE_PENDING_INPUT است؛ ادعای اتمام همهٔ معیارها در V-228/V-229 superseded است. Chrome runtime متصل نیست و شاهد مرورگری موجود نیست؛ Pilot واقعی default-off اکنون ساخته شده ولی Live اجرا نشده است. مرجع گزارش BALE_FULL_PRODUCT_INTEGRATION_REPORT_2026-09-28.md و V-230.

Milestone BALE-PRODUCT-REPAIR (2026-09-29، F-099/V-247/V-249): دستور اصلاحی BALE_ACCEPTANCE_REPAIR_2026-09-29 با موفقیت کامل پیاده‌سازی و بسته شد. Coordinator schema v13 با حصار تلاش (attempt_token و attempt_generation) در جدول رسیدها مستقر گردید؛ پاک‌سازی دیرهنگام ادعای تلاش جدید را آزاد نمی‌کند (stale_release=false)؛ صفحه‌بندی کران‌دار در سمت پروسهٔ فرزند (bale_provider_worker.py) و استعلام سریع contains_contact پیاده‌سازی شد؛ آزمون کانونیکال پروسهٔ فرزند واقعی سیستم‌عامل (subprocess.Popen) با ۲۰۰۰ مخاطب مصنوعی (نام‌های ۵۱۲کاراکتری) کران‌داری تمامی فریم‌های IPC زیر ۳۵۰ کیلوبایت و پیمایش ۴ صفحهٔ ۵۰۰تایی تا آخرین مخاطب و شبیه‌سازی UI را اثبات کرد؛ ۲ آزمون پروب ایزوله، ۲۰ آزمون test_bale_main_product.py و ۱۲۳ آزمون در ۶ سوئیت بله ۱۰۰٪ پاس شدند. وضعیت آفلاین کامل است (`OFFLINE_REPAIRED_AND_VERIFIED_V249 / B6_LIVE_PENDING_INPUT`).

Milestone EDUCATION-M2M-R02: زیرساخت اتصال سامانهٔ آموزش/آزمون پس از اعتبارسنجی مستقل اصلاح و تکمیل شد (F-083 → F-084، V-213 → V-214، ADR-59). احراز هویت ماشین‌به‌ماشین با اعتبارنامهٔ `eb_svc_` جدای نشست AppUser، resolve فقط‌خواندنیِ گیرنده از دایرکتوری مخاطبین + کاتالوگ گفتگوی حساب، منع استفاده از شمارهٔ خام به‌عنوان peer_reference، وضعیت‌های رسید accepted/provider_succeeded/uncertain/not_found، داربست fail-closed بله بات (ADR-59) و درگاه عامل هوشمند با پاسخ‌های علامت‌دار آزمایشی پیاده شد. پنل UI مدیریت اعتبارنامه‌ها اکنون به endpointهای واقعی متصل است. مجموعهٔ کامل Backend، بررسی‌های UI و کنترل‌های اسناد سبزند؛ هیچ عملیات زندهٔ ایتا/بله انجام نشده و پذیرش زنده به دروازه‌های اختصاصی نیاز دارد. مرجع F-084/V-214 و قرارداد `docs/contracts/EDUCATION_SYSTEM_API_CONTRACT_v1.md` نسخهٔ 1.1.0.

بازبینی مستقل بعدی در ۲۰۲۶-۰۹-۲۷ (F-085/V-215) چهار شکاف مرز مجوز/چت را آشکار کرد که همان روز با آزمون RED بازتولید و اصلاح شدند (V-217): چرخهٔ عمر زمینهٔ سرویس، حصار صریح حساب/Provider در صدور و استفاده، scope و مالکیت سرویس در استعلام رسید (Coordinator schema v9) و قرارداد کامل چت با message_id/replay/تاریخچهٔ واقعی/پیکربندی صریح آداپتور. هیچ‌یک از سه مرز هنوز پذیرش زنده ندارد.

ممیزی بعدی همان روز (F-090/V-221) سه نقص چت را بازتولید کرد که همان روز با آزمون RED→GREEN بسته شدند (V-222): تصمیم اولین‌اجرا/replay اتمیک در-فرایندی برای message_id (با رفتار تعریف‌شدهٔ انتظار/خطا/timeout/لغو و محدودیت صریح تا restart)، انقضای نشست پیش از هر خواندن، و حفظ عین پرچم و متن پاسخ cacheشده در replay با قید message_id به محتوا (`409 agent_message_id_conflict`). پیکربندی عامل واقعی اکنون HTTPS بیرونی و HTTP فقط loopback را می‌پذیرد.

ممیزی مستقل همان تحویل (F-091/V-223) نشان داده بود اگر ذخیرهٔ تاریخچه پس از پاسخ آداپتور، مثلاً بر اثر انقضای نشست و پرشدن ظرفیت، شکست بخورد، entry درخواست در `_inflight` باقی می‌ماند و replay همان `message_id` به `agent_reply_pending` می‌رسد. همان روز با V-224 بسته شد: `AgentChatSessionStore.record_exchange` مبادلهٔ چت (پیام کاربر، پیام عامل، رکورد پاسخ) را اتمیک ذخیره می‌کند و در هر خروجی — شکست ذخیره، شکست ثبت پاسخ یا لغو — claim همان `(service, user, session, message_id)` با کد خطای واقعی تعیین تکلیف و منتظران آزاد می‌شوند؛ تاریخچهٔ نیمه‌ثبت‌شده یا پاسخ ناقص باقی نمی‌ماند و retry بعدی claim تازه می‌گیرد. ممیزی تکمیلی V-225 پنجرهٔ حذف زودهنگام claim درون همان تراکنش را RED یافت و اصلاح کرد: entry تا انتشار کامل یا rollback و اعلام خطا زیر همان قفل ثبت می‌ماند. ضمانت همچنان در-فرایندی و تا restart است و پذیرش Live جداگانه است.

Milestone BALE-PERSONAL-AUTHORIZED: به دستور صریح مالک، تفسیر fail-closed دائمی از F-046/G-02 منسوخ شد و مسیر حساب شخصی بله به‌عنوان مسیر درجه‌یک محصول در کنار scaffold بات بله بازگشت (F-086/ADR-60/V-216). ثبت بله با مانیفست مجاز و capabilities واقعی، آداپتور واقعی متصل به `bale_client` با backend تزریقی و probe قرارداد آفلاین، رفع قرنطینهٔ بسته‌بندی + وابستگی `websockets`، و بازنویسی آزمون‌های نگهبان به قرارداد جدید انجام شد. `runtime/onboarding` چندProvider تا فاز اتصال onboarding/worker صادقانه False است؛ پذیرش زندهٔ نشست روی شاخهٔ Bale (V-194) معتبر و ارسال از مسیر orchestrator همچنان Live-نیست.

Milestone SERVER-FULL-RESET: به درخواست صریح مالک، سرویس Eitaa Bridge روی سرور متوقف شد و همهٔ ۱۳۵ فایل قدیمی فضای دادهٔ مشترک آن، از جمله نشست، پایگاه داده، پشتیبان، log، Config و `.env`، حذف شدند. بستهٔ پاک نسخهٔ محلی شاخهٔ Bale منتشر شد؛ تنها release فعال باقی ماند. Config تازهٔ HTTPS Reverse Proxy، AppUser Auth و Multi-session را روشن و Worker Process را طبق شاهد رفع خالی‌ماندن فهرست محلی خاموش دارد. یک مدیر تازه با رمز تازه ساخته شد؛ نشست‌های آزمون حذف شدند و حساب پیام‌رسان صفر است. UI، readiness، ورود مدیر و فهرست حساب‌ها روی دامنهٔ عمومی پذیرفته شدند. توکن اتصال ایتا که در پروژهٔ هم‌میزبان `onlineexam` دوباره ساخته شده بود نیز از فایل و کانتینر آن پاک شد؛ شرط اجباری قدیمیِ توکن در source سرور همان پروژه اصلاح و backend آن سالم شد. نمایش گفت‌وگوهای واقعی پس از ورود تازهٔ کاربر به ایتا هنوز شاهد Live ندارد. مرجع F-080/F-082، V-212 و گزارش بازنشانی سرور.

Milestone LOCAL-SECOND-RESET: پس از آزمون ورود و بازیابی ۲۰۶ گفت‌وگو، مالک بازنشانی دوبارهٔ همین نصب را درخواست کرد. برنامه مالکیت‌دار متوقف شد، داده/نشست/پروفایل مرورگر/لاگ/Config عملیاتی این نوبت به آرشیو دوم بیرون پروژه منتقل شد و تنها مدیر تازه در Coordinator جدید باقی ماند؛ حساب پیام‌رسان و نشست صفر است. Config تازه AppUser Auth و Multi-session را روشن و Worker Process را برای UI v1 محلی خاموش دارد. نقص آغاز برنامه با مدیر ولی بدون حساب در این حالت رفع شد؛ HTTP status محلی، آزمون هدفمند و full Backend و کنترل‌های UI سبز شدند. الگوی ثابت workbook گزارش‌سازی، که دادهٔ استفادهٔ قبلی نیست و قابلیت گزارش به آن وابسته است، به پروژه برگشت. مرجع F-081/V-211.

Milestone LOCAL-CLEAN-RESET: بنا به درخواست صریح مالک، داده‌های عملیاتی محلی این درخت پس از تأیید سلامت پشتیبان مستقل به آرشیو بازگشت‌پذیر بیرون پروژه منتقل شدند. Config واقعی با نمونهٔ نصب تازه جایگزین شد و `.env` واقعی، نشست‌های Eitaa/Bale، دیتابیس‌ها، رسانه، log، diagnostics، backup، catalog، screenshot و خروجی probe از درخت جاری بیرون رفتند. Coordinator تازه فقط یک AppUser مدیر و یک credential دارد؛ PhoneAccount، MessengerAccount و AppUser session صفرند. راه‌اندازی محلی API و وضعیت ورود HTTP 200 پذیرفته شد. ۱۴ پوشهٔ کش آزمون با ACL غیرقابل‌دسترسی در ریشه مانده‌اند؛ در پشتیبان هیچ فایل زیر آن‌ها ثبت نشده است. این اقدام هیچ نشست سمت Provider یا سرور بیرونی را ابطال نکرد. مرجع V-209.

Milestone LOCAL-DIALOG-RECOVERY: ورود تازهٔ ایتا در همین نصب انجام شد، اما Config نمونه `worker_process=true` مسیر v1 فهرست سایت را با `eitaa_process_operation_ipc_required` بست و UI به مرحلهٔ sync نرسید. تنظیم عملیاتی محلی به flag قبلی `worker_process=false` برگشت؛ AppUser Auth و Multi-session روشن ماندند. پس از restart مالکیت‌دار، درخواست‌های sites، dialog sync و message list موفق و ۲۰۶ گفت‌وگو در DB محلی ثبت شد. سازگاری UI با پروفایل Worker Process روشن همچنان F-080 باز است. مرجع V-210.

Milestone AUTH-CHILD-IPC-R01: در نسخهٔ محلی `AntiGravity2` پاسخ‌های ورود با کد و رمز دوم کلید ممنوع `session` را به IPC می‌دادند. سه حالت با Core واقعی و نشست مصنوعی پیش از اصلاح شکست خوردند؛ پاسخ Child اکنون خلاصهٔ غیرمحرمانه را با `session_snapshot` می‌فرستد و آزمون‌های مرتبط `19/19` سبزند. پذیرش ورود واقعی و وضعیت سرور هنوز باز است؛ مرجع F-079/V-205.

Milestone LINUX-PRODUCTION-DEPLOYMENT-R01: سرویس روی `eitaa.farhangimaz.ir` پشت Nginx و systemd مستقر شد؛ Backend و gateway برنامهٔ دوم فقط Loopback هستند. محافظ هویت غیرWindows با AES-GCM/HMAC و کلیدهای `0600` اضافه شد و Windows DPAPI دست‌نخورده ماند. انتشار اتمیک/rollback با `publish-site deploy eitaa-bridge` پذیرفته شد. Backend=`809 passed + 1 skipped / 810`، TypeScript/Observability/Build، package privacy و Live redirect/UI/login/cookie/session سبزند. TLS عمومی Edge باید توسط کاربر در CDN فعال شود؛ origin TLS حاضر است. مرجع=F-074/ADR-55/V-196/report feature.

Milestone EITAA-AUTH-ACCOUNT-UX-R01: پس از اصلاح Linux Child، audit امن سه ورود کامل ایتا و چند خروج موفق را در اقدام خود کاربر ثبت کرد. ردهای بعدی `account_phone_mismatch` مربوط به تلاش با شماره‌ای متفاوت از هویت حساب پیام‌رسان انتخاب‌شده‌اند، نه خرابی Child. فرم ورود اکنون انتخاب و افزودن حساب، راهنمای شمارهٔ ماسک‌شده و پیام مشخص عدم تطابق را نشان می‌دهد؛ guard سمت سرور تغییر نکرد. مرجع=F-076/F-077/V-198/V-199.

Milestone MULTI-ACCOUNT-CLEAN-INSTALL-RC5: پروفایل نصب تازه اکنون AppUser Auth، Multi-session و Worker Process را هم‌زمان روشن دارد. startup بدون حساب در runtime ایزوله crash نمی‌کند؛ UI ابتدا فعال‌سازی دستگاه، سپس ساخت مدیر اولیه و بعد افزودن نخستین حساب Eitaa متعلق به همان مدیر را نشان می‌دهد. ساخت حساب اتصال/OTP/Worker را خودکار آغاز نمی‌کند. rehearsal مالکیت=`admin/owner/active`، Backend=`691/691`، UI onboarding=`8/8`، TypeScript/Observability و payload privacy سبزند. RC5 Setup=`31,295,296 / SHA 2BC28046...20CC / signer, verify-only, tamper PASS`، Portable SHA=`175D8011...E925` و Delivery ZIP=`61,883,250 / SHA 66AF0894...2D26 / 15 entries` است. پذیرش واقعی حساب دوم و مشاهدهٔ مقصد باز است. مرجع=F-067/ADR-52/V-189/report feature.

Milestone GRAPHICAL-SETUP-ACTIVATION-UX-R01: پنجرهٔ فعال‌سازی دکمه/منوی صریح Copy/Paste/Select All، `Shift+Insert` و keycode فیزیکی مستقل از layout فارسی/انگلیسی دارد و whitespace/format-control Clipboard را بدون تغییر format امضاشده پاک می‌کند. Setup تک‌فایلی به WinForms فارسی RTL با نمایش مسیر `%LOCALAPPDATA%\Programs\EitaaBridge`، preservation، progress و launch option تبدیل شد؛ Batch داخلی quiet است. خروجی‌های قبلی محلی و delivery به آرشیوهای زمان‌دار منتقل شدند. RC4 Setup=`46,855,488 / SHA E964C93B...BFA4 / signer, verify-only, tamper PASS`، Portable SHA=`8D9AE8AD...66FC` و Delivery ZIP=`92,782,790 / SHA 6DACA748...FD9E / 13 entries / private-key=0 / 8 UTF-8 BOM texts` است. Backend=`690/690`، TypeScript/Observability PASS؛ clean-machine visual/install و trust مقصد بازند. مرجع=F-066/ADR-48..50/V-188/report feature.

Milestone INTERNAL-CODE-SIGNING-R01: گواهی Self-signed داخلی RSA 3072/SHA-256 با Code Signing EKU در `Cert:\CurrentUser\My` و کلید غیرقابل‌خروج ساخته شد؛ CER عمومی/metadata/Thumbprint/راهنمای فارسی/trust installer بیرون Repository تحویل شدند. PNG کاربر بدون edit مولد به ICO استاندارد نه‌اندازه تبدیل، در Setup و payload embed و برای Desktop/Start Menu wire شد. RC3 Setup=`46,842,176 bytes / SHA 9587728C...6463 / signer pinned / --verify-only و tamper PASS` و Portable SHA=`07931D6E...3566` است؛ payload=4665، operational/private-key entry صفر. delivery ZIP SHA=`81C45B14...F15E` و هفت متن آن UTF-8 BOM سالم‌اند. full Backend=`688/688`، TypeScript و Observability PASS. clean-machine install/shortcut visual و trust مقصد بازند؛ Self-signed public reputation ندارد. مرجع=F-064/ADR-50/V-186/report feature.

Milestone LICENSE-ACTIVATION-R01: نصب بسته‌بندی‌شده پیش از Config/Coordinator/Provider به فعال‌سازی آفلاین fail-closed وابسته شد. request code فقط fingerprint هش‌شدهٔ Machine GUID و serial دیسک سیستم را حمل می‌کند؛ مجوز با Ed25519 و private key خارج از release صادر، سپس با DPAPI همان Windows user در `data/licensing/activation.dat` ذخیره می‌شود. Launcher و API مستقیم هر دو gate دارند؛ انتقال پوشه/Backup به دستگاه دیگر فعال‌سازی را منتقل نمی‌کند. RED معتبر=`5 failed + 2 environment errors + 1 pass`، targeted نهایی=`60/60` و full Backend=`684/684` است؛ TypeScript/Observability سبز. RC2 payload=`4664 files`، private-key/operational finding صفر، packaged unlicensed→activation→API rehearsal سبز و EXE SHA-256=`84453D43...0EF02F` است. کلید فعلی branch-test و EXE unsigned است؛ Production key rotation، code-sign و clean-machine UI acceptance بازند.

Milestone INSTALLER-SELF-CONTAINED-R01: بستهٔ خام دستی یک `VERSION.txt` مفقود و wheel با دو فایل source ناهماهنگ داشت و dry-run آن fail شد. builder اکنون wheel را از source بازسازی و parity/allowlist را پیش از ساخت می‌سنجد؛ Python 3.13 و dependencyهای کاملاً آفلاین را application-local همراه EXE می‌برد، Node مقصد را حذف و داده/Session/Config/log build host را fail-closed رد می‌کند. Setup تک‌فایلی Windows 10/11 x64 با `--verify-only` ساخته شد؛ payload داخلی 4397 فایل، privacy finding صفر و SHA-256 EXE=`B609DD9A...30121` دارد. related=`88/88`، full Backend=`674/674`، TypeScript و UI/Electron Observability سبزند. Windows 7 عمداً پیش از mutation رد می‌شود؛ code-sign و نصب واقعی Windows تمیز باز است.

Milestone UX-WP-AVATAR-R02: پنل WordPress برای هر scope با default خاموش opt-in است؛ در حالت پنهان taxonomy request اجرا نمی‌شود و فقط عملیات گفتگو دیده می‌شود. این عملیات فقط برای active group/channel با نقش server-derived owner/admin فعال است. گفت‌وگوی فعال از priority avatar بالاتر بهره می‌گیرد، آواتارهای فهرست delayed/background هستند و پیام فعال همچنان مقدم است؛ Provider session سریال باقی می‌ماند. cache خراب تصویر بازسازی می‌شود. full Backend=`664/664`، تمام UI runnerها، TypeScript/build، wheel/archive deterministic و fresh-install آفلاین سبزند؛ Live/Provider/WordPress انجام نشد.

Milestone UX-MESSAGE-AVATAR-R01: پیام‌ها و آلبوم‌های مجاور یک فرستنده تا پنج دقیقه و در همان روز نمایشی یک Card محتوایی می‌شوند؛ متن، run عکس و فایل به ترتیب timeline حفظ می‌شوند و انتخاب/ایندکس/usage/unread/focus همهٔ member IDها را نگه می‌دارند. آواتار cache-first و account-scoped است؛ lane سریع cached-only از lane remote تک‌صف امن جداست و failure یک peer بقیه را reject یا متوقف نمی‌کند. full Backend=`659/659`، هر ۹ runner UI، TypeScript و build 1016-module سبز است. نبود photo reference بعضی Userهای گروهی محدودیت Core است و امن به initials برمی‌گردد؛ عملیات Live/Provider انجام نشد.

Milestone IR-Roadmap: کاربر در 2026-08-27 آغاز فاز صفر هوشمندسازی ایندکس و گزارش‌سازی را مجاز کرد. نقشه‌راه canonical با F-051/V-163 ثبت شده و اقدام بعدی `IR-0-A` برای inventory منابع، provenance و تعارض‌هاست. این milestone هیچ schema، migration، UI/API محصول، الگوریتم، اتصال مدل زبانی یا scheduler خودکاری را پیاده نکرده است؛ فهرست برنامه‌ها، معنای کدهای ابلاغی و قواعد شمارش تا بررسی مستندات رسمی قطعی نیستند.

Milestone IR-0-A/SRC-IR-001: کاربر workbook برنامه‌های متناظر ۱۴۰۵ را تنها سند موجود معرفی و ثبت آن به‌عنوان مرجع را درخواست کرد. فایل با SHA-256=`B7A8A79...FB9296` فقط‌خواندنی بررسی شد: هفت sheet/ناحیهٔ جدولی و formula صفر. transcription برنامه‌ها و قواعد مستقیم ثبت شده، اما تعارض کد `80402`، معنای ستاره، grain ردیف، projection زیارت عاشورا و سایر برداشت‌ها تا پاسخ‌های شماره‌دار کاربر باز هستند. فایل اصلی untracked و خارج از Git باقی است؛ محصول/runtime/schema تغییر نکرد.

Milestone IR-0-A/External artifacts: پنج artifact مرتبط Antigravity/Sonnet که forced category، schema v4، live learning و daemon ساعتی را قطعی/تکمیل‌شده نشان می‌دادند حذف نشدند، اما با هشدار superseded و metadata اصلاح‌شده مهار شدند. فایل‌های brain مرجع اجرایی نیستند. فرضیهٔ کاربر دربارهٔ کد `80403` تأییدنشده، اعتبار تا پایان ۱۴۰۵ موقت و معنای ستاره نیازمند واحد ستادی است. آمار دستی تخمینی/ساختگی باید provenance مستقل داشته باشد و تا Q-IR-013 به verified/training truth تبدیل نمی‌شود.

Milestone IR-0-A/Value quality: کاربر Q-IR-013 را پذیرفت. مقدارهای مشاهده‌شده، اعلامی واحد، تخمینی، placeholder ساختگی و تأییدشده باید قابل‌تفکیک باشند؛ تخمینی/ساختگی بدون تأیید صریح به verified یا training truth تبدیل نمی‌شود. این تصمیم در ADR-42/F-054/V-167 ثبت شد، ولی هنوز schema/UI/export gate پیاده نشده است.

Milestone IR-0-A/Reporting grain: کاربر Q-IR-004 را با قید امکان supersession رسمی بست. ردیف اصلی workbook آمار تجمیعی کل استان برای برنامه/دوره است؛ پیام/مدرک/رویداد grain داخلی‌اند و breakdown شهرستان/رویداد برای audit و ضمیمه حفظ می‌شود. ADR-43/F-055/V-168 ثبت شدند؛ aggregation engine یا schema هنوز ساخته نشده است.

Milestone IR-0-A/Special metric and questionnaire proposal: Q-IR-005 بسته شد؛ زیارت عاشورا metric استانی/ضمیمهٔ مستقل است و main ceremony count را افزایش نمی‌دهد (F-057/ADR-45/V-171). کاربر همچنین پرسشنامهٔ الکترونیکی هر برنامه را برای اتصال خبر، عدد، مالی، دادهٔ پایه و استنباط پیشنهاد کرد. مدل مفهومی مشترک+اختصاصی در F-058 ثبت شده، اما glossary/report map و هرگونه فرم/schema/calculation engine هنوز باز و ناپیاده‌اند.

Milestone IR-0-A/Central workflow boundary: Q-IR-014 بسته شد. شهرستان‌ها کاربر سامانه نیستند و فقط از Eitaa داده می‌فرستند؛ کاربران مجاز ستادی در شبکهٔ خصوصی محلی تکمیل و review را انجام می‌دهند. WordPress مخزن/نمای فعالیت و یک source/projection است. اتوماسیون محلی یا API Agent فقط کمک‌کننده است و تأیید، محاسبهٔ استانی و export فقط با انسان مرکزی مجاز انجام می‌شود (F-060/ADR-46/V-173). role schema، کنترل دسترسی، LAN deployment و workflow محصول هنوز پیاده نشده‌اند.

Milestone IR four-level/IR-GOV-01: کاربر مدل چهارسطحی را پذیرفت: L1 ایندکس معنایی، L2 projection اختیاری WordPress، L3 هستهٔ محلی گزارش و L4 اتصال/یادگیری کنترل‌شده. Codex مدیر معماری/یکپارچه‌سازی و promoter canonical پیش‌فرض است؛ واگذاری فقط با Task Contract، worktree/file ownership، خروجی noncanonical و review انجام می‌شود. کاربر همچنان مالک دامنه و approver نهایی گزارش است. F-065/ADR-51/V-187؛ enforcement ماشینی و تمام قابلیت‌های محصول ناپیاده‌اند. collision هم‌زمان F-064/V-186/ADR-50 برای امضای داخلی حفظ و در F-059 ثبت شد.

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
| Bale Personal | `contract_verified` + مجاز به تصمیم مالک F-086/ADR-60 و ADR-61/F-092؛ configured=true، runtime=true، onboarding=true | آداپتور متصل به `bale_client` و کارخانه‌های ورکر Process و In-Process | عملیات نشست روی شاخهٔ Bale پذیرش زنده شده (V-194)؛ ورود/ارسال تازه در انتظار ورودی زنده | V-228 آفلاین سبز |
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
- Eitaa و Bale هر دو onboardable هستند. Bale با تصمیم مالک و مأموریت‌های B0 تا B6 (ADR-61/F-092) با `configured=true`، `runtime_enabled=true`، `onboarding_enabled=true` و وضعیت `contract_verified` یکپارچه شد. مدیریت کامل چندحسابی، مخاطبان، دیالوگ‌ها، پیام‌ها، رسانه و ورکر اختصاصی متصل است.
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
- احراز هویت پیام‌رسان از مرورگر راه دور فقط با flag صریح در `web_reverse_proxy` معتبر است؛ پروفایل تولید Linux آن را فعال دارد و `trusted_lan_http` همچنان درخواست‌های OTP/2FA راه دور را fail-closed رد می‌کند.
- هویت شمارهٔ حساب در AppAuth، Registry و Child بر اساس سیستم‌عامل با یک انتخاب‌گر مشترک باز می‌شود؛ Linux از کلید سرویس و Windows از DPAPI استفاده می‌کند.
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
- آخرین full suite سبز Backend برای checkpoint Setup گرافیکی/فعال‌سازی برابر `690/690` است. TypeScript و UI/Electron Observability نیز سبزند؛ UI React تغییر نکرد و شواهد همهٔ runnerها/build از UX-WP-AVATAR-R02 جاری می‌ماند. نتیجه‌های `590/590` تا `688/688` شواهد تاریخی مراحل قبلی‌اند.
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
- ادامهٔ Live متوقف است: حساب دوم Eitaa و هر عملیات Bale به تأیید همان لحظه نیاز دارند. RC4 گرافیکی با امضای داخلی و آیکون ساخته و بدون نصب verify شده است؛ trust مقصد، Windows shortcut visual و clean-machine real-user install همچنان دروازهٔ مستقل‌اند و Production release مجاز اعلام نشده است.
- retention/disk health محلی در دامنهٔ مصنوعی G-08 بسته است؛ Web metrics همچنان deployment-dependent و deferred است.

Trigger ابطال: تغییر فایل‌های diagnostics، API dispatch/HTTP header، Electron main/preload/observability یا React root/error boundary.

## وضعیت ورود وب و بازیابی آغاز نرم‌افزار (2026-09-24)

- در AppUser Auth، مرورگر برای وضعیت ورود، login و APIهای دارای نشست به Bearer
  محلی نیاز ندارد؛ نشست AppUser، کنترل حساب و CSRF مرز دسترسی کاربر هستند.
  Bearer به‌تنهایی مجوز مسیر ارسال پیام یا سایر APIهای محافظت‌شده نمی‌دهد.
- خطای آغاز ورود به پیام قابل اقدام و کد امن تبدیل می‌شود. خطای گذرا فقط یک بار
  به‌طور خودکار تکرار می‌شود؛ درخواست وضعیت ورود رویداد refresh دوباره تولید
  نمی‌کند و تلاش دستی در صفحه باقی می‌ماند.
- gate انتشار Linux باید readiness و وضعیت ورود بدون credential را از gateway
  هم‌میزبان تأیید کند و در شکست هرکدام نسخهٔ قبلی را با مسیر رسمی بازگرداند.
- سطح شاهد: آزمون کامل محلی و پذیرش زندهٔ بدون credential در V-201؛ ورود
  واقعی مدیر از HTTPS در V-202 تأیید شد. در V-203 توکن‌ها و نشست‌های فعال
  باطل شدند و کپی توکن `onlineexam` نیز حذف شد. وضعیت جاری پس از V-204:
  داده‌های عملیاتی ایتا بنا به درخواست صریح مالک کاملاً بازنشانی شدند؛ تنها
  یک AppUser با نام کاربری `آخوندیان` و نقش مدیر کل وجود دارد و هیچ حساب
  پیام‌رسان، مخاطب، فایل نشست یا ردیف نشست باقی نمانده است. سرویس و readiness
  سالم‌اند و ورود HTTPS مدیر تازه تأیید شد. backend `onlineexam` بدون توکن
  سالم است؛ اتصال ایتا و ارسال OTP آن تا پیکربندی مجاز تازه ممکن نیست.
- در V-207، نسخهٔ محلی با اصلاح پاسخ Child در release
  `20260925T194540Z-52d1b93b938b` منتشر شد. ماژول نصب‌شدهٔ سرور اصلاح را
  دارد، آزمون مصنوعی IPC را گذرانده، سرویس فعال و UI/وضعیت ورود HTTP 200
  هستند. پذیرش واقعی OTP و نمایش پس از refresh هنوز در انتظار آزمون کاربر است.

## برنامهٔ تکمیل بله و کلاینت وب (2026-09-28)

[بستهٔ دستورهای اجرایی](../implementation-plans/bridge-client-2026-09-28/README.md) از checkout محلی `c513cdf3` تهیه شد: یک مأموریت بلهٔ شخصی در محصول اصلی و نه فاز مستقل برای فرستنده، محدودیت/رزرو، مخاطب و OTP، اتصال و سیاست دادهٔ AI، کلاینت و پذیرش Live/گرم. وضعیت تمام مأموریت‌ها `PLANNED / IMPLEMENTATION_NOT_STARTED` است. تهیهٔ این اسناد نه وضعیت سرور را تغییر داده و نه آمادگی حساب/AI واقعی را تأیید می‌کند. شاهد تاریخی V-194 فهرست/جستجوی مخاطب و ارسال/تاریخچهٔ بله است، نه شاهد افزودن/حذف مخاطب در مسیر عمومی محصول. مرجع F-092 و V-226؛ قابلیت‌های جاری و حدود F-090/F-091 تغییر نکرده‌اند.

## فصل ۸ — مرجع ساختار و مستندات

ممیزی متأخر بله در 2026-09-29، F-099/V-234 و بازآزمایی V-236 پس از تحویل P3/V-235: پذیرش کامل بله همچنان رد است. مسیر پایهٔ retry پس از refill، rate واقعی upsert و HTTP 429/Retry-After اکنون سبزند؛ اما paging از 501 مخاطب فقط 500 unique و پایان جعلی می‌دهد، و همان id ردشده با متن متفاوت پس از refill ارسال می‌شود (201 به‌جای conflict) چون release، binding receipt را حذف می‌کند. وضعیت جاری `PARTIALLY_REPAIRED / OFFLINE_REPAIR_REQUIRED / B6_LIVE_PENDING_INPUT` است. 54 آزمون هدفمند سبزند ولی probe مستقل دو true/دو false و exit=1 دارد. schema جاری 12 و درخت دارای کار مشترک بله/P1/P2/P3 است؛ gate نهایی باید روی snapshot ثابت گرفته شود. [دستور اصلاحی](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) مبنای ادامهٔ R1 binding و R3 است؛ کد محصول یا دادهٔ عملیاتی در این ممیزی اصلاح نشده.

بازآزمایی جدید V-246 پس از ادعای V-244: probe چهارگانه اکنون 4/4 سبز و سناریوهای پایهٔ binding/501 مورد رفع شده‌اند؛ اما F-099 دوباره باز است. cleanup دیررسِ تلاش قبلی، ادعای تازهٔ همان owner/key/fingerprint را آزاد می‌کند (نبود attempt fence، probe مستقل RED). مسیر Child مخاطبین همچنان کل فهرست را در یک frame بدون page/limit می‌فرستد؛ body 2000 مورد مصنوعی با نام 512حرفی از سقف 1 MiB IPC بزرگ‌تر است. وضعیت جاری `PARTIALLY_REPAIRED / OFFLINE_REPAIR_REQUIRED / B6_LIVE_PENDING_INPUT`؛ گزارش V-244 تاریخی و ناکافی برای R5-A02/A03 است. [دستور اصلاح به‌روز](../implementation-plans/bridge-client-2026-09-28/BALE_ACCEPTANCE_REPAIR_2026-09-29.md) مرجع ادامه است.

بسته‌شدن موانع آفلاین V-247/V-248 (2026-09-29): R1 با attempt fence (`attempt_token` + `attempt_generation`، شمای ۱۳) و R3 با صفحه‌بندی کران‌دار Child/IPC و `contacts.contains` بسته شدند؛ پروب fence و پروب چهارگانه سبز و در V-248 روی snapshot ثابت (پس از سکوت عامل هم‌زمان) بازآزمایی شدند: full pytest 1037 passed/1 skip، UI check/observability/build سبز، wheel بازسازی‌شده با parity 15/15. runner P8 نیز با قواعد فاز هماهنگ شد (ورودی حساس خارج از argv، تأیید همان عملیات، `warm_verified` فقط با شاهد نشست/شمار connect واقعی، ai-probe با نشست admin واقعی + CSRF و رد Bearer M2M). وضعیت جاری `OFFLINE_REPAIRED / B6_LIVE_PENDING_INPUT` است؛ این هیچ پذیرش قطعی نیست — برچسب نهایی با ممیز مستقل/مالک است و آزمون Live و ادغام وب‌سایت واقعی دو مسیر مستقل نیازمند ورودی خود‌اند.

- ورودی Agent: `../../AGENTS.md`.
- درگاه مستندات: `../README.md`.
- مشخصات پروژه: `../PROJECT_SPECIFICATION.md`.
- ساختار: `../PROJECT_STRUCTURE.md`.
- قرارداد logging: `../LOGGING_AND_OBSERVABILITY.md`.
- نقشهٔ فایل/نماد: `../project-map/PROJECT_FILE_MAP.md` و `../project-map/SYMBOL_INDEX.json`.
- فهرست گزارش‌ها: `../REPORTS_INDEX.md`.
- گزارش انتقال: `../DOCUMENT_ORGANIZATION_2026-08-13.md`.

اسناد گزارش تاریخی اکنون در `docs/reports/` دسته‌بندی شده‌اند؛ بازگشت گزارش‌ها به ریشه یا حذف cache/runtime بخشی از این Baseline نیست.
قید جاری V-255 (2026-10-01، F-101): در نصب تست جداگانه، ورود واقعی OTP بله نشست را ذخیره کرد، اما نخستین `dialogs.list` با `bale_not_connected` رد شد؛ Worker پس از تأیید کد، ذخیرهٔ نشست را به‌اشتباه معادل اتصال WebSocket می‌گرفت. مسیر OTP و رمز دومرحله‌ای اصلاح شد تا نخستین درخواست Provider از vault وصل شود. آزمون بازتولید RED→GREEN و پس از راه‌اندازی دوبارهٔ نصب تست، `dialogs.list` زنده موفق و پیام خطا از UI حذف شد. این شاهد فقط ورود و خواندن گفتگوهاست؛ ارسال/تغییر مخاطب و پذیرش کامل B6 هنوز انجام نشده‌اند.

قید جاری V-256 (2026-10-01، F-101): پس از قطع دیرهنگام WebSocket، Worker اکنون خطای امن `bale_not_connected` را نشانهٔ از دست رفتن اتصال می‌داند و درخواست بعدی را از نشست ذخیره‌شده وصل می‌کند. همان درخواست شکست‌خورده خودکار تکرار نمی‌شود. آزمون قطع و بازیابی برای OTP و عامل دوم RED→GREEN شد؛ نصب تست پس از راه‌اندازی دوباره گفتگوها را خواند. شاهد Live قطع دوباره هنوز اخذ نشده و B6 mutation باز است.

قید جاری V-257 (2026-10-01): مالک موفقیت خواندن/ارسال متن/مخاطبین را در نصب تست گزارش کرد؛ لاگ امن دو ارسال متن، دو upsert و یک remove موفق به‌همراه خواندن‌ها را ثبت کرده است. B6 در همین محدوده Live جزئی دارد، اما معیارهای باقی‌مانده، پذیرش کامل و انتشار هنوز بازند.

قید جاری F-102/V-260 (2026-10-01): در نصب تست بله، تکمیل نام گفتگوهای خصوصی در هر polling پنج‌ثانیه‌ای `GetContacts` می‌زد و رد RPC با کد ۸ کل `dialogs.list` را به پیام عمومی شکست تبدیل می‌کرد. اکنون دادهٔ تکمیلی نام‌ها با مهلت ۳۰۰ ثانیه cache می‌شود، شکست `bale_rpc_error` آن خواندن گفتگو را متوقف نمی‌کند، و خطای polling رابط پس از موفقیت پاک و در شکست‌ها با فاصلهٔ افزایشی تکرار می‌شود. پس از راه‌اندازی دوبارهٔ نصب تست، چندین بازخوانی پیوستهٔ گفتگو موفق بوده است؛ پذیرش کلی B6 از این شاهد نتیجه نمی‌شود.

قید متأخر V-262 (2026-10-01): موفقیت کوتاه V-260 برای دوام کافی نبود؛ بعدتر خود `LoadDialogs` در چرخهٔ پنج‌ثانیه‌ای به‌طور متناوب با کد ۸ رد شد. UI تازه، گفتگوها را هر ۱۵ ثانیه با backoff مستقل و تاریخچهٔ گفتگوی باز را هر ۵ ثانیه می‌خواند؛ تب پنهان polling نمی‌کند و شکست گفتگو تاریخچه را متوقف نمی‌کند. سرویس تست از وضعیت خاموش با نشست ذخیره‌شده بالا آمد و مالک بازگشت گفتگوها بدون کد تازه را تأیید کرد؛ لاگ امن نیز خواندن‌های موفق با فاصلهٔ حدود ۱۵ ثانیه نشان داد. این restore گرم زنده است؛ دوام بلندمدت نرخ تازه و بازیابی از قطع WebSocket در حین اجرا هنوز جدا هستند.

قید جاری F-103/V-265 (2026-10-01): راه‌انداز Office به‌علت تضاد نسخهٔ `VERSION.txt` (Bale1) و `eitaa_bridge.version` (GMI4.2) بک‌اند سالمِ کوتاه‌مدت را متعلق به همین نسخه نمی‌شناخت و با خطای readiness متوقف می‌شد. source و کنترل‌های نسخه با manifest canonical هماهنگ شدند؛ `EitaaBridge.bat` اکنون در همین نصب بک‌اند و پنجرهٔ Edge را راه می‌اندازد و پس از مهلت heartbeat، health و identity مالکیت موفق‌اند. full Backend ۱۰۵۲ پاس/۱ skip؛ این شاهد راه‌اندازی، جایگزین آزمون Provider یا ادغام وب‌سایت نیست.

قید جاری V-269/F-105 (2026-10-01): رابط بله با الگوی فضای کاری ایتا یکپارچه شد؛ ناوبری مشترک (با props اختیاری و بدون تغییر رفتار ایتا)، فهرست گفتگو با جست‌وجو/badge، سربرگ، کارت پیام با جهت گیرنده از `sender_reference`، نوار ارسال با تأیید و idempotency، دفترچهٔ مخاطبین دیالوگی و تنظیمات با چیپ قابلیت/علت. همهٔ داده‌ها همچنان از مسیر حساب‌محور بله و قابلیت همان حساب عبور می‌کنند و قراردادهای نرخ V-262 حفظ شده‌اند. full Backend ۱۰۶۸ پاس/۱ skip، هر ۹ runner UI، build و ۱۶ آزمون قرارداد تازه سبزند؛ پذیرش مرورگری روی فیکسچر مصنوعی است و هیچ پذیرش Live یا ارسال واقعی به دنبال ندارد. مرجع: [گزارش ویژگی](../reports/features/BALE_WORKSPACE_EITAA_LAYOUT_2026-10-01.md) و F-105.
