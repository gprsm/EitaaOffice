import fs from "node:fs/promises";
import {
  Presentation,
  PresentationFile,
} from "@oai/artifact-tool";

const PROJECT = "C:/Users/Mohsen/Documents/eitaa/Eitaa_Bridge_MVP6_1_1_GMI4_2_RTL_Contacts_Quick_Send";
const TMP = `${PROJECT}/.codex_work/report_ppt`;
const FONT = "Tahoma";
const W = 1280;
const H = 720;

const C = {
  ink: "#101820",
  muted: "#56616D",
  light: "#EEF1F3",
  lighter: "#F7F8F9",
  rule: "#C7CDD3",
  blue: "#3D8DFF",
  blueLight: "#DDF3FC",
  bluePale: "#EEF8FD",
  amber: "#F59E0B",
  amberLight: "#FFF3D6",
  white: "#FFFFFF",
};

const orgs = ["اداره ۱", "اداره ۲", "اداره ۳", "اداره ۴", "اداره ۵", "اداره ۶"];
const attendees = [15, 4, 20, 30, 25, 25];
const participation = [40, 30, 50, 60, 35, 70];
const spaces = [60, 80, 50, 60, 60, 50];
const payments = [0, 10.5, 6, 6, 5, 0];
const imamType = ["همکار", "مدعو", "مدعو", "مدعو", "مدعو", "همکار"];
const regularity = ["هر روز", "نامنظم", "هر روز", "هر روز", "هر روز", "گاهی (۴)"];

function faDigits(value) {
  return String(value).replace(/[0-9]/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]).replace(/\./g, "٫");
}

function rtl(value) {
  return String(value)
    .split("\n")
    .map((line) => (line ? line.trim().split(/\s+/).reverse().join(" ") : line))
    .join("\n");
}

function makeDeck() {
  return Presentation.create({ slideSize: { width: W, height: H } });
}

function addText(slide, {
  name,
  text,
  left,
  top,
  width,
  height,
  fontSize = 22,
  bold = false,
  color = C.ink,
  alignment = "right",
  verticalAlignment = "top",
  fill = "none",
  line = { style: "solid", fill: "none", width: 0 },
  insets = { top: 0, right: 0, bottom: 0, left: 0 },
  autoFit = "shrinkText",
}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: { left, top, width, height },
    fill,
    line,
  });
  shape.text = rtl(text);
  shape.text.style = {
    typeface: FONT,
    fontSize,
    bold,
    color,
    alignment,
    verticalAlignment,
    insets,
    autoFit,
    wrap: "square",
  };
  return shape;
}

function addRect(slide, { name, left, top, width, height, fill, lineFill = "none", lineWidth = 0, radius = 0 }) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    name,
    position: { left, top, width, height },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
    ...(radius ? { borderRadius: radius } : {}),
  });
}

function addRule(slide, { name, left, top, width, color = C.rule, weight = 1 }) {
  return slide.shapes.add({
    geometry: "line",
    name,
    position: { left, top, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: weight },
  });
}

function addSlideNumber(slide, number) {
  addText(slide, {
    name: `slide-number-${number}`,
    text: faDigits(number),
    left: 41,
    top: 662,
    width: 48,
    height: 22,
    fontSize: 14,
    color: C.muted,
    alignment: "left",
    verticalAlignment: "bottom",
  });
}

function addMethodFooter(slide, text = "مبنای گزارش: اطلاعات اعلامی ادارات تابعه، همراه با بازدیدهای میدانی") {
  addText(slide, {
    name: "method-footer",
    text,
    left: 105,
    top: 651,
    width: 1090,
    height: 28,
    fontSize: 14,
    color: C.muted,
    alignment: "right",
    verticalAlignment: "bottom",
  });
}

function setSourceNotes(slide, extra = "") {
  slide.speakerNotes.textFrame.setText(
    `[Sources]\n- Report.xlsx — Sheet1!A1:J7 — داده‌های ارائه‌شده توسط کاربر.\n[/Sources]${extra ? `\n\n${extra}` : ""}`,
  );
  slide.speakerNotes.setVisible(false);
}

