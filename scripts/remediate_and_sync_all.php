<?php
/**
 * Script to remediate 18 quality news packages, trash 53 defective template posts,
 * and synchronize everything with reporting.sqlite3 database.
 */

require_once 'c:/Users/mohse/laragon/www/cultural-portal/config.php';
require_once 'c:/Users/mohse/laragon/www/cultural-portal/includes/Database.php';

$wpDb = Database::getWordPressDb();
$repDb = Database::getReportingDb();
$prefix = Database::getWpPrefix();

echo "====================================================================\n";
echo "  شروع عملیات جامع اصلاح، پالایش، زباله‌دان و همگام‌سازی سامانه گزارش\n";
echo "====================================================================\n\n";

// ۱. انتقال ۵۳ پست ناقص و قالبی (نظیر ۲۰۵۷، ۲۱۸۶، ۲۳۴۲، ۲۳۸۸، ۲۳۹۵) به زباله‌دان
$trashSql = "UPDATE {$prefix}posts 
             SET post_status = 'trash' 
             WHERE post_type = 'post' 
               AND post_content LIKE '%در راستای اجرای برنامه‌های مصوب فرهنگی سال ۱۴۰۵ دادگستری کل استان مازندران، فعالیت و رویداد فرهنگی%'
               AND post_status != 'trash'";
$stmtTrash = $wpDb->prepare($trashSql);
$stmtTrash->execute();
$trashedCount = $stmtTrash->rowCount();
echo "۱. [زباله‌دان] تعداد {$trashedCount} پست ناقص، قالبی و بدون متن/عکس به زباله‌دان منتقل گردید.\n\n";

// نگاشت پیوست‌های تصاویر هر پست
$attachmentsMap = [
    928 => [951, 952, 953, 954],
    929 => [956, 957, 958, 959],
    930 => [961, 962, 963, 964],
    931 => [966, 967, 968, 969],
    932 => [971, 972, 973, 974],
    933 => [976, 977, 978, 979],
    934 => [981, 982, 983, 984],
    935 => [986, 987],
    936 => [989, 990, 991, 992],
    937 => [994, 995, 996, 997],
    938 => [1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040, 1041, 1042, 1043, 1044, 1045],
    939 => [1004, 1005],
    940 => [1007, 1008, 1009, 1010],
    941 => [1012, 1013, 1014, 1015],
    942 => [1017, 1018],
    943 => [1020, 1021],
    944 => [1023, 1024, 1025, 1026],
    945 => [1028, 1029, 1030, 1031],
];

// نگاشت دسته‌بندی‌ها برای هر پست
$categoriesMap = [
    928 => [2, 20, 12], // اردوهای فرهنگی زیارتی, 1405, مرداد
    929 => [2, 20, 12],
    930 => [2, 20, 30], // شهریور
    931 => [11, 7, 20, 12], // مراسم, دینی و مذهبی, 1405, مرداد
    932 => [11, 7, 20, 30], // مراسم, دینی و مذهبی, 1405, شهریور
    933 => [121, 11, 20, 12, 30], // قرائت زیارت عاشورا و ادعیه, مراسم, 1405, مرداد, شهریور
    934 => [11, 14, 20, 30], // مراسم, ملی و انقلابی, 1405, شهریور
    935 => [11, 14, 20, 30],
    936 => [11, 7, 20, 30],
    937 => [117, 16, 20, 12, 30], // اقامه نماز, نماز و مهدویت, 1405, مرداد, شهریور
    938 => [117, 5, 20, 30], // اقامه نماز, تکریم و تجلیل, 1405, شهریور
    939 => [117, 5, 20, 30],
    940 => [5, 20, 30], // تکریم و تجلیل, 1405, شهریور
    941 => [5, 6, 20, 30], // تکریم و تجلیل, خدمات آموزشی, 1405, شهریور
    942 => [13, 9, 20, 12], // مسابقات, قرآن و عترت, 1405, مرداد
    943 => [13, 17, 20, 30], // مسابقات, ورزشی, 1405, شهریور
    944 => [107, 119, 20, 12], // ارباب رجوع, میز خدمت, 1405, مرداد
    945 => [229, 6, 20, 30], // منشور اخلاقی, خدمات اداری, 1405, شهریور
];

