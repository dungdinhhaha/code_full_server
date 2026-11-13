// Build SMIOT_05_Use_case.docx from docs/submission/05_tai_lieu_use_case.md
// Node script using the `docx` npm package already present in node_modules.
// Run: node outputs/submission_word/build_docx.cjs

const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Table,
  TableRow,
  TableCell,
  WidthType,
  ShadingType,
  BorderStyle,
  ImageRun,
  TableOfContents,
  Header,
  Footer,
  PageNumber,
  PageBreak,
  LevelFormat,
  convertInchesToTwip,
  VerticalAlign,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const FIG_DIR = path.join(ROOT, "outputs", "submission_export", "figures");
const OUT_PATH = path.join(ROOT, "outputs", "submission_word", "SMIOT_05_Use_case.docx");

// ---------------------------------------------------------------------------
// Front matter (from docs/submission/05_tai_lieu_use_case.md YAML header)
// ---------------------------------------------------------------------------
const FRONT = {
  title: "Tài liệu use case SMIOT",
  project: "SMIOT Smart Farm",
  competition: "Mini Hackathon MongoDB x Datadog 2026",
  version: "0.9-draft",
  date: "2026-11-06",
  data_label: "synthetic",
};

// ---------------------------------------------------------------------------
// Fonts / sizes
// ---------------------------------------------------------------------------
const FONT = "Times New Roman";
const MONO_FONT = "Consolas";
const BODY_SIZE = 24; // 12pt
const CELL_SIZE = 20; // 10pt
const PAGE_WIDTH_TWIP = 11906;
const PAGE_HEIGHT_TWIP = 16838;
const MARGIN_TWIP = 1440; // 1 inch
const CONTENT_WIDTH_TWIP = PAGE_WIDTH_TWIP - 2 * MARGIN_TWIP; // 9026

const SHADE_LEFT_COL = "D9E2F3"; // light blue, used with ShadingType.CLEAR