function addTitle(slide, title, eyebrow = "گزارش وضعیت نمازخانه‌های ادارات تابعه") {
  addText(slide, {
    name: "eyebrow",
    text: eyebrow,
    left: 650,
    top: 34,
    width: 588,
    height: 34,
    fontSize: 18,
    bold: true,
    color: C.blue,
    alignment: "right",
  });
  addText(slide, {
    name: "slide-title",
    text: title,
    left: 105,
    top: 72,
    width: 1133,
    height: 70,
    fontSize: 49,
    bold: true,
    alignment: "right",
    verticalAlignment: "middle",
    autoFit: "shrinkText",
  });
  addRule(slide, { name: "title-rule", left: 42, top: 151, width: 1196, color: C.rule, weight: 1 });
}

function addCallout(slide, { name, top, number, label, detail, accent = C.blue }) {
  addRect(slide, { name: `${name}-panel`, left: 842, top, width: 396, height: 131, fill: C.light });
  addRect(slide, { name: `${name}-accent`, left: 1226, top, width: 12, height: 131, fill: accent });
  addText(slide, {
    name: `${name}-number`,
    text: number,
    left: 884,
    top: top + 16,
    width: 318,
    height: 48,
    fontSize: 38,
    bold: true,
    alignment: "right",
    verticalAlignment: "middle",
  });
  addText(slide, {
    name: `${name}-label`,
    text: label,
    left: 884,
    top: top + 67,
    width: 318,
    height: 28,
    fontSize: 21.5,
    bold: true,
    alignment: "right",
  });
  addText(slide, {
    name: `${name}-detail`,
    text: detail,
    left: 884,
    top: top + 98,
    width: 318,
    height: 22,
    fontSize: 19,
    color: C.muted,
    alignment: "right",
  });
}

function addAttendanceChart(slide, { left = 50, top = 172, width = 735, height = 420, title = "تعداد نمازگزاران ثبت‌شده" } = {}) {
  const chartOrgs = [...orgs].reverse().map(rtl);
  const chartAttendees = [...attendees].reverse();
  const chart = slide.charts.add("bar", {
    position: { left, top, width, height },
    title: rtl(title),
    titlePlacement: "aboveChart",
    titleTextStyle: { fontSize: 22, bold: true, fill: C.ink, alignment: "right", typeface: FONT },
    categories: chartOrgs,
    series: [{
      name: "نمازگزار",
      categories: chartOrgs,
      values: chartAttendees,
      fill: C.blue,
      points: [
        { idx: 2, fill: C.amber },
        { idx: 4, fill: C.amber },
      ],
      valuesFormatCode: "0",
    }],
    hasLegend: false,
    dataLabels: {
      showValue: true,
      position: "outEnd",
      textStyle: { fontSize: 16, bold: true, fill: C.ink, typeface: FONT },
    },
    chartFill: C.white,
    chartLine: { style: "solid", width: 0, fill: C.white },
    plotAreaFill: { type: "none" },
    plotAreaLine: { style: "solid", width: 0, fill: C.white },
    xAxis: {
      visible: true,
      min: 0,
      max: 35,
      majorUnit: 5,
      majorGridlines: { style: "solid", fill: C.light, width: 1 },
      line: { style: "solid", fill: C.rule, width: 1 },
      textStyle: { fontSize: 14, fill: C.muted, typeface: FONT },
    },
    yAxis: {
      visible: true,
      line: { style: "solid", fill: "none", width: 0 },
      textStyle: { fontSize: 16, fill: C.ink, typeface: FONT },
    },
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 55 },
  });
  return chart;
}