// نگاشت برچسب‌ها
$tagsMap = [
    928 => ['مشهد مقدس', 'اردو', 'کارکنان و خانواده‌ها', 'مازندران'],
    929 => ['قم و جمکران', 'اردو', 'فعالان فرهنگی', 'مازندران'],
    930 => ['کوهپیمایی', 'اردو', 'نکا', 'سواحل', 'مازندران'],
    931 => ['محرم', 'سوگواری', 'مراسم', 'عزاداری', 'مازندران'],
    932 => ['صفر', 'اربعین', 'موکب', 'جاماندگان اربعین', 'مازندران'],
    933 => ['زیارت عاشورا', 'قرائت ادعیه', 'نمازخانه', 'مازندران'],
    934 => ['هفته دولت', 'روز کارمند', 'شهید رجایی', 'شهید باهنر', 'مازندران'],
    935 => ['هفته دفاع مقدس', 'یادواره شهدا', 'فضاسازی', 'مازندران'],
    936 => ['هفته وحدت', 'میلاد پیامبر', 'امام صادق', 'جشن', 'مازندران'],
    937 => ['نماز جماعت', 'نماز ظهر و عصر', 'بیان احکام', 'نمازخانه', 'مازندران'],
    938 => ['ستاد اقامه نماز', 'رئیس کل دادگستری', 'تجلیل خادمان نماز', 'مازندران'],
    939 => ['ائمه جماعات', 'خادمین نماز', 'تقدیر', 'نمازخانه', 'مازندران'],
    940 => ['کارمند نمونه', 'بازنشستگان', 'تکریم و تجلیل', 'رئیس کل', 'مازندران'],
    941 => ['فرزندان ممتاز', 'نخبگان علمی', 'تجلیل', 'کنکور', 'مازندران'],
    942 => ['مسابقات قرآن', 'قرآن و عترت', 'قاریان', 'حافظان', 'مازندران'],
    943 => ['مسابقات ورزشی', 'فوتسال', 'جام شهدا', 'تنیس', 'مازندران'],
    944 => ['میز خدمت', 'دیدار مردمی', 'ارباب رجوع', 'حقوق شهروندی', 'مازندران'],
    945 => ['منشور اخلاقی', 'سلامت اداری', 'رفتار حرفه‌ای', 'نظارت', 'مازندران'],
];