// ---------------------------------------------------------------------------
// Inline markdown parsing: **bold**, `code`, plain text -> TextRun[]
// ---------------------------------------------------------------------------
function parseInline(text, baseOpts = {}) {
  const runs = [];
  // Tokenize on **bold** and `code` without consuming across them.
  const tokenRe = /(\*\*[^*]+\*\*)|(`[^`]+`)/g;
  let lastIndex = 0;
  let m;
  const pushPlain = (s) => {
    if (s.length === 0) return;
    runs.push(new TextRun({ text: s, font: FONT, size: baseOpts.size || BODY_SIZE, bold: baseOpts.bold, italics: baseOpts.italics }));
  };
  while ((m = tokenRe.exec(text)) !== null) {
    if (m.index > lastIndex) pushPlain(text.slice(lastIndex, m.index));
    if (m[1]) {
      const inner = m[1].slice(2, -2);
      runs.push(new TextRun({ text: inner, font: FONT, size: baseOpts.size || BODY_SIZE, bold: true }));
    } else if (m[2]) {
      const inner = m[2].slice(1, -1);
      runs.push(new TextRun({ text: inner, font: MONO_FONT, size: baseOpts.size || BODY_SIZE, bold: baseOpts.bold }));
    }
    lastIndex = tokenRe.lastIndex;
  }
  if (lastIndex < text.length) pushPlain(text.slice(lastIndex));
  if (runs.length === 0) runs.push(new TextRun({ text: "", font: FONT, size: baseOpts.size || BODY_SIZE }));
  return runs;
}

function para(text, opts = {}) {
  return new Paragraph({
    children: parseInline(text, opts),
    alignment: opts.alignment,
    spacing: opts.spacing || { after: 120 },
    bullet: opts.bullet,
    numbering: opts.numbering,
  });
}

// Split a markdown table-cell string on "<br>" into separate Paragraphs
// (per the no-"\n"-in-text rule: every line is its own Paragraph).
function cellParas(text, opts = {}) {
  const parts = String(text).split(/<br\s*\/?>/i);
  return parts.map((p, i) =>
    new Paragraph({
      children: parseInline(p.trim(), { size: CELL_SIZE }),
      spacing: i === parts.length - 1 ? { after: 0 } : { after: 60 },
    })
  );
}

function headingCell(text) {
  return new TableCell({
    width: { size: 0, type: WidthType.DXA }, // overridden by columnWidths on Table
    shading: { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL },
    verticalAlign: VerticalAlign.TOP,
    children: cellParas(text, { bold: true }),
  });
}

function bodyCell(text) {
  return new TableCell({
    width: { size: 0, type: WidthType.DXA },
    verticalAlign: VerticalAlign.TOP,
    children: cellParas(text),
  });
}

// ---------------------------------------------------------------------------
// Generic table builders
// ---------------------------------------------------------------------------

// Key/value "Mục | Nội dung" table used for each use case spec (left column shaded).
function kvTable(rows) {
  const widths = [Math.round(CONTENT_WIDTH_TWIP * 0.18), CONTENT_WIDTH_TWIP - Math.round(CONTENT_WIDTH_TWIP * 0.18)];
  return new Table({
    width: { size: CONTENT_WIDTH_TWIP, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: [
          new TableCell({
            width: { size: widths[0], type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL },
            children: [para("Mục", { bold: true, size: CELL_SIZE, spacing: { after: 0 } })],
          }),
          new TableCell({
            width: { size: widths[1], type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL },
            children: [para("Nội dung", { bold: true, size: CELL_SIZE, spacing: { after: 0 } })],
          }),
        ],
      }),
      ...rows.map(
        ([label, content]) =>
          new TableRow({
            children: [
              new TableCell({
                width: { size: widths[0], type: WidthType.DXA },
                shading: { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL },
                verticalAlign: VerticalAlign.TOP,
                children: cellParas(label, { bold: true }),
              }),
              new TableCell({
                width: { size: widths[1], type: WidthType.DXA },
                verticalAlign: VerticalAlign.TOP,
                children: cellParas(content),
              }),
            ],
          })
      ),
    ],
  });
}

// Generic data table with header row, explicit column width ratios (sum to 1).
function dataTable(headers, ratios, rows, shadeFirstCol = false) {
  let widths = ratios.map((r) => Math.round(CONTENT_WIDTH_TWIP * r));
  const diff = CONTENT_WIDTH_TWIP - widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += diff;

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map(
      (h, i) =>
        new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL },
          children: [para(h, { bold: true, size: CELL_SIZE, spacing: { after: 0 } })],
        })
    ),
  });

  const bodyRows = rows.map(
    (r) =>
      new TableRow({
        children: r.map((cellText, i) => {
          const shaded = shadeFirstCol && i === 0;
          return new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            verticalAlign: VerticalAlign.TOP,
            shading: shaded ? { type: ShadingType.CLEAR, color: "auto", fill: SHADE_LEFT_COL } : undefined,
            children: cellParas(cellText, shaded ? { bold: true } : {}),
          });
        }),
      })
  );

  return new Table({
    width: { size: CONTENT_WIDTH_TWIP, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...bodyRows],
  });
}

function tableCaption(text) {
  return new Paragraph({
    children: parseInline(text, { bold: true, size: CELL_SIZE }),
    spacing: { before: 160, after: 80 },
  });
}

function imageParagraph(figName, widthPx, heightPx) {
  const data = fs.readFileSync(path.join(FIG_DIR, figName));
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 120 },
    children: [
      new ImageRun({
        type: "png",
        data,
        transformation: { width: widthPx, height: heightPx },
      }),
    ],
  });
}

function bulletPara(text) {
  return new Paragraph({
    children: parseInline(text),
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 80 },
  });
}

function orderedPara(text) {
  return new Paragraph({
    children: parseInline(text),
    numbering: { reference: "decimal-list", level: 0 },
    spacing: { after: 80 },
  });
}

// ===========================================================================
// COVER PAGE
// ===========================================================================
const coverChildren = [
  new Paragraph({
    spacing: { before: 2400, after: 400 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: FRONT.project, font: FONT, size: 44, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 800 },
    children: [new TextRun({ text: FRONT.competition, font: FONT, size: 28 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 400 },
    children: [new TextRun({ text: FRONT.title, font: FONT, size: 36, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 1200 },
    children: [new TextRun({ text: "Mục hồ sơ: Phụ lục", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    children: [new TextRun({ text: `Phiên bản: ${FRONT.version}`, font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 800 },
    children: [new TextRun({ text: `Ngày: ${FRONT.date}`, font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 0 },
    children: [new TextRun({ text: "Dữ liệu tổng hợp (synthetic data)", font: FONT, size: 24, italics: true })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ===========================================================================
// TABLE OF CONTENTS PAGE
// ===========================================================================
const tocChildren = [
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "Mục lục", font: FONT, bold: true })],
  }),
  new TableOfContents("Mục lục", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ===========================================================================
// BODY CONTENT
// ===========================================================================
const body = [];

function h1(text) {
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, font: FONT, bold: true })] }));
}
function h2(text) {
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, font: FONT, bold: true })] }));
}
function h3(text) {
  body.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, font: FONT, bold: true })] }));
}
function p(text, opts = {}) {
  body.push(para(text, opts));
}
function pBold(text) {
  body.push(para(text, { bold: true }));
}
function table(t) {
  body.push(t);
}

// ---- Tóm tắt ----
h1("Tóm tắt");
p(
  "Tài liệu này đặc tả các use case của SMIOT Smart Farm: tác nhân nào tương tác với hệ thống, hệ thống phản ứng ra sao trong từng tình huống, và mỗi use case được hiện thực ở đâu trong mã nguồn. Bài toán trung tâm là xác định dữ liệu cảm biến nhà màng còn đủ tin cậy để quyết định tưới hay không, và phân biệt ba lớp lỗi cần ba phản ứng khác nhau [E-16]. Hồ sơ có 24 use case đã đặc tả: 19 có nguồn mã đã đối chiếu, 3 đang bổ sung, 2 đang bổ sung xác nhận [E-30, E-55, E-82]. Hiện trạng ngày 06/11/2026 gồm dữ liệu tổng hợp, PLC ảo, chỉ Greenhouse A có dữ liệu và trang `/chart` chỉ điều hướng sang Datadog [E-02, E-13, E-17]. Các mục còn thiếu bằng chứng được liệt kê trong Phụ lục A. Hệ thống phục vụ hai mục đích đã biết là quản lý nông trại và thiết bị, và giám sát phần mềm và thiết bị; mục đích thứ ba «ĐANG BỔ SUNG: mục đích thứ ba» chưa được xác định (xem mục Mục đích hệ thống)."
);

// ---- Mục đích hệ thống ----
h1("Mục đích hệ thống");
p(
  "Các use case dưới đây hiện thực mục tiêu chung của dự án (Tài liệu 01): để người vận hành quyết định tưới dựa trên dữ liệu đáng tin, và để nhóm phát hiện, điều tra và phục hồi có kiểm chứng khi phần mềm hoặc dịch vụ có lỗi."
);
p("Hệ thống có ba mục đích. Hai mục đích đầu được xác định từ mã nguồn và hồ sơ; mục đích thứ ba đang bổ sung căn cứ.");
p(
  "1. **Mục đích 1: quản lý nông trại và thiết bị.** Người vận hành quan sát trạng thái farm, xem đề xuất AI, điều khiển bơm ảo và lập lịch tưới. Chuỗi xử lý là quan sát → quyết định → lịch → tưới. Bơm và thiết bị là PLC ảo; dữ liệu cảm biến là luồng tổng hợp, không đến từ thiết bị vật lý [E-02, E-13]. Use case lịch tưới UC-06 còn đang bổ sung (mục 3.2)."
);
p(
  "2. **Mục đích 2: giám sát phần mềm và thiết bị.** Hệ thống phát hiện khi phần mềm hoặc thiết bị có lỗi, điều tra nguyên nhân và phục hồi có kiểm chứng. Ca 1, Ca 2 và Ca 3 là ba minh họa cho ba lớp lỗi: Ca 1 là lỗi hiển thị trạng thái (UC-12, UC-13), Ca 2 là dữ liệu cảm biến đứng số đo (UC-14, UC-15), Ca 3 là tiến trình ứng dụng dừng (UC-16, UC-17) [E-16]."
);
p("3. **Mục đích thứ ba:** «ĐANG BỔ SUNG: mục đích thứ ba». Mục đích này đang bổ sung (Phụ lục A, A18).");

h3("Hình 2.0. Use case theo mục đích");
p(
  "Hình 2.0 chia use case đã đặc tả theo hai mục đích. Mỗi nhóm có một nút mục đích nối tới các use case thuộc nhóm. UC-07 (hồ sơ lô công khai), UC-08 (xem lô và truy xuất) và UC-22 (bot Telegram) chưa thuộc hai mục đích đã biết nên không nằm trong hình; chờ xác nhận mục đích thứ ba. Hình này bổ sung cho Hình 2.1 đến Hình 2.5, không thay thế các hình đó."
);
p(
  "Khối sơ đồ Mermaid gốc của Hình 2.0 không được chuyển thành ảnh ở đây (ảnh fig_05_01.png đã cũ, còn use case UC-19 \"Điều tra bằng Bits AI Ca 2\" đã bị xóa khỏi tài liệu hiện tại). Nội dung sơ đồ Mermaid hiện tại được liệt kê trung thực bằng chữ dưới đây.",
  { italics: true }
);
body.push(para("Tác nhân xuất hiện trong sơ đồ: Người vận hành; Quản trị viên; PLC ảo; Datadog US1; Probe ngoài app; Guard và verifier trên host.", { bold: false }));
body.push(bulletPara("**Mục đích 1: Quản lý nông trại và thiết bị** (nút \"Quan sát, quyết định, lịch, tưới\"): UC-01 Xem trạng thái farm; UC-02 Xem đề xuất AI; UC-05 Điều khiển bơm ảo; UC-06 Quản lý lịch tưới (đang bổ sung)."));
body.push(bulletPara("**Mục đích 2: Giám sát phần mềm và thiết bị:** UC-09 Mở Datadog từ trang Biểu đồ; UC-10 Xem danh sách sự cố; UC-11 Xem hồ sơ một sự cố; UC-12 Ca 1 phát hiện hiển thị sai; UC-13 Ca 1 từ chối restart; UC-14 Ca 2 phát hiện đứng số đo; UC-15 Ca 2 phục hồi có xác minh; UC-16 Ca 3 phát hiện dừng app; UC-17 Ca 3 khởi động có điều kiện; UC-18 Điều tra theo incident_id; UC-21 Kiểm tra /healthz; UC-24 Xem tác động và lô bị ảnh hưởng."));
body.push(bulletPara("Quan hệ chính trong sơ đồ: nút mục đích 1 nối tới UC-01, UC-02, UC-05, UC-06; UC-01 → UC-02 → UC-06 → UC-05; UC-12 → UC-13; UC-14 → UC-15. Người vận hành nối tới UC-01, UC-02, UC-05, UC-06; Quản trị viên nối tới UC-09, UC-10, UC-11; Datadog US1 nối tới UC-18; Probe ngoài app nối tới UC-21; Guard và verifier nối tới UC-15; UC-05, UC-14, UC-15 nối tới PLC ảo."));

// ---- Bảng Đọc nhanh ----
h1("Bảng Đọc nhanh");
table(
  kvTable([
    ["Bài toán", "Quản lý nhà màng dưa lưới: quyết định tưới và lịch thu hoạch chỉ có giá trị khi chuỗi số đo đáng tin [E-03]"],
    [
      "Mục đích",
      "(1) Quản lý nông trại và thiết bị; (2) giám sát phần mềm và thiết bị; (3) «ĐANG BỔ SUNG: mục đích thứ ba». Chi tiết tại mục Mục đích hệ thống",
    ],
    [
      "Tác nhân",
      "Người vận hành, quản trị viên, khách xem mã QR; hệ thống gồm bộ phát dữ liệu demo, cầu nối Wokwi, PLC ảo, Datadog, LLM Observability, probe, guard và verifier (mục 1)",
    ],
    ["Use case", "24 đã đặc tả (mục 3); 6 dự kiến chưa hiện thực hoặc có chủ ý không hiện thực (mục 3.3)"],
    [
      "Trang và quyền",
      "Trang chủ, `/plc`, `/schedule`, `/chart`, `/mongodb-lab` yêu cầu đăng nhập; `/incident` và `/incident/{id}` chỉ cho admin hoặc quyền `manage_users`; `/lot/{token}` công khai [E-17]",
    ],
    ["Ba ca", "Ca 1 báo offline sai; Ca 2 đứng số đo; Ca 3 dừng `smiot.service` [E-16]"],
    ["Ý nghĩa trạng thái", "\"Đã kiểm chứng mã\" nghĩa là đã đọc mã và đối chiếu `file:dòng`. Không có nghĩa là đã chạy trên hệ thống sống"],
    [
      "Hiện trạng 06/11",
      "Dữ liệu tổng hợp; PLC ảo; chỉ Greenhouse A có dữ liệu; `/chart` chỉ điều hướng; chia vai Datadog điều tra, MongoDB đo tác động, ứng dụng điều hướng [E-17, E-52]",
    ],
    ["Giới hạn", "Mục 6"],
    ["Thứ tự đọc", "01 → 05 → 04 → 02 → 03 (tài liệu này là 05)"],
    ["Địa chỉ truy cập", "«URL demo — ĐANG BỔ SUNG» (tài liệu không ghi hostname)"],
  ])
);

// ---- Mục lục (văn bản gốc, không phải TOC tự động) ----
h1("Mục lục (tóm tắt)");
p("Tóm tắt; Mục đích hệ thống; Bảng Đọc nhanh; Mục lục.");
p(
  "Mục đích hệ thống (Hình 2.0). 1 Tác nhân. 2 Sơ đồ use case (Hình 2.1 đến Hình 2.5). 3 Đặc tả use case (UC-01 đến UC-24; 3.3 use case chưa hiện thực). 4 Ma trận tác nhân × use case. 5 Ma trận truy vết và bảng tuyên bố. 6 Hạn chế và phạm vi. 7 Kết luận. Phụ lục A: Mục cần bổ sung."
);

// ---- 1 Tác nhân ----
h1("1 Tác nhân");
p(
  "Bảng 1.1 liệt kê tác nhân có trong mã nguồn. Repo không có tác nhân là thiết bị cảm biến vật lý hay bơm vật lý; mọi số đo và trạng thái bơm đều đến từ luồng tổng hợp hoặc PLC ảo [E-02, E-13]."
);
body.push(tableCaption("Bảng 1.1. Tác nhân của hệ thống"));
table(
  dataTable(
    ["Mã", "Tác nhân", "Loại", "Vai trò trong mã", "Nguồn"],
    [0.07, 0.16, 0.1, 0.42, 0.25],
    [
      ["TN-01", "Người vận hành nông trại", "Chính", "Vai trò `operator`: xem dashboard, điều khiển inverter, bật tắt bảy bơm ảo. Vai trò `viewer` chỉ xem", "`service/auth.py:15-31`; `pages/plc.py:63-67`"],
      ["TN-02", "Quản trị viên", "Chính", "Vai trò `admin` hoặc quyền `manage_users`: xem `/incident`, quản lý người dùng và quyền, sao lưu", "`pages/incident.py:132-145`; `pages/permission.py:79-80`"],
      ["TN-03", "Khách xem mã QR", "Phụ", "Không đăng nhập; đọc hồ sơ lô qua token", "`pages/public_lot.py:8-18`"],
      ["TN-04", "Người nhận và hỏi đáp qua Telegram", "Phụ", "Nhận thông báo `farm/notify`, hỏi trợ lý AI qua bot", "`service/telegram_bot.py:98, 186`; `service/mqtt.py:51-53`"],
      ["TN-05", "Bộ phát dữ liệu demo", "Hệ thống", "Phát `farm/sensor`, `farm/status`, `farm/data` khi bật `SMIOT_DEMO_MODE`; dữ liệu có nhãn tổng hợp", "`service/demo_mode.py:44-45, 425-471`"],
      ["TN-06", "Cầu nối Wokwi", "Hệ thống", "Chuyển mẫu từ kênh Wokwi sang MQTT nội bộ; gửi HOLD tới đầu ra ảo khi workflow thành công", "`scripts/wokwi_datadog_bridge.py:30-31, 460-506`"],
      ["TN-07", "PLC ảo", "Hệ thống", "Nhận lệnh bơm và chế độ an toàn; trả trạng thái và ACK; không điều khiển thiết bị vật lý", "`service/demo_mode.py:213-233, 288-354`; `pages/plc.py:50-72`"],
      ["TN-08", "Datadog (monitor, Workflow, Private Action Runner, Logs, APM, dashboard)", "Hệ thống ngoài", "Phát hiện, điều tra và thực hiện bước workflow đã định nghĩa trước", "`outputs/evidence/monitor_*.json` [E-50]; `scripts/aws/smiot-recover-guarded.sh:2`"],
      ["TN-09", "LLM Observability", "Dịch vụ Datadog", "Nhận span của trợ lý AI; nội dung vào và ra bị che", "`service/observability.py:50-61` [E-19]"],
      ["TN-10", "Probe ngoài app", "Hệ thống", "Đo HTTP và tuổi mẫu từ bên ngoài tiến trình app; mở `service_down`", "`scripts/smiot_external_probe.py:50-55, 298-344` [E-23]"],
      ["TN-11", "Guard và verifier trên host", "Hệ thống", "Guard khởi động có điều kiện `smiot.service`; verifier kiểm mẫu trước khi gỡ HOLD", "`scripts/aws/smiot-recover-guarded.sh`; `scripts/verify_and_clear_demo_safe_mode.py` [E-22, E-24]"],
      ["TN-12", "Gemini", "Dịch vụ mô hình bên ngoài", "Sinh đề xuất và trả lời trợ lý AI", "`service/ai_service.py:218-267, 369` [E-19]"],
      ["TN-13", "MongoDB Community tự quản", "Hệ thống", "Lưu telemetry Time Series, sự cố, quyết định, sổ lệnh, người dùng", "`service/auth.py:71-98` [E-12]"],
    ],
    true
  )
);

// ---- 2 Sơ đồ use case ----
h1("2 Sơ đồ use case");
p(
  "Các sơ đồ dùng Mermaid `flowchart LR`. Tác nhân là nút có nhãn; use case là nút bo tròn; ranh giới hệ thống là `subgraph`. Mã UC trong nhãn trỏ tới mục 3."
);

h3("Hình 2.1. Sơ đồ use case tổng thể");
body.push(imageParagraph("fig_05_02.png", 600, 816));
p(
  "Hình 2.1 có 4 tác nhân người, 7 tác nhân hệ thống hoặc dịch vụ và 17 use case. Người vận hành và quản trị viên đi qua đăng nhập trước khi vào các trang được bảo vệ. Ca 1 đến Ca 3 đi qua Datadog, probe, guard và verifier, và chạm PLC ảo khi cần HOLD hoặc CLEAR."
);

h3("Hình 2.2. Giám sát và vận hành");
body.push(imageParagraph("fig_05_03.png", 600, 395));
p(
  "Hình 2.2 cho thấy người vận hành đọc trạng thái và đề xuất, điều khiển bơm ảo và quản lý lịch. Dữ liệu cảm biến đi từ bộ phát tổng hợp tới trang chủ. Probe gọi kiểm tra sức khỏe. Lệnh bơm ảo đi tới PLC ảo."
);

h3("Hình 2.3. Quản trị và phân quyền");
body.push(imageParagraph("fig_05_04.png", 600, 461));
p(
  "Hình 2.3 cho thấy đăng nhập ghi vai trò và quyền vào phiên. Các trang `/permission`, `/incident` và `/incident/{id}` kiểm tra vai trò admin hoặc `manage_users`. Quyền bơm và lịch được kiểm bằng `check_permission` theo người dùng trong MongoDB. Hai cơ chế đọc quyền này có thể lệch nhau cho đến khi đăng nhập lại (mục 6)."
);

h3("Hình 2.4. Phát hiện, điều tra và xử lý Ca 1, Ca 2, Ca 3");
body.push(imageParagraph("fig_05_05.png", 600, 548));
p(
  "Hình 2.4 là chuỗi đầy đủ. Ca 1 do Datadog phát hiện và workflow chỉ ghi nhận từ chối. Ca 2 do watchdog mở sự cố, HOLD đi tới PLC ảo và CLEAR chỉ sau verifier. Ca 3 do probe mở sự cố và guard có thể khởi động đúng một unit. MongoDB được đọc để đo tác động và để xác minh phục hồi."
);

h3("Hình 2.5. Điều hướng Datadog và trợ lý AI");
p(
  "Khối sơ đồ Mermaid gốc của Hình 2.5 không được chuyển thành ảnh ở đây (ảnh fig_05_06.png đã cũ, còn tách riêng UC-19 \"Điều tra bằng Bits AI\" và UC-20 \"Quan sát trợ lý AI\"; nay chỉ còn một use case UC-19 \"Quan sát trợ lý AI\", đã đổi số từ UC-20). Nội dung sơ đồ Mermaid hiện tại được liệt kê trung thực bằng chữ dưới đây.",
  { italics: true }
);
body.push(para("Tác nhân xuất hiện trong sơ đồ: Người vận hành; Quản trị viên; Người dùng Telegram; Datadog US1; LLM Observability; Gemini."));
body.push(bulletPara("Use case trong ranh giới \"Điều hướng và trợ lý AI\": UC-09 Mở Datadog từ trang Biểu đồ; UC-02 Xem đề xuất AI trên trang chủ; UC-19 Quan sát trợ lý AI; UC-22 Hỏi đáp qua bot Telegram; cùng thành phần \"Dịch vụ ai_service\"."));
body.push(bulletPara("Quan hệ chính: Người vận hành và Quản trị viên → UC-09 → Datadog US1; Người vận hành → UC-02 → Dịch vụ ai_service; Người dùng Telegram → UC-22 → Dịch vụ ai_service; Dịch vụ ai_service → Gemini và → LLM Observability; UC-19 → LLM Observability."));
p(
  "Hình 2.5 cho thấy trang Biểu đồ chỉ là điều hướng sang Datadog. Trợ lý AI đi qua `ai_service`, gọi Gemini, và span được gửi tới LLM Observability với nội dung đã che."
);

// ---- 3 Đặc tả use case ----
h1("3 Đặc tả use case");
h2("3.1 Quy ước");
p(
  "Mỗi use case có một bảng. Cột \"Nguồn mã\" dùng đường dẫn tương đối từ gốc repo. Trạng thái nhận một trong ba giá trị: **đã kiểm chứng mã** (đã đọc mã và đối chiếu dòng), **đang bổ sung** (đang bổ sung bằng chứng trong repo hoặc đọc thêm mã), **chờ thông tin** (cần thông tin hoặc hành động của người dùng, ghi trong Phụ lục A). Ngưỡng phát hiện và xác minh theo mã hiện tại; số mẫu quan sát của từng lần diễn tập ghi theo hồ sơ của lần đó [E-22, E-40, E-41]."
);

h2("3.2 Danh sách use case");

const useCases = [
  {
    title: "UC-01. Xem trạng thái farm và node trên trang chủ",
    rows: [
      ["ID", "UC-01"],
      ["Tên", "Xem trạng thái farm và node trên trang chủ"],
      ["Tác nhân chính", "Người vận hành; quản trị viên"],
      ["Tiền điều kiện", "Đã đăng nhập"],
      ["Kích hoạt", "Mở `/`"],
      ["Luồng chính", "(1) `check_login` kiểm tra phiên; nếu chưa có, chuyển sang `/login`.<br>(2) Trang đồng bộ trạng thái node 1 và node 2 của farm đang chọn từ bản ghi telemetry mới nhất.<br>(3) Trạng thái hiển thị là ONLINE, STALE, OFFLINE hoặc UNKNOWN theo tuổi mẫu."],
      ["Luồng thay thế, ngoại lệ", "Chưa có mẫu: trạng thái UNKNOWN, không suy diễn. Lỗi MongoDB: giữ trạng thái cũ và ghi debug log."],
      ["Hậu điều kiện", "Trang hiển thị trạng thái mới nhất có sẵn. Khi hiển thị lệch MongoDB, metric `smiot.telemetry.status_mismatch` được phát cho farm đang chọn."],
      ["Nguồn mã", "`pages/home.py:1344-1346`; `service/telemetry_health.py:26, 356-382, 389-446`; `service/telemetry_health.py:380-381`"],
      ["Trạng thái", "đã kiểm chứng mã"],
    ],
  },
  {
    title: "UC-02. Xem đề xuất lượng nước từ AI",
    rows: [
      ["ID", "UC-02"],
      ["Tên", "Xem đề xuất lượng nước từ AI"],
      ["Tác nhân chính", "Người vận hành"],
      ["Tiền điều kiện", "Đã đăng nhập; có đề xuất đã lưu cho farm nếu chưa có dự đoán mới"],
      ["Kích hoạt", "Mở trang chủ, hoặc nhận thông điệp `farm/ai`"],
      ["Luồng chính", "(1) Thông điệp `farm/ai` được phân loại bằng `classify_ai_payload`.<br>(2) Nếu trạng thái không phải OK hoặc thiếu lượng, van hiển thị đóng (HOLD).<br>(3) Nếu chưa có dự đoán mới, card lấy đề xuất đã lưu gần nhất và gắn nhãn \"dự đoán cũ\".<br>(4) Đề xuất có lượng được lưu dạng snapshot."],
      ["Luồng thay thế, ngoại lệ", "Lỗi nhà cung cấp: \"AI lỗi - HOLD, không tưới\". Thiếu dữ liệu: \"Chưa có dữ liệu - HOLD\". Giá trị 0 ml là khuyến nghị không tưới, khác với thiếu dữ liệu."],
      ["Hậu điều kiện", "Người xem biết đề xuất là mới hay cũ, và khi nào hệ thống giữ van đóng."],
      ["Nguồn mã", "`pages/home.py:1074-1118`; `service/mqtt.py:485-516`; `service/auth.py:348, 368`; `service/ai_service.py:341`"],
      ["Trạng thái", "đang bổ sung. Repo không có publisher `farm/ai`; xem N4 và Phụ lục A"],
    ],
  },
  {
    title: "UC-03. Đăng nhập",
    rows: [
      ["ID", "UC-03"],
      ["Tên", "Đăng nhập"],
      ["Tác nhân chính", "Mọi người dùng có tài khoản đang hoạt động"],
      ["Tiền điều kiện", "Tài khoản tồn tại và đang hoạt động; mật khẩu lưu dạng băm"],
      ["Kích hoạt", "Mở `/login`, hoặc bị chuyển từ trang được bảo vệ"],
      ["Luồng chính", "(1) Nhập tên đăng nhập và mật khẩu.<br>(2) `verify_user` tìm tài khoản đang hoạt động và so khớp băm; nếu băm cũ, nâng cấp băm.<br>(3) Đọc quyền bằng `get_user_permissions`.<br>(4) Lưu `user_id`, `username`, `role`, `permissions` vào `app.storage.user`.<br>(5) Chuyển về `/`."],
      ["Luồng thay thế, ngoại lệ", "Sai thông tin: thông báo chung, không cho biết tài khoản có tồn tại. Chưa có người dùng nào: `init_db` yêu cầu biến môi trường `SMIOT_BOOTSTRAP_ADMIN_PASSWORD`, thiếu thì dừng khởi tạo."],
      ["Hậu điều kiện", "Phiên có vai trò và quyền; các trang gọi `check_login` cho phép truy cập."],
      ["Nguồn mã", "`pages/login.py:196-200, 202-205, 235-260`; `service/auth.py:109-113, 127-139, 177-185`"],
      ["Trạng thái", "đã kiểm chứng mã. Repo không có tệp test cho đăng nhập trong `tests/`"],
    ],
  },
  {
    title: "UC-04. Quản lý người dùng và phân quyền",
    rows: [
      ["ID", "UC-04"],
      ["Tên", "Quản lý người dùng và phân quyền"],
      ["Tác nhân chính", "Quản trị viên"],
      ["Tiền điều kiện", "Đã đăng nhập với vai trò admin hoặc quyền `manage_users`"],
      ["Kích hoạt", "Mở `/permission`"],
      ["Luồng chính", "(1) Kiểm tra vai trò hoặc quyền; không đạt thì thông báo và chuyển về `/`.<br>(2) Liệt kê người dùng và danh mục quyền.<br>(3) Chọn quyền cho một người dùng và lưu."],
      ["Luồng thay thế, ngoại lệ", "Thanh bên chỉ hiện mục Incident và Permission khi có đủ điều kiện. Người không đủ quyền không thấy liên kết."],
      ["Hậu điều kiện", "Quyền được lưu trong MongoDB. Trang `/incident` và `/permission` đọc quyền từ phiên; quyền bơm và lịch đọc từ MongoDB, nên hiệu lực có thể khác nhau cho đến khi đăng nhập lại."],
      ["Nguồn mã", "`pages/permission.py:73-82, 284`; `pages/home.py:756-760`; `service/auth.py:15-31, 182-185`"],
      ["Trạng thái", "đã kiểm chứng mã. Hành vi lệch quyền đang bổ sung kiểm chứng trên hệ thống sống (Phụ lục A, A14)"],
    ],
  },
  {
    title: "UC-05. Điều khiển bơm ảo qua PLC ảo",
    rows: [
      ["ID", "UC-05"],
      ["Tên", "Điều khiển bơm ảo qua PLC ảo"],
      ["Tác nhân chính", "Người vận hành có quyền `pump_N_control`"],
      ["Tiền điều kiện", "Đã đăng nhập; bộ phát demo đang chạy để PLC ảo phản hồi"],
      ["Kích hoạt", "Mở `/plc` và thay đổi trạng thái một bơm"],
      ["Luồng chính", "(1) Trang đọc trạng thái bơm từ PLC ảo.<br>(2) Khi thay đổi bơm N, kiểm `check_permission` với `pump_N_control`.<br>(3) Trang gửi lệnh tới `farm/control`; hàng bơm hiển thị trạng thái chờ.<br>(4) PLC ảo áp lệnh và phát trạng thái mới."],
      ["Luồng thay thế, ngoại lệ", "Không có quyền: thông báo \"không có quyền điều khiển Bơm N\", lệnh không gửi. Trạng thái yêu cầu và trạng thái thực lệch nhau: hàng hiển thị trạng thái lệch."],
      ["Hậu điều kiện", "Trạng thái bơm ảo thay đổi. Không có tác động vật lý."],
      ["Nguồn mã", "`pages/plc.py:7-9, 50-72`; `service/demo_mode.py:213-233, 368, 453`; `service/demo_mode.py:288-354`"],
      ["Trạng thái", "đã kiểm chứng mã. Không có tệp test cho trang `/plc`"],
    ],
  },
  {
    title: "UC-06. Quản lý lịch tưới",
    rows: [
      ["ID", "UC-06"],
      ["Tên", "Quản lý lịch tưới"],
      ["Tác nhân chính", "Quản trị viên; người có quyền `manage_schedule`"],
      ["Tiền điều kiện", "Đã đăng nhập"],
      ["Kích hoạt", "Mở `/schedule`"],
      ["Luồng chính", "(1) Trang xác định farm hiện tại và tuần đang xem.<br>(2) Người có `manage_schedule` thêm hoặc sửa lịch.<br>(3) Người có `export_schedule_logs` xuất nhật ký."],
      ["Luồng thay thế, ngoại lệ", "Không có quyền: chỉ xem. Lịch ở trạng thái running khi khởi động lại được đánh dấu failed."],
      ["Hậu điều kiện", "Lịch lưu trong collection `schedules`, nhật ký trong `schedule_logs`."],
      ["Nguồn mã", "`pages/schedule.py:147-150, 214, 291-297`; `service/auth.py:106-107`; `service/scheduler.py:16`"],
      ["Trạng thái", "đang bổ sung. Đã đọc điểm vào và kiểm quyền; luồng ghi và bộ lập lịch nền đang được đọc thêm"],
    ],
  },
  {
    title: "UC-07. Xem hồ sơ lô công khai qua mã QR",
    rows: [
      ["ID", "UC-07"],
      ["Tên", "Xem hồ sơ lô công khai qua mã QR"],
      ["Tác nhân chính", "Khách xem mã QR"],
      ["Tiền điều kiện", "Có token lô"],
      ["Kích hoạt", "Quét mã mở `/lot/{token}`"],
      ["Luồng chính", "(1) Tra cứu lô theo token bằng `customer_lot_by_token`.<br>(2) Hiển thị thông tin lô và các chặng sản xuất, chỉ đọc."],
      ["Luồng thay thế, ngoại lệ", "Token không tồn tại hoặc lỗi truy vấn: hiển thị \"Không tìm thấy hồ sơ lô\", không lộ chi tiết lỗi."],
      ["Hậu điều kiện", "Không ghi dữ liệu."],
      ["Nguồn mã", "`pages/public_lot.py:8-18`; `service/traceability.py:73`"],
      ["Trạng thái", "đang bổ sung. Không có tệp test; nội dung lô là dữ liệu tổng hợp"],
    ],
  },
  {
    title: "UC-08. Xem lô và truy xuất mùa vụ",
    rows: [
      ["ID", "UC-08"],
      ["Tên", "Xem lô và truy xuất mùa vụ"],
      ["Tác nhân chính", "Người vận hành"],
      ["Tiền điều kiện", "Đã đăng nhập"],
      ["Kích hoạt", "Mở `/mongodb-lab`, hoặc `/traceability` (chuyển hướng)"],
      ["Luồng chính", "(1) `/traceability` chỉ chuyển sang `/mongodb-lab`.<br>(2) `/mongodb-lab` kiểm đăng nhập rồi đọc danh sách lô và câu chuyện mùa vụ."],
      ["Luồng thay thế, ngoại lệ", "Chưa đăng nhập: chuyển sang `/login`."],
      ["Hậu điều kiện", "Chỉ đọc."],
      ["Nguồn mã", "`pages/traceability.py:6-8`; `pages/mongodb_lab.py:7, 17-19`"],
      ["Trạng thái", "đã kiểm chứng mã (điều hướng). Nội dung lô là dữ liệu tổng hợp"],
    ],
  },
  {
    title: "UC-09. Mở dashboard, monitor và quan sát AI từ trang Biểu đồ",
    rows: [
      ["ID", "UC-09"],
      ["Tên", "Mở dashboard, monitor và quan sát AI từ trang Biểu đồ"],
      ["Tác nhân chính", "Người vận hành; quản trị viên"],
      ["Tiền điều kiện", "Đã đăng nhập; có tài khoản Datadog để xem nội dung (ngoài ứng dụng)"],
      ["Kích hoạt", "Mở `/chart`, hoặc `/history` (chuyển sang `/chart`)"],
      ["Luồng chính", "(1) Kiểm đăng nhập.<br>(2) Hiển thị ba thẻ: Dashboard vận hành, Quan sát AI, Tất cả monitor.<br>(3) Bấm thẻ mở liên kết Datadog ở tab mới."],
      ["Luồng thay thế, ngoại lệ", "Không có quyền trên Datadog: Datadog tự từ chối; ứng dụng không kiểm tra."],
      ["Hậu điều kiện", "Người dùng chuyển sang Datadog. Ứng dụng không vẽ biểu đồ nào."],
      ["Nguồn mã", "`pages/chart.py:7-8, 28-35, 38-40, 43-67`"],
      ["Trạng thái", "đã kiểm chứng mã. Số widget của dashboard `nkc-685-vw8` cần xác nhận: «ĐANG BỔ SUNG: số widget 06/11» (E-03 ghi 8 widget ngày 04/11)"],
    ],
  },
  {
    title: "UC-10. Xem danh sách sự cố",
    rows: [
      ["ID", "UC-10"],
      ["Tên", "Xem danh sách sự cố"],
      ["Tác nhân chính", "Quản trị viên"],
      ["Tiền điều kiện", "Vai trò admin hoặc quyền `manage_users`; tài khoản giám khảo: «ĐANG BỔ SUNG: tài khoản giám khảo» (A2)"],
      ["Kích hoạt", "Mở `/incident`"],
      ["Luồng chính", "(1) `_guard` kiểm đăng nhập và quyền.<br>(2) Đọc tối đa 50 sự cố mới nhất từ `operational_incidents`.<br>(3) Hiển thị ba thẻ Ca 1 đến Ca 3; bấm thẻ để lọc.<br>(4) Bấm một dòng để mở `/incident/{id}`.<br>(5) Trang tự làm mới sau 10 s."],
      ["Luồng thay thế, ngoại lệ", "Không đọc được MongoDB: hiển thị lỗi trên trang. Chưa có sự cố: hiển thị gợi ý chạy một ca diễn tập."],
      ["Hậu điều kiện", "Chỉ đọc."],
      ["Nguồn mã", "`pages/incident.py:27, 132-145, 725-781`; `service/incident_blackbox.py:542-548`"],
      ["Trạng thái", "đã kiểm chứng mã. Ảnh minh chứng: «ĐANG BỔ SUNG: ảnh /incident» (E-83)"],
    ],
  },
  {
    title: "UC-11. Xem hồ sơ một sự cố và sáu câu hỏi",
    rows: [
      ["ID", "UC-11"],
      ["Tên", "Xem hồ sơ một sự cố và sáu câu hỏi"],
      ["Tác nhân chính", "Quản trị viên"],
      ["Tiền điều kiện", "Như UC-10"],
      ["Kích hoạt", "Mở `/incident/{incident_id}`"],
      ["Luồng chính", "(1) `_guard` kiểm quyền.<br>(2) `build_incident_timeline` đọc sự cố, bằng chứng, quyết định, sổ lệnh và telemetry trong cửa sổ quanh sự cố.<br>(3) `build_six_questions` dựng sáu câu: phát hiện, nguồn phát hiện, nhật ký và trace, lô bị ảnh hưởng, hành động và execution, phục hồi.<br>(4) `metric_links` dựng khối \"Metric của sự cố\": tên metric theo loại sự cố và liên kết mở Metrics Explorer hoặc dashboard Datadog theo khung giờ sự cố, từ 15 phút trước lúc mở đến 15 phút sau lúc phục hồi.<br>(5) Liên kết Datadog chỉ hiện khi có giá trị."],
      ["Luồng thay thế, ngoại lệ", "Mã không tồn tại: \"Không tìm thấy sự cố\". Thiếu dữ liệu: hiển thị \"—\" hoặc \"chưa xác định\", không điền số giả."],
      ["Hậu điều kiện", "Chỉ đọc. Trang tự cập nhật sau 20 s khi có thay đổi."],
      ["Nguồn mã", "`pages/incident.py:350-364, 470-519, 800-833, 865-880, 1004-1018`; `service/incident_blackbox.py:580-585`"],
      ["Trạng thái", "đã kiểm chứng mã"],
    ],
  },
  {
    title: "UC-12. Ca 1: phát hiện hiển thị sai (`false_offline`)",
    rows: [
      ["ID", "UC-12"],
      ["Tên", "Ca 1: phát hiện hiển thị sai"],
      ["Tác nhân chính", "Watchdog trong app; Datadog monitor 341409441"],
      ["Tiền điều kiện", "Greenhouse A node 1 vẫn có mẫu vào MongoDB; giao diện báo OFFLINE"],
      ["Kích hoạt", "Trạng thái hiển thị lệch trạng thái tính từ MongoDB; metric `smiot.telemetry.status_mismatch` bằng 1"],
      ["Luồng chính", "(1) Watchdog tính trạng thái từ mẫu mới nhất của farm đang chọn.<br>(2) So với trạng thái hiển thị (`reconcile_display_status`).<br>(3) Phát metric; mở sự cố `false_offline` khi chuyển từ không lệch sang lệch.<br>(4) Monitor 341409441 (`max(last_5m)` > 0 theo farm và node) chuyển Alert; monitor đối chứng 339977703 cho thấy mẫu vẫn tươi."],
      ["Luồng thay thế, ngoại lệ", "Farm không được chọn không được đối chiếu hiển thị, chỉ phát tuổi mẫu. Lỗi MongoDB: ghi log, không mở sự cố."],
      ["Hậu điều kiện", "Sự cố có monitor và workflow đã gán. Sự cố đóng khi MongoDB có bằng chứng tươi và trạng thái ONLINE."],
      ["Nguồn mã", "`service/telemetry_health.py:30-43, 300-345, 389-446`; `service/mqtt.py:443-469`; `outputs/evidence/monitor_341409441.json` [E-50]"],
      ["Trạng thái", "đã kiểm chứng mã và Datadog. Lượt `a782b12c…` (04:50:21Z) ghi nhánh REFUSED_RESTART (E-81)"],
    ],
  },
  {
    title: "UC-13. Ca 1: từ chối restart khi báo offline sai",
    rows: [
      ["ID", "UC-13"],
      ["Tên", "Ca 1: từ chối restart"],
      ["Tác nhân chính", "Datadog Workflow e2835af0"],
      ["Tiền điều kiện", "Monitor 341409441 Alert; workflow đã publish"],
      ["Kích hoạt", "Monitor Alert"],
      ["Luồng chính", "(1) Workflow đọc tuổi mẫu từ hai metric Datadog và rẽ nhánh theo ngưỡng (mặc định 90 s).<br>(2) Ghi `REFUSED_RESTART` khi mẫu còn tươi, hoặc `ESCALATE_HUMAN` khi không xác nhận được; không gọi restart; không tác động EC2 hoặc thiết bị; trigger monitor giới hạn 1 lượt mỗi 300 s.<br>(3) Người điều tra đối chiếu log và trace theo incident_id với monitor đối chứng."],
      ["Luồng thay thế, ngoại lệ", "Vượt giới hạn tần suất: lượt chạy không thực hiện bước nào. Playbook ghi nhận workflow Ca 2 từng bị \"Rate limit exceeded\" bốn lần, nên cần kiểm tần suất trước mỗi diễn tập [E-44]."],
      ["Hậu điều kiện", "Không có thay đổi trên host. Sự cố vẫn mở đến khi có bằng chứng tươi."],
      ["Nguồn mã", "`outputs/evidence/workflow_e2835af0-63fc-48e0-9562-2a1ee4a351d3.json` (khối `rateLimit`: 1 lượt mỗi 300 s); `docs/THREE_CASES_PLAYBOOK.md:77`"],
      ["Trạng thái", "đã kiểm chứng mã và execution (lượt `a782b12c…`, E-81)"],
    ],
  },
  {
    title: "UC-14. Ca 2: phát hiện đứng số đo, ghi nhận và HOLD",
    rows: [
      ["ID", "UC-14"],
      ["Tên", "Ca 2: phát hiện đứng số đo và HOLD"],
      ["Tác nhân chính", "Watchdog; Datadog monitor 339977691 và workflow 18d1b008; cầu nối Wokwi; PLC ảo"],
      ["Tiền điều kiện", "Greenhouse A node 2 nhận mẫu liên tục"],
      ["Kích hoạt", "10 mẫu mới nhất của node 2 cùng có độ ẩm đất chênh lệch không quá 0,01 trong cửa sổ 600 s; monitor 339977691 Alert"],
      ["Luồng chính", "(1) Watchdog đọc 10 mẫu node 2 đã lưu; nếu đứng số đo, đánh dấu flatline.<br>(2) Mở sự cố `soil_humidity_flatline` cho greenhouse_a node 2; ngoài phạm vi này thì bỏ qua.<br>(3) Mẫu có giá trị 2,4 được gắn incident_id và ghi bản ghi quyết định BLOCKED.<br>(4) Khi workflow thành công trong lúc monitor Alert, cầu nối gửi HOLD tới PLC ảo và ghi ACK vào sổ hành động; nếu HOLD đã giữ, ghi nhận trùng lặp đã được chặn."],
      ["Luồng thay thế, ngoại lệ", "Workflow failed hoặc canceled: không gửi lệnh (log của cầu nối). Lỗi MongoDB: watchdog không dừng."],
      ["Hậu điều kiện", "Sự cố ở trạng thái open, sau đó holding khi HOLD được ack. Dữ liệu gắn nhãn tổng hợp. Ngưỡng theo mã hiện tại (10 mẫu); hồ sơ 03/11 ghi số mẫu quan sát của lần đó [E-40, E-41]."],
      ["Nguồn mã", "`service/telemetry_health.py:35-37, 228-250, 474-511`; `service/mqtt.py:473-480`; `service/incident_lifecycle.py:47-95, 102-116, 117-170, 227-237`; `scripts/wokwi_datadog_bridge.py:460-506`"],
      ["Trạng thái", "đã kiểm chứng mã. Hồ sơ 03/11 đầy đủ [E-40, E-41]; diễn tập 06/11 một phần [E-56]"],
    ],
  },
  {
    title: "UC-15. Ca 2: phục hồi có xác minh và gỡ HOLD",
    rows: [
      ["ID", "UC-15"],
      ["Tên", "Ca 2: phục hồi có xác minh và CLEAR"],
      ["Tác nhân chính", "Watchdog (gọi verifier); Datadog Workflow (gọi endpoint khi phục hồi); verifier; PLC ảo (ACK)"],
      ["Tiền điều kiện", "Sự cố `soil_humidity_flatline` đang mở; monitor 339977691 OK khi đọc qua API"],
      ["Kích hoạt", "Mẫu node 2 dao động trở lại: watchdog gọi verifier; hoặc workflow gọi `POST /api/internal/safe-mode/recovery-clear` kèm bearer token"],
      ["Luồng chính", "(1) Verifier đọc monitor; yêu cầu trạng thái OK và có thời điểm trigger.<br>(2) Tìm HOLD đã ack của workflow sau thời điểm trigger hoặc HOLD gần nhất chưa CLEAR.<br>(3) Lấy sự cố canonical; sự cố `UNMATCHED-` bị loại.<br>(4) Nếu đã có CLEAR verified: trả thành công (idempotent).<br>(5) Đếm mẫu node 2 khác 2,4 trong cửa sổ sau HOLD: ít nhất 10 mẫu; mẫu mới nhất không quá 90 s; biên độ ít nhất 0,5.<br>(6) Gửi CLEAR tới PLC ảo, chờ ACK trong 8 s.<br>(7) Ghi `action_ledger` trạng thái verified; sự cố chuyển `recovered`."],
      ["Luồng thay thế, ngoại lệ", "Monitor không OK: \"Refusing to clear HOLD\", trả HTTP 200 với `verification_not_passed`, HOLD giữ nguyên. Lỗi hạ tầng: HTTP 503. Đang chạy: HTTP 409. Chưa cấu hình token: HTTP 503. Token sai: HTTP 401. Quá 55 s: HTTP 504. Mẫu chưa đủ: không CLEAR."],
      ["Hậu điều kiện", "CLEAR chỉ gửi khi verifier đạt. Sự cố `recovered` kèm `recovery_verification`. Watchdog đóng sự cố qua `close_flatline_incident` khi verifier đạt."],
      ["Nguồn mã", "`main.py:194-241`; `scripts/verify_and_clear_demo_safe_mode.py:29-44, 64-127, 129-159, 166, 182-221`; `service/telemetry_health.py:160-225`; `service/incident_lifecycle.py:227-243, 342-356`"],
      ["Trạng thái", "đã kiểm chứng mã. Ca 2 ngày 06/11: trạng thái `recovered` đang bổ sung (E-86). Ngưỡng lớn hơn ngưỡng của watchdog (0,01) vì verifier yêu cầu biên độ 0,5"],
    ],
  },
  {
    title: "UC-16. Ca 3: phát hiện dừng tiến trình app",
    rows: [
      ["ID", "UC-16"],
      ["Tên", "Ca 3: phát hiện dừng tiến trình app"],
      ["Tác nhân chính", "Probe ngoài app; Datadog monitor 340356283; workflow b83453ff"],
      ["Tiền điều kiện", "Probe chạy định kỳ 30 s; MongoDB sống để đọc mẫu"],
      ["Kích hoạt", "Endpoint app không trả lời (`app_up` bằng 0) hai lần liên tiếp"],
      ["Luồng chính", "(1) Probe gửi HTTP tới app, đo tuổi mẫu mới nhất, gửi metric `smiot.external.*` qua DogStatsD.<br>(2) Sau hai lần `app_up` bằng 0 liên tiếp và MongoDB sống, mở sự cố `service_down` với monitor và workflow đã gán.<br>(3) Monitor 340356283 (`systemd.unit.active` của `smiot.service` ≤ 0) xác nhận.<br>(4) Khi app trả lời và có mẫu không quá 180 s, probe đóng sự cố."],
      ["Luồng thay thế, ngoại lệ", "Không có khóa API Datadog: probe vẫn đóng sự cố. Lỗi tra cứu workflow không làm hỏng probe."],
      ["Hậu điều kiện", "Sự cố `service_down` có thời điểm mở và đóng. Thời gian mất dữ liệu được tính từ khoảng thiếu mẫu trong hộp đen sự cố [E-16]."],
      ["Nguồn mã", "`scripts/smiot_external_probe.py:50-55, 62-81, 83-118, 202-290, 298-344`; `deploy/systemd/smiot-external-probe.service`"],
      ["Trạng thái", "đã kiểm chứng mã. Diễn tập 06/11 đo được một lần; execution ID `06cb1b46…` đã có [E-82, E-59]"],
    ],
  },
  {
    title: "UC-17. Ca 3: khởi động có điều kiện `smiot.service`",
    rows: [
      ["ID", "UC-17"],
      ["Tên", "Ca 3: khởi động có điều kiện `smiot.service`"],
      ["Tác nhân chính", "Datadog Workflow qua Private Action Runner (thiết kế); người vận hành khi diễn tập thủ công"],
      ["Tiền điều kiện", "Monitor 340356283 Alert; `smiot.service` inactive hoặc failed; `mongod` và `mosquitto` active; đĩa dưới 85 %; không có lượt khởi động trong 300 s"],
      ["Kích hoạt", "Workflow b83453ff chạy `scripts/aws/smiot-recover-guarded.sh`; hoặc người vận hành chạy `scripts/drill_ca3_service_down.ps1 -Confirm` trong diễn tập"],
      ["Luồng chính", "(1) Chờ 5 s để systemd restart policy có cơ hội chạy.<br>(2) Nếu endpoint đã khỏe, kết thúc (không làm gì).<br>(3) Nếu app active nhưng endpoint lỗi: từ chối, không restart.<br>(4) Kiểm đĩa, MongoDB và MQTT; đọc mốc thời gian mẫu Mongo.<br>(5) Khóa chống chạy chồng và kiểm cooldown 300 s.<br>(6) `systemctl start smiot.service`.<br>(7) Chờ tối đa 60 s để unit active và endpoint khỏe.<br>(8) Chờ tối đa 90 s để có mẫu Mongo mới không quá 180 s; ghi `start verified`, hoặc `start unverified`."],
      ["Luồng thay thế, ngoại lệ", "Các nhánh từ chối: đĩa, MongoDB hoặc MQTT không active, đọc Mongo lỗi. Các nhánh bỏ qua: khóa đang giữ, cooldown. Các nhánh lỗi: start lỗi, endpoint lỗi. Script không restart host, MongoDB, MQTT hay Datadog Agent. Bản ghi JSON của guard có các trường `action`, `result`, `reason`."],
      ["Hậu điều kiện", "Tối đa một unit được khởi động trong một lượt. Phục hồi chỉ được coi là đã xác minh khi có cả endpoint khỏe và mẫu Mongo mới."],
      ["Nguồn mã", "`scripts/aws/smiot-recover-guarded.sh:1-148`; `scripts/aws/smiot-recovery-mongo-readback.py:1-2`; `scripts/drill_ca3_service_down.ps1:6-8, 34-38, 56, 193`"],
      ["Trạng thái", "Ca 3 ngày 06/11: monitor Alert lúc 03:11:43Z, workflow `b83453ff…` tự kích hoạt lúc 03:12:43Z (execution `06cb1b46…`, chạy `recover-smiot-web` thành công) [E-82]. Đầu ra lệnh trên EC2 đang bổ sung do giới hạn quyền."],
    ],
  },
  {
    title: "UC-18. Điều tra theo `incident_id` trong Datadog",
    rows: [
      ["ID", "UC-18"],
      ["Tên", "Điều tra theo `incident_id` trong Datadog"],
      ["Tác nhân chính", "Quản trị viên; Datadog Logs và APM"],
      ["Tiền điều kiện", "Sự cố có `incident_id`; log có trường `@incident.id`; trace có thể có"],
      ["Kích hoạt", "Bấm liên kết log hoặc trace ở trang chi tiết"],
      ["Luồng chính", "(1) Trang chi tiết dựng liên kết truy vấn log theo sự cố và liên kết trace.<br>(2) Người điều tra xem sự kiện `smiot.guarded_recovery` hoặc `smiot_status_mismatch` trong Datadog."],
      ["Luồng thay thế, ngoại lệ", "Không có trace: không hiện nút trace. Thiếu giá trị: không tạo liên kết."],
      ["Hậu điều kiện", "Chỉ đọc; không thao tác trên Datadog từ ứng dụng."],
      ["Nguồn mã", "`pages/incident.py:209-253`; `service/incident_lifecycle.py:246-300`; `service/telemetry_health.py:333-350`"],
      ["Trạng thái", "đã kiểm chứng mã. Ảnh log và APM theo `incident_id`: «ĐANG BỔ SUNG: ảnh log và APM» (E-60 cần kiểm che trước khi dùng)"],
    ],
  },
  {
    title: "UC-19. Quan sát trợ lý AI bằng LLM Observability",
    rows: [
      ["ID", "UC-19"],
      ["Tên", "Quan sát trợ lý AI bằng LLM Observability"],
      ["Tác nhân chính", "Datadog LLM Observability; ứng dụng (sinh span)"],
      ["Tiền điều kiện", "`ddtrace` có sẵn; LLMObs bật với `ml_app` mặc định `smiot-smart-farm`; khóa Gemini hợp lệ"],
      ["Kích hoạt", "Gọi trợ lý AI (`ask_ai`) hoặc đề xuất AI"],
      ["Luồng chính", "(1) `initialize_tracing` bật LLMObs với `ml_app`.<br>(2) Mỗi lần gọi model tạo span với tên model và thao tác.<br>(3) Nội dung vào và ra được thay bằng tóm tắt đã che (`content_redacted`, số ký tự).<br>(4) Số token được gắn vào span."],
      ["Luồng thay thế, ngoại lệ", "Thiếu `ddtrace`: bỏ qua, không làm hỏng yêu cầu. Lỗi khi annotate: không làm hỏng yêu cầu. Khóa API không lộ trong log khi nhà cung cấp trả lỗi."],
      ["Hậu điều kiện", "Có span trong Datadog LLM Observability. Nội dung không hiển thị dạng thô."],
      ["Nguồn mã", "`service/observability.py:50-61, 72-76`; `service/ai_service.py:218-267, 369`; `tests/test_llmobs.py`"],
      ["Trạng thái", "đã kiểm chứng mã. Ảnh minh chứng: «ĐANG BỔ SUNG: ảnh LLM Observability» (E-84). Khai báo `docs/DECLARATIONS.md` ghi ngược, xem A15"],
    ],
  },
  {
    title: "UC-21. Kiểm tra sức khỏe ứng dụng qua `/healthz`",
    rows: [
      ["ID", "UC-21"],
      ["Tên", "Kiểm tra sức khỏe ứng dụng qua `/healthz`"],
      ["Tác nhân chính", "Probe, Datadog hoặc người vận hành (hệ thống giám sát)"],
      ["Tiền điều kiện", "Ứng dụng đang chạy"],
      ["Kích hoạt", "`GET /healthz`"],
      ["Luồng chính", "(1) Ping MongoDB và đọc mẫu mới nhất trong thời gian giới hạn.<br>(2) Kiểm kết nối MQTT.<br>(3) Trả JSON gồm `app`, `mongo`, `mqtt`, tuổi mẫu mới nhất; không trả lỗi chi tiết hay bí mật."],
      ["Luồng thay thế, ngoại lệ", "MongoDB lỗi: `mongo` ghi \"fail\", `app` vẫn \"ok\". Mẫu có thời điểm tương lai: kẹp về 0."],
      ["Hậu điều kiện", "Phản hồi không lưu cache (`Cache-Control: no-store`)."],
      ["Nguồn mã", "`main.py:142-191`; `tests/test_healthz.py`"],
      ["Trạng thái", "đã kiểm chứng mã"],
    ],
  },
  {
    title: "UC-22. Hỏi đáp AI qua bot Telegram",
    rows: [
      ["ID", "UC-22"],
      ["Tên", "Hỏi đáp AI qua bot Telegram"],
      ["Tác nhân chính", "Người dùng Telegram được cấu hình"],
      ["Tiền điều kiện", "Biến môi trường token và chat_id quản trị đã đặt; bot chạy như tiến trình riêng (không thuộc `main.py`)"],
      ["Kích hoạt", "Người dùng gửi tin nhắn tới bot"],
      ["Luồng chính", "(1) Bot nhận cập nhật qua API Telegram.<br>(2) Chuyển nội dung tới `ask_ai`.<br>(3) Gửi câu trả lời về chat.<br>(4) Bot cũng nhận `farm/notify` và gửi thông báo của hệ thống."],
      ["Luồng thay thế, ngoại lệ", "Thiếu token: bot dừng với thông báo. Lỗi nhà cung cấp AI được xử lý theo nguyên tắc HOLD (`tests/test_ai_failsafe.py`)."],
      ["Hậu điều kiện", "Bot không gửi lệnh điều khiển tới MQTT."],
      ["Nguồn mã", "`service/telegram_bot.py:26, 93-113, 141-187, 220`; `service/mqtt.py:51-53`"],
      ["Trạng thái", "đang bổ sung: «ĐANG BỔ SUNG: bot Telegram có đang chạy và có đưa vào hồ sơ không»"],
    ],
  },
  {
    title: "UC-23. Sao lưu và khôi phục dữ liệu MongoDB",
    rows: [
      ["ID", "UC-23"],
      ["Tên", "Sao lưu và khôi phục dữ liệu MongoDB"],
      ["Tác nhân chính", "Quản trị viên"],
      ["Tiền điều kiện", "Công cụ sao lưu có quyền đọc; đĩa đủ chỗ"],
      ["Kích hoạt", "Timer sao lưu, hoặc lệnh thủ công; diễn tập khôi phục"],
      ["Luồng chính", "(1) Sao lưu logic bằng `mongodump` và `mongoexport`, gồm collection Time Series.<br>(2) Diễn tập khôi phục vào nơi thử và đếm mẫu.<br>(3) So khớp số mẫu và số sự cố."],
      ["Luồng thay thế, ngoại lệ", "PITR và khôi phục EBS nằm ngoài phạm vi hiện tại."],
      ["Hậu điều kiện", "Có bản sao logic. Diễn tập 03/11 khớp 154.618/154.618 mẫu và 1/1 sự cố."],
      ["Nguồn mã", "`scripts/aws/mongodb_backup.sh`; `scripts/aws/mongodb_restore_drill.sh`; `scripts/aws/resume_ubuntu.sh:217-218` [E-28]; `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md` [E-42]"],
      ["Trạng thái", "đã kiểm chứng mã (tệp tồn tại) và tài liệu diễn tập"],
    ],
  },
  {
    title: "UC-24. Xem tác động trên dữ liệu và lô bị ảnh hưởng",
    rows: [
      ["ID", "UC-24"],
      ["Tên", "Xem tác động trên dữ liệu và lô bị ảnh hưởng"],
      ["Tác nhân chính", "Quản trị viên"],
      ["Tiền điều kiện", "Như UC-10"],
      ["Kích hoạt", "Mở chi tiết sự cố (`/incident/{id}`)"],
      ["Luồng chính", "(1) `build_impact_chart_data` tách số mẫu theo mức giá trị trong từng phút: bất thường, bình thường, không xác định.<br>(2) Đếm quyết định BLOCKED, số lô bị ảnh hưởng, số giờ và khoảng thiếu mẫu.<br>(3) Vẽ biểu đồ chất lượng dữ liệu; khoảng thiếu mẫu tính trong MongoDB bằng `$setWindowFields` và `$shift` [E-16]."],
      ["Luồng thay thế, ngoại lệ", "Giá trị không có: hiển thị \"không xác định\", không thay bằng 0."],
      ["Hậu điều kiện", "Chỉ đọc. Số liệu phục vụ trình bày sự cố; không thay thế đo lường có chuẩn."],
      ["Nguồn mã", "`pages/incident.py:520-632, 963-977`; `service/incident_blackbox.py:1-15, 170-300`"],
      ["Trạng thái", "đã kiểm chứng mã"],
    ],
  },
];

for (const uc of useCases) {
  pBold(uc.title);
  table(kvTable(uc.rows));
}

h2("3.3 Use case dự kiến hoặc có chủ ý không hiện thực");
table(
  dataTable(
    ["Mã", "Use case", "Căn cứ kiểm tra", "Trạng thái"],
    [0.08, 0.22, 0.48, 0.22],
    [
      ["N1", "Đăng ký tài khoản tự phục vụ", "Không có tuyến đăng ký trong `pages/`, không có mã đăng ký trong `*.py` (grep 06/11)", "ngoài phạm vi hiện tại"],
      ["N2", "Gửi thông báo sự cố qua email", "Không có mã gửi email trong `*.py` (grep 06/11). Thông báo hiện qua Telegram (`service/mqtt.py:51-53`)", "ngoài phạm vi hiện tại"],
      ["N3", "Tự đóng sự cố khi monitor Datadog trở về OK", "Mã ghi rõ không đóng tự động; đóng qua verifier hoặc probe (`service/telemetry_health.py:233-234`)", "không hiện thực có chủ ý"],
      ["N4", "Nhận đề xuất AI từ publisher trong repo", "Không có publisher `farm/ai`; chỉ có bộ tiêu thụ (`service/mqtt.py:485`)", "ngoài phạm vi repo hiện tại"],
      ["N5", "Xem mục tiêu mức dịch vụ (SLO)", "SLO nằm trên Datadog và chưa đủ 7 ngày dữ liệu", "ngoài phạm vi hiện tại"],
      ["N6", "Vận hành dữ liệu cho Greenhouse B đến D", "Watchdog quét bốn farm (`service/telemetry_health.py:25`), nhưng chỉ Greenhouse A có dữ liệu theo xác nhận 06/11", "chờ kết nối dữ liệu"],
    ]
  )
);

// ---- 4 Ma trận tác nhân × use case ----
h1("4 Ma trận tác nhân × use case");
p("Ký hiệu: ● tác nhân chính hoặc thành phần thực hiện; ○ tác nhân phụ hoặc thành phần tham gia; trống là không liên quan.");
body.push(tableCaption("Bảng 4.1. Ma trận tác nhân × use case"));
table(
  dataTable(
    ["UC", "Vận hành", "Quản trị", "Khách QR", "Datadog", "PLC ảo", "Nguồn dữ liệu", "Probe", "Guard, verifier", "Watchdog app", "Telegram"],
    [0.07, 0.093, 0.093, 0.093, 0.093, 0.093, 0.093, 0.093, 0.093, 0.093, 0.079],
    [
      ["UC-01", "●", "○", "", "", "", "○", "", "", "", ""],
      ["UC-02", "●", "", "", "", "", "", "", "", "", ""],
      ["UC-03", "●", "●", "", "", "", "", "", "", "", ""],
      ["UC-04", "", "●", "", "", "", "", "", "", "", ""],
      ["UC-05", "●", "○", "", "", "●", "", "", "", "", ""],
      ["UC-06", "○", "●", "", "", "", "", "", "", "", ""],
      ["UC-07", "", "", "●", "", "", "", "", "", "", ""],
      ["UC-08", "●", "○", "", "", "", "", "", "", "", ""],
      ["UC-09", "●", "●", "", "●", "", "", "", "", "", ""],
      ["UC-10", "", "●", "", "○", "", "", "", "", "", ""],
      ["UC-11", "", "●", "", "○", "", "", "", "", "", ""],
      ["UC-12", "", "", "", "●", "", "○", "", "", "●", ""],
      ["UC-13", "", "", "", "●", "", "", "", "", "", ""],
      ["UC-14", "", "", "", "○", "○", "●", "", "", "●", ""],
      ["UC-15", "", "", "", "○", "○", "", "", "●", "○", ""],
      ["UC-16", "", "", "", "○", "", "", "●", "", "", ""],
      ["UC-17", "○", "", "", "●", "", "", "○", "●", "", ""],
      ["UC-18", "", "●", "", "●", "", "", "", "", "", ""],
      ["UC-19", "", "", "", "●", "", "", "", "", "", ""],
      ["UC-21", "○", "", "", "○", "", "", "●", "", "", ""],
      ["UC-22", "", "", "", "", "", "", "", "", "", "●"],
      ["UC-23", "", "●", "", "", "", "", "", "", "", ""],
      ["UC-24", "", "●", "", "", "", "", "", "", "", ""],
    ]
  )
);
p(
  "Ghi chú bảng: UC-02 phụ thuộc nguồn `farm/ai` nằm ngoài repo, nên không đánh dấu nguồn dữ liệu. Ca 1 do watchdog trong app và Datadog cùng phát hiện; ký hiệu đặt trên watchdog và Datadog."
);

// ---- 5 Ma trận truy vết ----
h1("5 Ma trận truy vết");
h2("5.1 Từ use case đến trang, mô-đun, tệp test và bằng chứng");
p("Tên tệp test là tên thật trong `tests/`, kiểm bằng grep ngày 06/11/2026. Ô \"không có\" nghĩa là không có tệp test tự động cho use case đó.");
body.push(tableCaption("Bảng 5.1. Ma trận truy vết"));
table(
  dataTable(
    ["UC", "Trang hoặc mô-đun", "Tệp test trong `tests/`", "Bằng chứng"],
    [0.08, 0.3, 0.3, 0.32],
    [
      ["UC-01", "`pages/home.py`; `service/telemetry_health.py`", "`test_node_status.py` (ComputeNodeStatusTest, ReconcileTest)", "[E-11, E-14]"],
      ["UC-02", "`pages/home.py`; `service/mqtt.py`; `service/auth.py`", "`test_ai_failsafe.py`; `test_rv1_fixes.py` (AiHoldTests)", "—"],
      ["UC-03", "`pages/login.py`; `service/auth.py`", "không có", "—"],
      ["UC-04", "`pages/permission.py`; `service/auth.py`", "không có", "—"],
      ["UC-05", "`pages/plc.py`; `service/demo_mode.py`", "không có", "—"],
      ["UC-06", "`pages/schedule.py`; `service/scheduler.py`", "không có", "—"],
      ["UC-07", "`pages/public_lot.py`; `service/traceability.py`", "không có", "—"],
      ["UC-08", "`pages/traceability.py`; `pages/mongodb_lab.py`", "không có", "[E-18]"],
      ["UC-09", "`pages/chart.py`", "không có cho `/chart`", "[E-52, E-72]"],
      ["UC-10", "`pages/incident.py`; `service/incident_blackbox.py`", "`test_incident_list.py`; `test_incident_cases.py`", "[E-16, E-17]"],
      ["UC-11", "`pages/incident.py`", "`test_incident_navigation.py` (SixQuestionsTest); `test_incident_polish.py`", "[E-17, E-40, E-41]"],
      ["UC-12", "`service/telemetry_health.py`; `service/mqtt.py`", "`test_incident_autolink.py` (WatchdogLinkTests); `test_node_status.py` (ReconcileTest)", "[E-14, E-50]"],
      ["UC-13", "Datadog Workflow e2835af0", "không có (cấu hình ngoài repo)", "[E-55]"],
      ["UC-14", "`service/telemetry_health.py`; `service/incident_lifecycle.py`; `scripts/wokwi_datadog_bridge.py`", "`test_flatline_auto.py`; `test_incident_autolink.py` (test_start_flatline_incident_document_has_ids)", "[E-14, E-15, E-40, E-41, E-56]"],
      ["UC-15", "`main.py`; `scripts/verify_and_clear_demo_safe_mode.py`; `service/telemetry_health.py`", "`test_flatline_recovery.py`", "[E-22, E-56, E-86]"],
      ["UC-16", "`scripts/smiot_external_probe.py`", "`test_probe_autolink.py` (ServiceDownDocumentTests, WorkflowLookupTests); `test_gap_scope.py`", "[E-23, E-59]"],
      ["UC-17", "`scripts/aws/smiot-recover-guarded.sh`; `scripts/drill_ca3_service_down.ps1`", "không có tệp test tự động cho shell script", "[E-24, E-27, E-43, E-54, E-59, E-82]"],
      ["UC-18", "`pages/incident.py`; `service/incident_lifecycle.py`", "`test_incident_navigation.py` (SixQuestionsTest); `test_incident_polish.py` (FirstTraceTest)", "[E-17, E-60, E-83]"],
      ["UC-19", "`service/observability.py`; `service/ai_service.py`", "`test_llmobs.py` (LlmObsEnabledTests, ApiKeyNotLeakedTests)", "[E-19, E-84]"],
      ["UC-21", "`main.py`", "`test_healthz.py`", "—"],
      ["UC-22", "`service/telegram_bot.py`", "không có", "—"],
      ["UC-23", "`scripts/aws/mongodb_backup.sh`; `scripts/aws/mongodb_restore_drill.sh`", "không có", "[E-28, E-42]"],
      ["UC-24", "`pages/incident.py`; `service/incident_blackbox.py`", "`test_incident_graphs.py` (ImpactCardsTest, QualitySeriesTest); `test_gap_scope.py`", "[E-16, E-17]"],
    ]
  )
);
p("Tổng số test theo mục E-30 là 162 test đạt trên máy local ngày 06/11/2026, thuộc 17 tệp test [E-30].");

h2("5.2 Bảng tuyên bố, bằng chứng và trạng thái");
body.push(tableCaption("Bảng 5.2. Tuyên bố – Bằng chứng – Trạng thái"));
table(
  dataTable(
    ["Tuyên bố", "Bằng chứng", "Trạng thái"],
    [0.5, 0.26, 0.24],
    [
      ["Trang `/incident` và `/incident/{id}` chỉ cho admin hoặc quyền `manage_users`", "[E-17]", "đã kiểm chứng mã"],
      ["Ca 1 từ chối restart; workflow chỉ có bước Echo, không tác động EC2", "[E-55]", "đã kiểm chứng mã (cấu hình); execution đang bổ sung [E-81]"],
      ["Verifier CLEAR yêu cầu ít nhất 10 mẫu, mẫu mới nhất không quá 90 s, biên độ ít nhất 0,5 (mã hiện tại)", "[E-22]", "đã kiểm chứng mã"],
      ["Phục hồi Ca 3 được xác minh bằng HTTP và mẫu Mongo mới không quá 180 s", "[E-24]", "đã kiểm chứng mã; tác nhân khởi động 06/11 là workflow tự kích hoạt [E-82]"],
      ["Ca 3 ngày 06/11 đo được dừng 418 s đến phục hồi xác minh", "[E-59]", "đã kiểm chứng một phần (một lần quan sát)"],
      ["Ca 2 có hai hồ sơ đầy đủ ngày 03/11", "[E-40, E-41]", "đã kiểm chứng (tài liệu)"],
      ["Ca 2 ngày 06/11 đạt execution thành công; trạng thái `recovered` đang bổ sung", "[E-56, E-86]", "đang bổ sung (phần `recovered`)"],
      ["Trang `/chart` chỉ điều hướng sang Datadog, mở tab mới", "—", "đã kiểm chứng mã"],
      ["LLMObs bật với `ml_app` smiot-smart-farm; nội dung vào và ra bị che", "[E-19]", "đã kiểm chứng mã; ảnh đang bổ sung [E-84]"],
      ["162 test đơn vị đạt trên máy local ngày 06/11/2026", "[E-30]", "đã kiểm chứng (chạy local)"],
      ["Dashboard `nkc-685-vw8` có 12 widget ngày 06/11", "Số liệu người dùng cung cấp; E-03 ghi 8 widget ngày 04/11", "đang bổ sung"],
      ["Dữ liệu tổng hợp, có nhãn `source.synthetic` và `meta.source`", "[E-02, E-13]", "đã kiểm chứng mã"],
      ["PLC là PLC ảo, không điều khiển thiết bị vật lý", "[E-02]", "đã kiểm chứng mã"],
      ["Dữ liệu hiện có cho Greenhouse A; Greenhouse B đến D nằm ngoài phạm vi hiện tại", "Xác nhận của người dùng 06/11", "đang bổ sung (không có bằng chứng trong repo)"],
      ["Sao lưu logic khớp 154.618/154.618 mẫu và 1/1 sự cố ngày 03/11", "[E-42]", "đã kiểm chứng (tài liệu)"],
    ]
  )
);

// ---- 6 Hạn chế và phạm vi ----
h1("6 Hạn chế và phạm vi");
const limitItems = [
  "**Dữ liệu tổng hợp.** Toàn bộ số đo đến từ bộ phát demo và cầu nối Wokwi. Không có thiết bị vật lý trong phạm vi. Nhãn tổng hợp nằm trong `source.synthetic` và `meta.source` [E-13].",
  "**PLC ảo.** Trạng thái bơm, chế độ an toàn và ACK đều do PLC ảo trong ứng dụng thực hiện. Hồ sơ không nói về thiết bị vật lý nào.",
  "**Phạm vi farm.** Dữ liệu hiện có cho Greenhouse A; Greenhouse B đến D nằm ngoài phạm vi hiện tại (N6). Watchdog quét cả bốn farm nhưng sự cố Ca 2 chỉ mở cho greenhouse_a node 2 [E-14].",
  "**Luồng `farm/ai` chưa có publisher trong repo.** Card đề xuất AI và bộ tiêu thụ `farm/ai` có mã, nhưng nguồn phát nằm ngoài repo (UC-02, N4).",
  "**Một EC2 cho app, MongoDB, Mosquitto và Datadog Agent.** Các thành phần chung một miền lỗi [E-03].",
  "**Ca 1 có execution ghi nhận.** Lượt `a782b12c…` (04:50:21Z) ghi nhánh REFUSED_RESTART; đầu ra từng bước đang bổ sung [E-55, E-81].",
  "**Ca 2 ngày 06/11: trạng thái `recovered` đang bổ sung.** HOLD và CLEAR trong sổ hành động đang bổ sung để đối chiếu [E-86].",
  "**Ca 3 ngày 06/11: tác nhân khởi động là workflow.** Monitor Alert lúc 03:11:43Z, workflow chạy lúc 03:12:43Z [E-82]. Đầu ra lệnh trên EC2 và log `smiot.guarded_recovery` đang bổ sung [E-82].",
  "**Số widget dashboard.** E-03 ghi 8 widget ngày 04/11; ghi nhận 12 widget ngày 06/11. Đang bổ sung xác nhận trước khi nộp (Phụ lục A, A9).",
];
limitItems.forEach((t, i) => p(`${i + 1}. ${t}`));
// Note: the source markdown's own numbered list skips "10." and continues at
// "11." — preserved here verbatim as plain numbered text (not Word
// auto-numbering) so the source's exact (slightly irregular) sequence is not
// silently "corrected".
body.push(para("11. **Quyền đọc từ hai nguồn.** Trang đọc quyền từ phiên đăng nhập; điều khiển bơm và lịch đọc từ MongoDB. Hiệu lực có thể lệch cho đến khi đăng nhập lại (UC-04)."));
body.push(para("12. **Một phần chưa có test tự động.** Đăng nhập, quản lý quyền, PLC, lịch, lô công khai, `/chart`, bot Telegram và shell script guard chưa có tệp test trong `tests/`."));
body.push(para("13. **ID sự cố cố định trong dữ liệu seed.** `service/demo_mode.py:90` gắn nhãn `greenhouse-a-node2-flatline-20261101` cho một số mẫu seed lịch sử. Cần đối chiếu để không nhầm với sự cố 03/11 và 06/11."));
body.push(para("14. **Ngưỡng verifier thay đổi theo phiên bản.** Mã hiện tại yêu cầu 10 mẫu, nhưng chuỗi lý do trong mã vẫn có chữ \"six or more\" [E-22]. Số mẫu trong hồ sơ là số quan sát của từng lần."));
body.push(para("15. **Spec workflow nằm ngoài repo.** Repo chỉ có ảnh cấu trúc workflow 18d1b008 và b83453ff [E-53, E-54]. Cần xuất JSON để đối chiếu (A8)."));
body.push(para("16. **MongoDB.** Hệ thống chạy MongoDB Community tự quản, khai báo chế độ standalone; cần xác nhận phiên bản và chế độ bằng lệnh chỉ đọc [E-80]. Hệ thống không sử dụng Atlas Search, Vector Search, Triggers, Charts hoặc Stream Processing, và không dùng Change Streams."));
body.push(para("17. **Thời lượng diễn tập.** Mỗi ca có một lần quan sát đo được. Chỉ số thời gian phát hiện hay khôi phục trung bình chưa được tính; SLO chưa đủ 7 ngày dữ liệu."));
body.push(para("18. **Trợ lý AI và Telegram.** Ảnh span LLM Observability của trợ lý AI đang bổ sung; bot Telegram đang chạy (UC-22)."));

// ---- 7 Kết luận ----
h1("7 Kết luận");
p(
  "Hồ sơ đặc tả 24 use case của SMIOT Smart Farm và truy vết mỗi use case tới trang, mô-đun và tệp test. Phần đã kiểm chứng mã gồm ba chuỗi phản ứng cho ba lớp lỗi: Ca 1 từ chối restart, Ca 2 HOLD và CLEAR sau xác minh, Ca 3 khởi động có điều kiện với xác minh bằng dữ liệu đọc lại. Phần còn thiếu bằng chứng là kết quả chạy trên hệ thống sống: execution Ca 1, tác nhân và execution Ca 3 ngày 06/11, trạng thái `recovered` Ca 2 ngày 06/11, ảnh giao diện, và số widget dashboard. Các mục này nằm trong Phụ lục A và đang bổ sung bổ sung trước khi chốt."
);

// ---- Phụ lục A ----
h1("Phụ lục A. Mục cần bổ sung");
p("Phụ lục gom mọi mục «ĐANG BỔ SUNG» trong tài liệu. Cột \"Liên quan\" trỏ tới use case hoặc bằng chứng.");
table(
  dataTable(
    ["Mã", "Nội dung cần bổ sung", "Liên quan"],
    [0.07, 0.68, 0.25],
    [
      ["A1", "«URL demo — ĐANG BỔ SUNG»: quyết định có ghi địa chỉ truy cập hay không (hostname có chứa IP công khai)", "Bảng Đọc nhanh"],
      ["A2", "Tài khoản giám khảo có vai trò admin hoặc quyền `manage_users` để xem `/incident`", "UC-10, UC-11 [E-17]"],
      ["A3", "Ảnh `/incident` (ba thẻ ca) và `/incident/{id}` từng ca", "UC-10, UC-11 [E-83]"],
      ["A4", "Ảnh LLM Observability với `ml_app` smiot-smart-farm và nội dung bị che", "UC-19 [E-84]"],
      ["A5", "Ca 1: bản ghi diễn tập đang bổ sung: incident ID, mốc thời gian, số lần restart bằng 0 (execution `REFUSED_RESTART` đã có [E-81])", "UC-12, UC-13 [E-81]"],
      ["A6", "Ca 2 ngày 06/11: incident ID, HOLD và CLEAR trong `action_ledger`, trạng thái `recovered`", "UC-15 [E-86]"],
      ["A7", "Ca 3 ngày 06/11: đầu ra lệnh `recover-smiot-web` trên EC2 và log `smiot.guarded_recovery` (`action`, `result`)", "UC-17 [E-82]"],
      ["A8", "Xuất JSON của workflow 18d1b008 và b83453ff (spec nằm ngoài repo)", "UC-15, UC-17 [E-53, E-54]"],
      ["A9", "Số widget dashboard `nkc-685-vw8` ngày 06/11 (người dùng báo 12; E-03 ghi 8 ngày 04/11): ảnh toàn trang hoặc export JSON", "UC-09 [E-52, E-03]"],
      ["A10", "Nguồn phát bản tin `farm/ai` có nằm ngoài repo hay không", "UC-02, N4"],
      ["A11", "Bot Telegram có đang chạy không, và có đưa vào hồ sơ không", "UC-22"],
      ["A13", "Xác nhận phiên bản MongoDB và chế độ standalone bằng lệnh chỉ đọc", "Mục 6, hạn chế 16 [E-80]"],
      ["A14", "Kiểm chứng hành vi lệch quyền giữa phiên và MongoDB trên hệ thống sống", "UC-04, Hình 2.3"],
      ["A15", "Sửa khai báo `docs/DECLARATIONS.md`: mục ghi không có LLM Observability không khớp mã (`service/observability.py:50-61`)", "UC-19 [E-02, E-19]"],
      ["A16", "Xác nhận các bản ghi Ca 3 ngày 06/11 trong `outputs/drill_ca3_20261106T030613Z.json` có trường execution trống; bổ sung nếu có", "UC-17 [E-59]"],
      ["A17", "Ảnh log và APM theo `incident_id` (kiểm che thông tin trước khi dùng)", "UC-18 [E-60]"],
      ["A18", "Mục đích thứ ba của hệ thống; đang bổ sung căn cứ để ghi", "Mục đích hệ thống"],
    ]
  )
);

// ===========================================================================
// DOCUMENT ASSEMBLY
// ===========================================================================
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "decimal-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  styles: {
    default: {
      document: {
        run: { font: FONT, size: BODY_SIZE },
        paragraph: { spacing: { after: 120 } },
      },
      heading1: {
        run: { font: FONT, size: 32, bold: true, color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 180 }, keepNext: true, pageBreakBefore: false },
      },
      heading2: {
        run: { font: FONT, size: 28, bold: true, color: "2E5496" },
        paragraph: { spacing: { before: 280, after: 140 }, keepNext: true },
      },
      heading3: {
        run: { font: FONT, size: 24, bold: true, color: "2E5496" },
        paragraph: { spacing: { before: 220, after: 120 }, keepNext: true },
      },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH_TWIP, height: PAGE_HEIGHT_TWIP },
          margin: { top: MARGIN_TWIP, bottom: MARGIN_TWIP, left: MARGIN_TWIP, right: MARGIN_TWIP },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 }),
              ],
            }),
          ],
        }),
      },
      children: [...coverChildren, ...tocChildren, ...body],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT_PATH, buffer);
  console.log("Wrote", OUT_PATH, buffer.length, "bytes");
});