function buildSample1() {
  const deck = makeDeck();
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "وضعیت نمازخانه‌های ۶ اداره تابعه در یک نگاه");
  addAttendanceChart(slide, { left: 42, top: 172, width: 745, height: 410 });
  addCallout(slide, {
    name: "attendance-summary",
    top: 172,
    number: "۱۱۹",
    label: "مجموع حضور ثبت‌شده",
    detail: "نفر | میانگین هر اداره: حدود ۲۰ نفر",
  });
  addCallout(slide, {
    name: "participation-summary",
    top: 314,
    number: "۴۷٫۵٪",
    label: "میانگین نسبت مشارکت",
    detail: "بالاترین نسبت: اداره ۶ با ۷۰٪",
  });
  addCallout(slide, {
    name: "payment-summary",
    top: 456,
    number: "۲۷٫۵",
    label: "مجموع حق‌القدم ائمه مدعو",
    detail: "میلیون تومان | ائمه همکار: صفر",
    accent: C.amber,
  });
  addRect(slide, { name: "caveat-panel", left: 42, top: 602, width: 1196, height: 43, fill: C.amberLight });
  addText(slide, {
    name: "attendance-caveat",
    text: "تعداد نمازگزاران ادارات ۲ و ۴ تقریبی است؛ به دلیل مأموریت‌های کاری و سرکشی سازمانی، برای مقایسه نهایی نیاز به تعدیل دارد.",
    left: 64,
    top: 611,
    width: 1152,
    height: 25,
    fontSize: 17,
    bold: true,
    color: "#7A4B00",
    alignment: "right",
  });
  addSlideNumber(slide, 1);
  setSourceNotes(slide, "مبالغ حق‌القدم بر حسب میلیون تومان است.");
  return deck;
}

function addMetricPanel(slide, { left, number, headline, detail, accent = C.blue }) {
  addRect(slide, { name: `metric-panel-${left}`, left, top: 328, width: 374, height: 280, fill: C.light });
  addRect(slide, { name: `metric-accent-${left}`, left, top: 328, width: 374, height: 10, fill: accent });
  addText(slide, {
    name: `metric-number-${left}`,
    text: number,
    left: left + 28,
    top: 364,
    width: 318,
    height: 78,
    fontSize: 54,
    bold: true,
    alignment: "right",
    verticalAlignment: "bottom",
  });
  addText(slide, {
    name: `metric-headline-${left}`,
    text: headline,
    left: left + 28,
    top: 454,
    width: 318,
    height: 44,
    fontSize: 23,
    bold: true,
    alignment: "right",
  });
  addText(slide, {
    name: `metric-detail-${left}`,
    text: detail,
    left: left + 28,
    top: 510,
    width: 318,
    height: 70,
    fontSize: 18,
    color: C.muted,
    alignment: "right",
  });
}

function addSummarySlide(deck) {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "زیرساخت مناسب؛ تمرکز بر مشارکت و انتظام");
  addText(slide, {
    name: "summary-copy",
    text: "در هر ۶ اداره پخش منظم اذان و فعالیت فرهنگی ثبت شده است.\nحضور مدیران در ۵ اداره مستمر و در یک اداره گاه‌به‌گاه گزارش شده است.",
    left: 205,
    top: 188,
    width: 1033,
    height: 88,
    fontSize: 24,
    color: C.muted,
    alignment: "right",
    verticalAlignment: "middle",
  });
  addMetricPanel(slide, {
    left: 42,
    number: "۶۰",
    headline: "مترمربع؛ میانگین فضای نمازخانه",
    detail: "دامنه ثبت‌شده: ۵۰ تا ۸۰ مترمربع",
  });
  addMetricPanel(slide, {
    left: 453,
    number: "۴",
    headline: "اداره با حضور روزانه\nامام جماعت",
    detail: "اداره ۲: نامنظم\nاداره ۶: گاه‌به‌گاه",
    accent: C.amber,
  });
  addMetricPanel(slide, {
    left: 864,
    number: "۴",
    headline: "امام جماعت مدعو",
    detail: "۲ امام همکار بدون حق‌القدم\n۴ امام مدعو با حق‌القدم",
  });
  addMethodFooter(slide);
  addSlideNumber(slide, 1);
  setSourceNotes(slide);
}