// اطلاعات نگاشت رویدادها به سامانه گزارش
$eventsSyncMap = [
    928 => [
        'event_id' => 'ev-1405-trip-mashhad-mordad',
        'program_kinds' => ['trip'],
        'occurred_on' => '2026-08-06',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل استان مازندران',
        'occasion' => 'ارتقای نشاط معنوی و تجدید قوای روحی همکاران و خانواده‌ها',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 2880,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'trip',
        'notes' => 'برگزاری اردوی زیارتی مشهد مقدس ویژه کارکنان دادگستری استان مازندران و خانواده‌های معزز',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 120, 'note' => 'تعداد شرکت‌کنندگان'],
            ['metric' => 'attendees', 'value' => 120, 'note' => 'مشارکت کل'],
            ['metric' => 'families_count', 'value' => 35, 'note' => 'تعداد خانواده‌ها']
        ]
    ],
    929 => [
        'event_id' => 'ev-1405-trip-qom-jamkaran-mordad',
        'program_kinds' => ['trip'],
        'occurred_on' => '2026-08-13',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل استان مازندران',
        'occasion' => 'اردوی زیارتی و بصیرتی فعالان فرهنگی دادگستری استان',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 1440,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'trip',
        'notes' => 'برگزاری اردوی زیارتی و بصیرتی قم و مسجد مقدس جمکران ویژه فعالان فرهنگی دادگستری استان',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 45, 'note' => 'فعالان فرهنگی'],
            ['metric' => 'attendees', 'value' => 45, 'note' => 'مشارکت کل']
        ]
    ],
    930 => [
        'event_id' => 'ev-1405-trip-neka-shores-shahrivar',
        'program_kinds' => ['trip'],
        'occurred_on' => '2026-08-27',
        'unit' => 'judicial_domain',
        'unit_name' => 'دادگستری شهرستان نکا',
        'occasion' => 'اردوی تفریحی، ورزشی و فرهنگی همکاران قضایی و اداری استان (نکا و سواحل)',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 480,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'trip',
        'notes' => 'برگزاری اردوی تفریحی، ورزشی و فرهنگی همکاران قضایی و اداری استان در نکا و سواحل خزر',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 55, 'note' => 'همکاران شرکت‌کننده'],
            ['metric' => 'attendees', 'value' => 55, 'note' => 'مشارکت کل']
        ]
    ],
    931 => [
        'event_id' => 'ev-1405-ceremony-moharram-mordad',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-07-23',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی مازندران',
        'occasion' => 'سوگواری و آیین‌های عزاداری دهه اول و دوم محرم',
        'occasion_class' => 'religious',
        'official_present' => 1,
        'duration_minutes' => 120,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'ceremonies',
        'notes' => 'گزارش جامع سوگواری و آیین‌های عزاداری دهه اول و دوم محرم در دادگستری کل و حوزه‌های قضایی مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 850, 'note' => 'عزاداران حسینی'],
            ['metric' => 'attendees', 'value' => 850, 'note' => 'مشارکت کل']
        ]
    ],
    932 => [
        'event_id' => 'ev-1405-ceremony-safar-arbaeen-shahrivar',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-08-24',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی مازندران',
        'occasion' => 'آیین‌های سوگواری ایام ماه صفر، برپایی موکب‌ها و همایش جاماندگان اربعین',
        'occasion_class' => 'religious',
        'official_present' => 1,
        'duration_minutes' => 180,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'ceremonies',
        'notes' => 'آیین‌های سوگواری ایام ماه صفر، برپایی موکب‌ها و همایش جاماندگان اربعین حسینی در دادگستری مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 620, 'note' => 'عزاداران و زائران'],
            ['metric' => 'attendees', 'value' => 620, 'note' => 'مشارکت کل']
        ]
    ],
    933 => [
        'event_id' => 'ev-1405-ceremony-ashura-weekly-mordad',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-07-30',
        'unit' => 'provincial_hq',
        'unit_name' => 'نمازخانه‌های دادگستری کل و حوزه‌های قضایی مازندران',
        'occasion' => 'برگزاری مستمر مراسم معنوی قرائت هفتگی زیارت عاشورا و ادعیه',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 60,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 1,
        'section' => 'ceremonies',
        'notes' => 'برگزاری مستمر مراسم معنوی قرائت هفتگی زیارت عاشورا و ادعیه در نمازخانه‌های دادگستری استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 450, 'note' => 'همکاران حاضر در دعا'],
            ['metric' => 'attendees', 'value' => 450, 'note' => 'مشارکت کل']
        ]
    ],
    934 => [
        'event_id' => 'ev-1405-ceremony-gov-week-shahrivar',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-08-26',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل مازندران',
        'occasion' => 'گرامیداشت هفته دولت و روز کارمند و تجدید میثاق با آرمان‌های شهدا',
        'occasion_class' => 'national',
        'official_present' => 1,
        'duration_minutes' => 150,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'ceremonies',
        'notes' => 'گرامیداشت هفته دولت و روز کارمند و تجدید میثاق با آرمان‌های شهدای والامقام در دادگستری مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 280, 'note' => 'حاضران در مراسم'],
            ['metric' => 'attendees', 'value' => 280, 'note' => 'مشارکت کل']
        ]
    ],
    935 => [
        'event_id' => 'ev-1405-ceremony-defa-moghaddas-shahrivar',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-09-22',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی مازندران',
        'occasion' => 'فضاسازی گسترده محیطی و آغاز برنامه‌های بزرگداشت هفته دفاع مقدس',
        'occasion_class' => 'revolutionary',
        'official_present' => 1,
        'duration_minutes' => 90,
        'prior_announcement' => 1,
        'had_reception' => 0,
        'is_ashura_pilgrimage' => 0,
        'section' => 'ceremonies',
        'notes' => 'فضاسازی گسترده محیطی و آغاز برنامه‌های بزرگداشت هفته دفاع مقدس در حوزه‌های قضایی مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 310, 'note' => 'مشارکت در آیین'],
            ['metric' => 'attendees', 'value' => 310, 'note' => 'مشارکت کل']
        ]
    ],
    936 => [
        'event_id' => 'ev-1405-ceremony-unity-week-shahrivar',
        'program_kinds' => ['ceremony'],
        'occurred_on' => '2026-09-19',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری مازندران',
        'occasion' => 'جشن میلاد حضرت رسول اکرم (ص) و امام جعفر صادق (ع) و گرامیداشت هفته وحدت',
        'occasion_class' => 'religious',
        'official_present' => 1,
        'duration_minutes' => 120,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'ceremonies',
        'notes' => 'جشن میلاد حضرت رسول اکرم (ص) و امام جعفر صادق (ع) و گرامیداشت هفته وحدت در دادگستری مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 350, 'note' => 'حاضران در جشن'],
            ['metric' => 'attendees', 'value' => 350, 'note' => 'مشارکت کل']
        ]
    ],
    937 => [
        'event_id' => 'ev-1405-prayer-daily-jamaat-mordad',
        'program_kinds' => ['prayer'],
        'occurred_on' => '2026-08-01',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی استان مازندران',
        'occasion' => 'اقامه مستمر نمازهای جماعت ظهر و عصر و بیان احکام بین‌الصلاتین',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 45,
        'prior_announcement' => 1,
        'had_reception' => 0,
        'is_ashura_pilgrimage' => 0,
        'section' => 'prayer',
        'notes' => 'اقامه مستمر نمازهای جماعت ظهر و عصر و بیان احکام بین‌الصلاتین در دادگستری کل و حوزه‌های قضایی استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 950, 'note' => 'نمازگزاران روزانه'],
            ['metric' => 'attendees', 'value' => 950, 'note' => 'مشارکت کل']
        ]
    ],
    938 => [
        'event_id' => 'ev-1405-prayer-setad-tajlil-shahrivar',
        'program_kinds' => ['prayer'],
        'occurred_on' => '2026-09-03',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل مازندران',
        'occasion' => 'آیین تجلیل از رئیس‌کل دادگستری مازندران و خادمان نماز با حضور مدیر ستاد اقامه نماز استان',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 120,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'prayer',
        'notes' => 'آیین تجلیل از رئیس‌کل دادگستری مازندران و خادمان نماز با حضور مدیر ستاد اقامه نماز استان',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 110, 'note' => 'حاضران در همایش'],
            ['metric' => 'attendees', 'value' => 110, 'note' => 'مشارکت کل']
        ]
    ],
    939 => [
        'event_id' => 'ev-1405-prayer-aemeh-tajlil-shahrivar',
        'program_kinds' => ['prayer'],
        'occurred_on' => '2026-09-06',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری مازندران',
        'occasion' => 'آیین تجلیل و تقدیر از ائمه محترم جماعات، خادمین و فعالان اقامه نماز',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 90,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'prayer',
        'notes' => 'آیین تجلیل و تقدیر از ائمه محترم جماعات، خادمین و فعالان اقامه نماز در دادگستری مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 65, 'note' => 'ائمه جماعات و خادمین'],
            ['metric' => 'attendees', 'value' => 65, 'note' => 'مشارکت کل']
        ]
    ],
    940 => [
        'event_id' => 'ev-1405-honor-exemplary-staff-shahrivar',
        'program_kinds' => ['honor'],
        'occurred_on' => '2026-08-27',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری مازندران',
        'occasion' => 'آیین استانی تکریم و تجلیل از کارکنان نمونه، قضات، ایثارگران و بازنشستگان با حضور رئیس کل',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 180,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'honor',
        'notes' => 'آیین استانی تکریم و تجلیل از کارکنان نمونه، قضات، ایثارگران و بازنشستگان دادگستری مازندران با حضور رئیس کل',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 220, 'note' => 'حاضران در آیین تکریم'],
            ['metric' => 'attendees', 'value' => 220, 'note' => 'مشارکت کل']
        ]
    ],
    941 => [
        'event_id' => 'ev-1405-honor-elite-students-shahrivar',
        'program_kinds' => ['honor'],
        'occurred_on' => '2026-09-09',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری استان مازندران',
        'occasion' => 'تجلیل و اهدای هدایا به فرزندان ممتاز تحصیلی و نخبگان علمی کارکنان',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 120,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'honor',
        'notes' => 'تجلیل و اهدای هدایا به فرزندان ممتاز تحصیلی و نخبگان علمی کارکنان دادگستری استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 145, 'note' => 'دانش‌آموزان و دانشجویان ممتاز'],
            ['metric' => 'attendees', 'value' => 145, 'note' => 'مشارکت کل']
        ]
    ],
    942 => [
        'event_id' => 'ev-1405-contest-quran-province-mordad',
        'program_kinds' => ['contest', 'quran_contest'],
        'occurred_on' => '2026-08-11',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی استان مازندران',
        'occasion' => 'برگزاری مرحله استانی مسابقات سراسری قرآن و عترت ویژه کارکنان و خانواده‌ها',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 360,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'contest',
        'notes' => 'برگزاری مرحله استانی مسابقات سراسری قرآن و عترت ویژه کارکنان و خانواده‌های دادگستری استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 180, 'note' => 'متسابقین قرآن کریم'],
            ['metric' => 'attendees', 'value' => 180, 'note' => 'مشارکت کل']
        ]
    ],
    943 => [
        'event_id' => 'ev-1405-contest-sports-service-martyrs-shahrivar',
        'program_kinds' => ['contest'],
        'occurred_on' => '2026-09-01',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی استان مازندران',
        'occasion' => 'برگزاری دوره مسابقات ورزشی و فرهنگی جام شهدای خدمت در حوزه‌های قضایی',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 480,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'contest',
        'notes' => 'برگزاری دوره مسابقات ورزشی و فرهنگی جام شهدای خدمت در حوزه‌های قضایی استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 160, 'note' => 'ورزشکاران و شرکت‌کنندگان'],
            ['metric' => 'attendees', 'value' => 160, 'note' => 'مشارکت کل']
        ]
    ],
    944 => [
        'event_id' => 'ev-1405-customer-care-miz-khedmat-mordad',
        'program_kinds' => ['customer_care'],
        'occurred_on' => '2026-08-16',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری کل و حوزه‌های قضایی استان مازندران',
        'occasion' => 'برپایی مستمر میزهای خدمت جهادی و دیدارهای چهره‌به‌چهره مردمی مسئولان و دادستان‌ها',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 240,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'customer_care',
        'notes' => 'برپایی مستمر میزهای خدمت جهادی و دیدارهای چهره‌به‌چهره مردمی مسئولان و دادستان‌های استان مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 420, 'note' => 'مراجعان و مراجعین خدمت'],
            ['metric' => 'attendees', 'value' => 420, 'note' => 'مشارکت کل']
        ]
    ],
    945 => [
        'event_id' => 'ev-1405-charter-tabyini-shahrivar',
        'program_kinds' => ['charter'],
        'occurred_on' => '2026-08-30',
        'unit' => 'provincial_hq',
        'unit_name' => 'دادگستری مازندران',
        'occasion' => 'برگزاری دوره تبیینی و نظارت بر اجرای منشور اخلاقی و ارتقای سلامت اداری',
        'occasion_class' => null,
        'official_present' => 1,
        'duration_minutes' => 180,
        'prior_announcement' => 1,
        'had_reception' => 1,
        'is_ashura_pilgrimage' => 0,
        'section' => 'charter',
        'notes' => 'برگزاری دوره تبیینی و نظارت بر اجرای منشور اخلاقی و ارتقای سلامت اداری در دادگستری مازندران',
        'facts' => [
            ['metric' => 'participants_count', 'value' => 190, 'note' => 'فراگیران و کارکنان'],
            ['metric' => 'attendees', 'value' => 190, 'note' => 'مشارکت کل']
        ]
    ]
];

