# گزارش ریزفاز ۲.۳ — برجسته‌سازی «منتخب» در منوی پایین

تاریخ: ۲۰۲۶-۰۸-۲۱
وضعیت: `COMPLETED / FULL_AUTOMATED_VERIFIED`

«منتخب» دقیقاً گزینهٔ میانی Bottom Navigation موبایل است. با استفاده از `mobileSections` ترتیب اختصاصی همه | کانال‌ها | منتخب | گروه‌ها | شخصی روی موبایل اعمال شد، در حالی که حالت دسکتاپ دست‌نخورده باقی ماند. ظاهر گزینه `favorite` با حفظ استانداردهای Material UI به شکل دکمه شناور مرکزی (Circular Background, scale, translateY) استایل‌دهی شد.

## Validation

- افزوده شدن تست RED و شکست مورد انتظار ثابت شد (تطبیق آرایه mobileSections و استایل translateY).
- TypeScript و UI Check بدون خطا (GREEN).
- تست‌های Phase 9 و mobile navigation contract کاملاً پاس شدند (12/12).
- Observability بدون نشست اطلاعات موفق بود.
- Full Python Regression شامل 590/590 بدون تغییر بک‌اند سبز شد.
