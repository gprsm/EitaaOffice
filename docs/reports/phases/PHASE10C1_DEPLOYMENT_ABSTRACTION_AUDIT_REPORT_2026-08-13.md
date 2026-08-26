# گزارش Phase 10-C1 — ممیزی انتزاع استقرار — 2026-08-13

## نتیجه

**C1 کامل و پذیرفته شد.** وضعیت Public/DHCP/Firewall رایانهٔ توسعه از قرارداد محصول جدا شد و
سه پروفایل `desktop_loopback`، `trusted_lan_http` و `web_reverse_proxy` مرزهای مستقل و fail-closed
دارند. هیچ IP، Host، Port یا مسیر متعلق به این رایانه در منطق استقرار جدید ثبت نشد.

## تغییرات قابل‌حمل

- Config اکنون mode وب مستقل، limits و قرارداد reverse proxy را مدل می‌کند.
- Electron و Office endpoint را از `bridge.json` می‌خوانند و Host/Port موازی به backend تحمیل نمی‌کنند.
- endpoint رسانه در Renderer حذف و با protocol خصوصی `eitaa-media` به main process منتقل شد؛ CSP نیز
  دیگر به پورت ثابت backend وابسته نیست.
- پیکربندی نصب‌شدهٔ desktop فقط روی Loopback پذیرفته می‌شود؛ Launcher برای mode دیگر fail-closed است.
- پورت 80 در Config و انتخاب bind قابل تنظیم است، بدون اینکه در این مرحله bind واقعی انجام شود.
- HTTP server داخلی پورت 443 را رد می‌کند؛ 443 فقط در قرارداد TLS terminator خارجی معنا دارد.

مقادیر Loopback/default موجود، default محصول و سازگاری نسخه‌های قبلی‌اند و مشاهدهٔ شبکهٔ این
رایانه نیستند. نمونه‌های مستند نیز از دامنه‌های رزروشدهٔ example استفاده می‌کنند و باید در زمان
استقرار جایگزین شوند.

## شواهد

- `tests/test_runtime_ownership.py`: Config-driven endpoint، ownership و Launcher contracts؛
- `tests/test_phase10c_web_reverse_proxy_contract.py`: پروفایل وب، 80/443 و نمونهٔ checked-in؛
- Syntax Electron: موفق؛ TypeScript: موفق؛ build تولیدی: موفق؛
- مجموعهٔ مشترک Portability/Web: 33/33 موفق؛
- regression پیکربندی/LAN/Runtime نیز موفق ماند.

## عملیات بیرونی انجام‌نشده

هیچ bind واقعی 80/443، نصب Proxy، certificate، تغییر Firewall/Router/Network Profile، ارسال ایتا یا
انتشار WordPress انجام نشد. `bridge.json` واقعی تغییر نکرد و سرویس واقعی با پروفایل Loopback حفظ شد.

## دروازهٔ خروج

C1 پذیرفته است و ادامه به C2 مجاز شد.