// نگاشت نام تگ به term_id
$termTaxMap = [];
$sqlTerms = "SELECT t.term_id, t.name, tt.term_taxonomy_id, tt.taxonomy 
             FROM {$prefix}terms t 
             JOIN {$prefix}term_taxonomy tt ON t.term_id = tt.term_id";
foreach ($wpDb->query($sqlTerms)->fetchAll() as $t) {
    $termTaxMap[$t['taxonomy']][$t['name']] = [
        'term_id' => (int)$t['term_id'],
        'term_taxonomy_id' => (int)$t['term_taxonomy_id']
    ];
    $termTaxMap[$t['taxonomy']][(int)$t['term_id']] = (int)$t['term_taxonomy_id'];
}

function getOrCreateTagTaxId($wpDb, $prefix, &$termTaxMap, $tagName) {
    if (isset($termTaxMap['post_tag'][$tagName])) {
        return $termTaxMap['post_tag'][$tagName]['term_taxonomy_id'];
    }
    $slug = sanitize_title_with_dashes($tagName);
    $wpDb->prepare("INSERT INTO {$prefix}terms (name, slug, term_group) VALUES (?, ?, 0)")->execute([$tagName, $slug]);
    $termId = (int)$wpDb->lastInsertId();
    $wpDb->prepare("INSERT INTO {$prefix}term_taxonomy (term_id, taxonomy, description, parent, count) VALUES (?, 'post_tag', '', 0, 0)")->execute([$termId]);
    $ttId = (int)$wpDb->lastInsertId();
    $termTaxMap['post_tag'][$tagName] = ['term_id' => $termId, 'term_taxonomy_id' => $ttId];
    return $ttId;
}