function addComparisonTableSlide(deck) {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "مقایسه ادارات و نقاط پیگیری");
  addText(slide, {
    name: "table-intro",
    text: "تمرکز جدول بر شاخص‌های تصمیم‌ساز است؛ مقادیر علامت‌دار برای مقایسه نهایی نیازمند تعدیل‌اند.",
    left: 240,
    top: 165,
    width: 998,
    height: 42,
    fontSize: 21.5,
    color: C.muted,
    alignment: "right",
  });

  const values = [["حق‌القدم", "انتظام امام", "نوع امام", "فضا (م²)", "مشارکت", "نمازگزار", "اداره"].map(rtl)];
  for (let i = 0; i < 6; i += 1) {
    values.push([
      faDigits(payments[i]),
      rtl(regularity[i]),
      rtl(imamType[i]),
      faDigits(spaces[i]),
      `${faDigits(participation[i])}٪`,
      `${faDigits(attendees[i])}${i === 1 || i === 3 ? "*" : ""}`,
      faDigits(i + 1),
    ]);
  }
  const table = slide.tables.add({
    rows: 7,
    columns: 7,
    left: 42,
    top: 220,
    width: 1196,
    height: 350,
    columnWidths: [155, 186, 150, 150, 160, 170, 125],
    values,
  });
  table.borders.assign({ style: "solid", fill: C.rule, width: 1 });
  table.styleOptions = { headerRow: true, bandedRows: false };
  for (let r = 0; r < 7; r += 1) {
    for (let c = 0; c < 7; c += 1) {
      const cell = table.getCell(r, c);
      cell.fill = r === 0 ? C.ink : (r === 2 || r === 4 ? C.amberLight : (r % 2 === 0 ? C.lighter : C.white));
      cell.text.style = {
        typeface: FONT,
        fontSize: r === 0 ? 18 : 17,
        bold: r === 0 || c === 6,
        color: r === 0 ? C.white : C.ink,
        alignment: "center",
        verticalAlignment: "middle",
        autoFit: "shrinkText",
      };
    }
  }
  addRect(slide, { name: "table-caveat", left: 42, top: 590, width: 1196, height: 52, fill: C.amberLight });
  addText(slide, {
    name: "table-caveat-text",
    text: "علامت ستاره: اعداد ادارات ۲ و ۴ برای مقایسه نهایی با کارکنان حاضر در بازه نماز تعدیل شود.",
    left: 65,
    top: 599,
    width: 1150,
    height: 34,
    fontSize: 16,
    bold: true,
    color: "#7A4B00",
    alignment: "right",
  });
  addMethodFooter(slide, "حق‌القدم بر حسب میلیون تومان | مبنا: اطلاعات اعلامی ادارات تابعه و بازدیدهای میدانی");
  addSlideNumber(slide, 2);
  setSourceNotes(slide, "مبالغ حق‌القدم بر حسب میلیون تومان است؛ ائمه جماعت همکار مبلغ صفر دارند.");
}

function buildSample2() {
  const deck = makeDeck();
  addSummarySlide(deck);
  addComparisonTableSlide(deck);
  return deck;
}

function addCoverSlide(deck) {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addText(slide, {
    name: "cover-kicker",
    text: "نمونه روایی قابل توسعه",
    left: 810,
    top: 44,
    width: 428,
    height: 34,
    fontSize: 19,
    bold: true,
    color: C.blue,
    alignment: "right",
  });
  addText(slide, {
    name: "cover-title",
    text: "گزارش وضعیت\nنمازخانه‌های ادارات تابعه",
    left: 220,
    top: 225,
    width: 1018,
    height: 245,
    fontSize: 74,
    bold: true,
    alignment: "right",
    verticalAlignment: "bottom",
    autoFit: "shrinkText",
  });
  addRule(slide, { name: "cover-rule", left: 590, top: 505, width: 648, color: C.blue, weight: 5 });
  addText(slide, {
    name: "cover-subtitle",
    text: "شش اداره | حضور، زیرساخت و انتظام اقامه نماز",
    left: 490,
    top: 536,
    width: 748,
    height: 52,
    fontSize: 28,
    color: C.muted,
    alignment: "right",
  });
  addText(slide, {
    name: "cover-source",
    text: "بر پایه اطلاعات اعلامی ادارات و بازدیدهای میدانی",
    left: 665,
    top: 618,
    width: 573,
    height: 30,
    fontSize: 17,
    color: C.muted,
    alignment: "right",
  });
  addSlideNumber(slide, 1);
  setSourceNotes(slide);
}

function addParticipationSlide(deck) {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "مشارکت؛ مکمل تعداد نمازگزاران");
  const chartOrgs = [...orgs].reverse().map(rtl);
  const chartParticipation = [...participation].reverse();
  const chart = slide.charts.add("bar", {
    position: { left: 42, top: 184, width: 760, height: 405 },
    title: rtl("نسبت مشارکت ثبت‌شده در هر اداره"),
    titlePlacement: "aboveChart",
    titleTextStyle: { fontSize: 22, bold: true, fill: C.ink, typeface: FONT, alignment: "right" },
    categories: chartOrgs,
    series: [{
      name: "مشارکت",
      categories: chartOrgs,
      values: chartParticipation,
      fill: C.blue,
      points: [
        { idx: 2, fill: C.amber },
        { idx: 4, fill: C.amber },
      ],
      valuesFormatCode: "0\"%\"",
    }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 16, bold: true, fill: C.ink, typeface: FONT } },
    chartFill: C.white,
    chartLine: { style: "solid", width: 0, fill: C.white },
    plotAreaFill: { type: "none" },
    plotAreaLine: { style: "solid", width: 0, fill: C.white },
    xAxis: {
      visible: true,
      min: 0,
      max: 80,
      majorUnit: 20,
      numberFormatCode: "0\"%\"",
      majorGridlines: { style: "solid", fill: C.light, width: 1 },
      line: { style: "solid", fill: C.rule, width: 1 },
      textStyle: { fontSize: 14, fill: C.muted, typeface: FONT },
    },
    yAxis: { visible: true, line: { style: "solid", fill: "none", width: 0 }, textStyle: { fontSize: 16, fill: C.ink, typeface: FONT } },
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 55 },
  });
  void chart;
  addCallout(slide, {
    name: "participation-top",
    top: 184,
    number: "۷۰٪",
    label: "بالاترین نسبت مشارکت",
    detail: "اداره ۶؛ امام جماعت همکار",
  });
  addCallout(slide, {
    name: "participation-mid",
    top: 326,
    number: "۵۰٪+",
    label: "در سه اداره",
    detail: "ادارات ۳، ۴ و ۶",
  });
  addCallout(slide, {
    name: "participation-low",
    top: 468,
    number: "۳۰٪",
    label: "کمترین نسبت ثبت‌شده",
    detail: "اداره ۲؛ همراه با حضور نامنظم امام",
    accent: C.amber,
  });
  addRect(slide, { name: "ratio-note", left: 42, top: 606, width: 1196, height: 39, fill: C.amberLight });
  addText(slide, {
    name: "ratio-note-text",
    text: "نسبت‌های ادارات ۲ و ۴ پس از تثبیت شمارش کارکنان حاضر، دوباره محاسبه شود.",
    left: 66,
    top: 614,
    width: 1148,
    height: 23,
    fontSize: 17,
    bold: true,
    color: "#7A4B00",
    alignment: "right",
  });
  addSlideNumber(slide, 2);
  setSourceNotes(slide);
}