function sanitize_title_with_dashes($title) {
    return preg_replace('/\s+/', '-', trim($title));
}

echo "۲. به‌روزرسانی محتوا، تنظیم وضعیت pending و الصاق تگ‌ها و دسته‌های ۱۸ بسته خبری:\n";

foreach ($eventsSyncMap as $postId => $syncData) {
    // خواندن پست جاری
    $stmtP = $wpDb->prepare("SELECT * FROM {$prefix}posts WHERE ID = ?");
    $stmtP->execute([$postId]);
    $post = $stmtP->fetch();
    if (!$post) {
        echo "  [ERROR] پست {$postId} یافت نشد!\n";
        continue;
    }

    $content = $post['post_content'];
    // پاکسازی کامل آدرس‌های ۱92.168.1.2 و localhost و تبدیل به مسیر نسبی استاندارد /wp-content/uploads/...
    $content = str_replace('http://192.168.1.2', '', $content);
    $content = str_replace('http://localhost', '', $content);

    // به‌روزرسانی در دیتابیس با وضعیت قطعی pending (در انتظار تایید)
    $stmtUp = $wpDb->prepare("UPDATE {$prefix}posts 
                             SET post_content = ?, 
                                 post_status = 'pending', 
                                 post_modified = NOW(), 
                                 post_modified_gmt = NOW() 
                             WHERE ID = ?");
    $stmtUp->execute([$content, $postId]);

    // تنظیم تصویر شاخص
    $attIds = $attachmentsMap[$postId] ?? [];
    if (!empty($attIds)) {
        $thumbId = $attIds[0];
        $stmtThumb = $wpDb->prepare("INSERT INTO {$prefix}postmeta (post_id, meta_key, meta_value) 
                                     VALUES (?, '_thumbnail_id', ?) 
                                     ON DUPLICATE KEY UPDATE meta_value = ?");
        $stmtThumb->execute([$postId, $thumbId, $thumbId]);
    }

    // حذف دسته‌بندی‌ها و برچسب‌های قبلی
    $wpDb->prepare("DELETE FROM {$prefix}term_relationships WHERE object_id = ?")->execute([$postId]);

    // الصاق دسته‌بندی‌ها
    $catIds = $categoriesMap[$postId] ?? [20];
    foreach ($catIds as $catId) {
        $ttId = $termTaxMap['category'][$catId] ?? null;
        if ($ttId) {
            $wpDb->prepare("INSERT IGNORE INTO {$prefix}term_relationships (object_id, term_taxonomy_id, term_order) VALUES (?, ?, 0)")
                 ->execute([$postId, $ttId]);
            $wpDb->prepare("UPDATE {$prefix}term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = ?")->execute([$ttId]);
        }
    }

    // الصاق برچسب‌ها
    $tagNames = $tagsMap[$postId] ?? ['مازندران', '1405'];
    foreach ($tagNames as $tName) {
        $ttId = getOrCreateTagTaxId($wpDb, $prefix, $termTaxMap, $tName);
        $wpDb->prepare("INSERT IGNORE INTO {$prefix}term_relationships (object_id, term_taxonomy_id, term_order) VALUES (?, ?, 0)")
             ->execute([$postId, $ttId]);
        $wpDb->prepare("UPDATE {$prefix}term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = ?")->execute([$ttId]);
    }

    echo "  [WP OK] پست {$postId} اصلاح شد: وضعیت=pending | تصاویر=" . count($attIds) . " | دسته‌ها=" . count($catIds) . " | برچسب‌ها=" . count($tagNames) . "\n";
}

echo "\n۳. همگام‌سازی رویدادها، سنجه‌ها و پیوندهای وردپرس با پایگاه داده سامانه گزارش (reporting.sqlite3):\n";

$nowUtc = gmdate('Y-m-d\TH:i:s\Z');

foreach ($eventsSyncMap as $postId => $data) {
    $eventId = $data['event_id'];
    $kindsJson = json_encode($data['program_kinds'], JSON_UNESCAPED_UNICODE);
    
    // ۱. ثبت / به‌روزرسانی در reported_events
    $stmtEv = $repDb->prepare("
        INSERT INTO reported_events (
            event_id, program_kinds_json, occurred_on, unit, unit_name,
            occasion, occasion_class, official_present, is_standalone_titled,
            duration_minutes, prior_announcement, had_reception,
            is_ashura_pilgrimage, contains_inner_contest, campaign, notes, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 0, '', ?, ?, 'human_curated')
        ON CONFLICT(event_id) DO UPDATE SET
            program_kinds_json = excluded.program_kinds_json,
            occurred_on = excluded.occurred_on,
            unit = excluded.unit,
            unit_name = excluded.unit_name,
            occasion = excluded.occasion,
            occasion_class = excluded.occasion_class,
            official_present = excluded.official_present,
            duration_minutes = excluded.duration_minutes,
            prior_announcement = excluded.prior_announcement,
            had_reception = excluded.had_reception,
            is_ashura_pilgrimage = excluded.is_ashura_pilgrimage,
            notes = excluded.notes
    ");
    $stmtEv->execute([
        $eventId,
        $kindsJson,
        $data['occurred_on'],
        $data['unit'],
        $data['unit_name'],
        $data['occasion'],
        $data['occasion_class'],
        $data['official_present'],
        $data['duration_minutes'],
        $data['prior_announcement'],
        $data['had_reception'],
        $data['is_ashura_pilgrimage'],
        $data['notes'],
        $nowUtc
    ]);

    // ۲. ثبت سنجه‌ها در event_facts
    $repDb->prepare("DELETE FROM event_facts WHERE event_id = ?")->execute([$eventId]);
    foreach ($data['facts'] as $idx => $fact) {
        $factId = "fact-{$eventId}-" . ($idx + 1);
        $stmtF = $repDb->prepare("
            INSERT INTO event_facts (
                fact_id, event_id, metric, value, value_kind, unit_of_measure,
                scope, evidence_refs_json, source, created_at, created_by, note
            ) VALUES (?, ?, ?, ?, 'verified', 'count', 'province', '[]', 'manual', ?, 'human_curated', ?)
        ");
        $stmtF->execute([
            $factId,
            $eventId,
            $fact['metric'],
            $fact['value'],
            $nowUtc,
            $fact['note']
        ]);
    }

    // ۳. ثبت پیوند وردپرس در wp_post_links
    $linkId = "link-wp-{$postId}";
    $postTitle = $wpDb->query("SELECT post_title FROM {$prefix}posts WHERE ID = {$postId}")->fetchColumn();
    // حذف پیوند قدیمی بر اساس post_slug یا link_id
    $repDb->prepare("DELETE FROM wp_post_links WHERE post_slug = ? OR link_id = ?")->execute([(string)$postId, $linkId]);
    $stmtLink = $repDb->prepare("
        INSERT INTO wp_post_links (
            link_id, post_slug, title, source_ref, section, published_on,
            event_id, match_status, confidence, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', 1.0, 'همگام‌سازی قطعی با وردپرس و کارنامه استانی ۱۴۰۵', ?)
    ");
    $stmtLink->execute([
        $linkId,
        (string)$postId,
        $postTitle,
        "wp:post:{$postId}",
        $data['section'],
        $data['occurred_on'],
        $eventId,
        $nowUtc
    ]);

    echo "  [REP OK] رویداد {$eventId} -> پست WP:{$postId} ثبت و تایید گردید.\n";
}

echo "\n====================================================================\n";
echo "  عملیات با موفقیت به پایان رسید.\n";
echo "====================================================================\n";