function addPaymentAndActionSlide(deck) {
  const slide = deck.slides.add();
  slide.background.fill = C.white;
  addTitle(slide, "حق‌القدم و اولویت کیفیت اجرا");
  const chartOrgs = [...orgs].reverse().map((x) => rtl(x.replace("*", "")));
  const chartPayments = [...payments].reverse();
  slide.charts.add("bar", {
    position: { left: 42, top: 182, width: 745, height: 405 },
    title: rtl("حق‌القدم امام جماعت به تفکیک اداره — میلیون تومان"),
    titlePlacement: "aboveChart",
    titleTextStyle: { fontSize: 21.5, bold: true, fill: C.ink, typeface: FONT, alignment: "right" },
    categories: chartOrgs,
    series: [{
      name: "حق‌القدم",
      categories: chartOrgs,
      values: chartPayments,
      fill: C.blue,
      points: [{ idx: 0, fill: C.rule }, { idx: 5, fill: C.rule }],
      valuesFormatCode: "0.0",
    }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 16, bold: true, fill: C.ink, typeface: FONT } },
    chartFill: C.white,
    chartLine: { style: "solid", width: 0, fill: C.white },
    plotAreaFill: { type: "none" },
    plotAreaLine: { style: "solid", width: 0, fill: C.white },
    xAxis: { visible: true, min: 0, max: 12, majorUnit: 2, majorGridlines: { style: "solid", fill: C.light, width: 1 }, line: { style: "solid", fill: C.rule, width: 1 }, textStyle: { fontSize: 14, fill: C.muted, typeface: FONT } },
    yAxis: { visible: true, line: { style: "solid", fill: "none", width: 0 }, textStyle: { fontSize: 16, fill: C.ink, typeface: FONT } },
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 55 },
  });
  addCallout(slide, {
    name: "payment-total",
    top: 182,
    number: "۲۷٫۵",
    label: "مجموع حق‌القدم ائمه مدعو",
    detail: "میلیون تومان | در چهار اداره",
  });
  addCallout(slide, {
    name: "employee-imams",
    top: 324,
    number: "۲",
    label: "بدون حق‌القدم",
    detail: "امام جماعت همکار | ادارات ۱ و ۶",
  });
  addCallout(slide, {
    name: "next-actions",
    top: 466,
    number: "۳",
    label: "تثبیت داده و کیفیت اجرا",
    detail: "تعدیل ۲ و ۴؛ انتظام امام در ۲ و ۶",
    accent: C.amber,
  });
  addRect(slide, { name: "close-message", left: 42, top: 606, width: 1196, height: 39, fill: C.bluePale });
  addText(slide, {
    name: "close-message-text",
    text: "جمع‌بندی مدیریتی: زیرساخت عمومی فراهم است؛ اولویت، تثبیت مبنای سنجش حضور و ارتقای انتظام اقامه نماز است.",
    left: 66,
    top: 614,
    width: 1148,
    height: 23,
    fontSize: 17.5,
    bold: true,
    color: "#174F72",
    alignment: "right",
  });
  addSlideNumber(slide, 3);
  setSourceNotes(slide, "مبالغ حق‌القدم بر حسب میلیون تومان است؛ مبلغ ائمه جماعت همکار صفر است.");
}

function buildSample3() {
  const deck = makeDeck();
  addCoverSlide(deck);
  addParticipationSlide(deck);
  addPaymentAndActionSlide(deck);
  return deck;
}

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

async function exportDeck(deck, finalPath, qaFolder) {
  await fs.mkdir(qaFolder, { recursive: true });
  for (let i = 0; i < deck.slides.items.length; i += 1) {
    const slide = deck.slides.items[i];
    const stem = `slide-${String(i + 1).padStart(2, "0")}`;
    await writeBlob(`${qaFolder}/${stem}.png`, await deck.export({ slide, format: "png", scale: 1.5 }));
    await fs.writeFile(`${qaFolder}/${stem}.layout.json`, await (await slide.export({ format: "layout" })).text());
  }
  await writeBlob(`${qaFolder}/montage.webp`, await deck.export({ format: "webp", montage: true, scale: 1 }));
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(finalPath);
  const inspect = await deck.inspect({ kind: "slide,textbox,shape,table,chart,notes", maxChars: 30000 });
  await fs.writeFile(`${qaFolder}/inspect.ndjson`, inspect.ndjson, "utf8");
}

if (process.env.QA_SINGLE_ONLY !== "1") {
await exportDeck(
  buildSample1(),
  `${PROJECT}/نمونه_1_گزارش_نمازخانه_مدیریتی.pptx`,
  `${TMP}/qa_sample_1`,
);
await exportDeck(
  buildSample2(),
  `${PROJECT}/نمونه_2_گزارش_نمازخانه_تحلیلی.pptx`,
  `${TMP}/qa_sample_2`,
);
await exportDeck(
  buildSample3(),
  `${PROJECT}/نمونه_3_گزارش_نمازخانه_روایی.pptx`,
  `${TMP}/qa_sample_3`,
);
}

const qaSingleSlides = [
  ["qa_s3_slide1.pptx", addCoverSlide],
  ["qa_s3_slide2.pptx", addParticipationSlide],
  ["qa_s3_slide3.pptx", addPaymentAndActionSlide],
];
for (const [fileName, addSlide] of qaSingleSlides) {
  const qaDeck = makeDeck();
  addSlide(qaDeck);
  const qaPptx = await PresentationFile.exportPptx(qaDeck);
  await qaPptx.save(`${TMP}/${fileName}`);
}

console.log("Created 3 editable PPTX samples.");
