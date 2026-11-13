'use strict';
/* Build SMIOT_04_Mo_ta_su_co.docx from docs/submission/04_mo_ta_su_co_van_hanh.md
 * Faithful conversion: no content added/removed, only formatting.
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, Footer, PageNumber, LevelFormat, ImageRun,
  PageBreak, convertInchesToTwip, VerticalAlign
} = require('docx');

const ROOT = 'D:\\IOT Trung\\code_full_server';
const MD_PATH = path.join(ROOT, 'docs', 'submission', '04_mo_ta_su_co_van_hanh.md');
const FIG_DIR = path.join(ROOT, 'outputs', 'submission_export', 'figures');
const OUT_PATH = path.join(ROOT, 'outputs', 'submission_word', 'SMIOT_04_Mo_ta_su_co.docx');

const raw = fs.readFileSync(MD_PATH, 'utf8');

// ---------- split front matter ----------
const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
if (!fmMatch) throw new Error('Front matter not found');
const fmText = fmMatch[1];
const body = fmMatch[2];

function fmField(name) {
  const re = new RegExp('^' + name + ':\\s*(.+)$', 'm');
  const m = fmText.match(re);
  if (!m) return '';
  let v = m[1].trim();
  if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1);
  return v;
}
const docTitle = fmField('title');
const docVersion = fmField('version');
const docDate = fmField('date');

// ---------- PNG dimension reader (no extra deps) ----------
function pngSize(file) {
  const buf = fs.readFileSync(file);
  // PNG signature 8 bytes, then IHDR chunk: length(4) type(4) width(4) height(4)
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height };
}

// ---------- inline markdown parser ----------
// returns array of {text, bold, italics, code}
function parseInline(str) {
  const runs = [];
  let i = 0;
  while (i < str.length) {
    if (str[i] === '`') {
      const j = str.indexOf('`', i + 1);
      if (j === -1) { runs.push({ text: str.slice(i) }); break; }
      runs.push({ text: str.slice(i + 1, j), code: true });
      i = j + 1;
      continue;
    }
    if (str.startsWith('**', i)) {
      const j = str.indexOf('**', i + 2);
      if (j === -1) { runs.push({ text: str.slice(i) }); break; }
      runs.push({ text: str.slice(i + 2, j), bold: true });
      i = j + 2;
      continue;
    }
    if (str[i] === '*') {
      const j = str.indexOf('*', i + 1);
      if (j === -1) { runs.push({ text: str.slice(i) }); break; }
      runs.push({ text: str.slice(i + 1, j), italics: true });
      i = j + 1;
      continue;
    }
    let j = i;
    while (j < str.length && str[j] !== '`' && str[j] !== '*') j++;
    if (j === i) j++;
    runs.push({ text: str.slice(i, j) });
    i = j;
  }
  return runs;
}

function makeRuns(str, extra) {
  extra = extra || {};
  return parseInline(str).map(r => new TextRun(Object.assign({
    text: r.text,
    bold: !!r.bold || !!extra.bold,
    italics: !!r.italics || !!extra.italics,
    font: r.code ? 'Consolas' : (extra.font || undefined),
    size: extra.size || undefined,
  }, r.code ? { shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' } } : {})));
}

// ---------- block-level parser ----------
const lines = body.split(/\r?\n/);
const blocks = [];
let i = 0;
let mermaidCount = 0;

function isTableRow(line) {
  return /^\s*\|.*\|\s*$/.test(line);
}
function isSeparatorRow(line) {
  return /^\s*\|?[\s:\-|]+\|?\s*$/.test(line) && line.includes('-');
}
function splitRow(line) {
  let t = line.trim();
  if (t.startsWith('|')) t = t.slice(1);
  if (t.endsWith('|')) t = t.slice(0, -1);
  // split on unescaped pipes
  return t.split('|').map(c => c.trim());
}

while (i < lines.length) {
  let line = lines[i];

  if (line.trim() === '') { i++; continue; }

  // mermaid code block
  if (line.trim().startsWith('```mermaid')) {
    i++;
    while (i < lines.length && lines[i].trim() !== '```') i++;
    i++; // skip closing ```
    mermaidCount++;
    blocks.push({ type: 'image', n: mermaidCount });
    continue;
  }
  // any other fenced code block (none expected, but guard)
  if (line.trim().startsWith('```')) {
    i++;
    while (i < lines.length && lines[i].trim() !== '```') i++;
    i++;
    continue;
  }

  // headings
  let hm = line.match(/^(#{1,3})\s+(.*)$/);
  if (hm) {
    const level = hm[1].length;
    blocks.push({ type: 'h' + level, text: hm[2].trim() });
    i++;
    continue;
  }

  // table
  if (isTableRow(line) && i + 1 < lines.length && isSeparatorRow(lines[i + 1])) {
    const header = splitRow(line);
    i += 2;
    const rows = [];
    while (i < lines.length && isTableRow(lines[i])) {
      rows.push(splitRow(lines[i]));
      i++;
    }
    blocks.push({ type: 'table', header, rows });
    continue;
  }

  // bullet list
  if (/^\s*-\s+/.test(line)) {
    const items = [];
    while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
      items.push(lines[i].replace(/^\s*-\s+/, ''));
      i++;
    }
    blocks.push({ type: 'ul', items });
    continue;
  }

  // numbered list
  if (/^\s*\d+\.\s+/.test(line)) {
    const items = [];
    while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
      items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
      i++;
    }
    blocks.push({ type: 'ol', items });
    continue;
  }

  // paragraph (accumulate until blank line or next special block)
  {
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim() !== '' &&
      !/^#{1,3}\s+/.test(lines[i]) &&
      !lines[i].trim().startsWith('```') &&
      !isTableRow(lines[i]) &&
      !/^\s*-\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])) {
      buf.push(lines[i]);
      i++;
    }
    const text = buf.join(' ').trim();
    const captionMatch = /^\*Hình\s.*\*$/.test(text);
    blocks.push({ type: captionMatch ? 'caption' : 'p', text });
    continue;
  }
}

// ---------- styles / numbering ----------
const PAGE_WIDTH_DXA = 11906; // A4 portrait
const MARGIN_DXA = 1134; // ~2cm
const CONTENT_WIDTH_DXA = PAGE_WIDTH_DXA - 2 * MARGIN_DXA;

const styles = {
  default: {
    document: {
      run: { font: 'Times New Roman', size: 24 }, // 12pt
      paragraph: { spacing: { line: 276, after: 160 } },
    },
    heading1: {
      run: { font: 'Calibri', size: 32, bold: true, color: '1F4E79' },
      paragraph: { spacing: { before: 360, after: 200 }, keepNext: true },
    },
    heading2: {
      run: { font: 'Calibri', size: 27, bold: true, color: '2E74B5' },
      paragraph: { spacing: { before: 280, after: 160 }, keepNext: true },
    },
    heading3: {
      run: { font: 'Calibri', size: 24, bold: true, color: '1F4E79' },
      paragraph: { spacing: { before: 220, after: 120 }, keepNext: true },
    },
  },
};

const numbering = {
  config: [
    {
      reference: 'bullet-list',
      levels: [
        {
          level: 0,
          format: LevelFormat.BULLET,
          text: '\u2022',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        },
      ],
    },
    {
      reference: 'num-list',
      levels: [
        {
          level: 0,
          format: LevelFormat.DECIMAL,
          text: '%1.',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        },
      ],
    },
  ],
};

// ---------- assemble body children ----------
const children = [];

// Cover page
children.push(
  new Paragraph({ spacing: { before: 1800 }, alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: 'SMIOT Smart Farm', bold: true, size: 56, font: 'Calibri' }),
  ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 600 }, children: [
    new TextRun({ text: 'Mini Hackathon MongoDB x Datadog 2026', size: 30, font: 'Calibri' }),
  ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 200 }, children: [
    new TextRun({ text: docTitle, bold: true, size: 40, font: 'Calibri' }),
  ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 }, children: [
    new TextRun({ text: 'Mục hồ sơ: 11', size: 26, font: 'Calibri' }),
  ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, children: [
    new TextRun({ text: `Phiên bản ${docVersion} — ${docDate}`, size: 24, font: 'Calibri' }),
  ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 }, children: [
    new TextRun({ text: 'Dữ liệu tổng hợp (synthetic data)', italics: true, size: 24, font: 'Calibri' }),
  ] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Table of contents
children.push(
  new Paragraph({ children: [new TextRun({ text: 'Mục lục', bold: true, size: 32, font: 'Calibri' })], spacing: { after: 200 } }),
  new TableOfContents('Mục lục', {
    hyperlink: true,
    headingStyleRange: '1-3',
  }),
  new Paragraph({ children: [new PageBreak()] }),
);

let tableCount = 0;
let imageCount = 0;
let h1Count = 0, h2Count = 0, h3Count = 0;

function cellParaFromText(text, opts) {
  opts = opts || {};
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
    children: makeRuns(text, { bold: opts.bold, size: opts.size }),
  });
}

for (const b of blocks) {
  if (b.type === 'h1') {
    h1Count++;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: makeRuns(b.text) }));
  } else if (b.type === 'h2') {
    h2Count++;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: makeRuns(b.text) }));
  } else if (b.type === 'h3') {
    h3Count++;
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: makeRuns(b.text) }));
  } else if (b.type === 'p') {
    children.push(new Paragraph({ children: makeRuns(b.text), spacing: { after: 160 } }));
  } else if (b.type === 'caption') {
    const inner = b.text.replace(/^\*/, '').replace(/\*$/, '');
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 240 },
      children: [new TextRun({ text: inner, italics: true, size: 20, font: 'Calibri' })],
    }));
  } else if (b.type === 'ul') {
    for (const item of b.items) {
      children.push(new Paragraph({
        numbering: { reference: 'bullet-list', level: 0 },
        children: makeRuns(item),
      }));
    }
  } else if (b.type === 'ol') {
    for (const item of b.items) {
      children.push(new Paragraph({
        numbering: { reference: 'num-list', level: 0 },
        children: makeRuns(item),
      }));
    }
  } else if (b.type === 'table') {
    tableCount++;
    const header = b.header;
    const ncols = header.length;
    const colWidths = [];
    const base = Math.floor(CONTENT_WIDTH_DXA / ncols);
    let sum = 0;
    for (let c = 0; c < ncols; c++) {
      if (c === ncols - 1) colWidths.push(CONTENT_WIDTH_DXA - sum);
      else { colWidths.push(base); sum += base; }
    }
    const headerRow = new TableRow({
      tableHeader: true,
      children: header.map((h, c) => new TableCell({
        width: { size: colWidths[c], type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: 'D9E2F3', color: 'auto' },
        verticalAlign: VerticalAlign.CENTER,
        children: [cellParaFromText(h, { bold: true })],
      })),
    });
    const dataRows = b.rows.map(r => new TableRow({
      children: header.map((_, c) => new TableCell({
        width: { size: colWidths[c], type: WidthType.DXA },
        verticalAlign: VerticalAlign.CENTER,
        children: [cellParaFromText(r[c] !== undefined ? r[c] : '')],
      })),
    }));
    children.push(new Table({
      width: { size: CONTENT_WIDTH_DXA, type: WidthType.DXA },
      columnWidths: colWidths,
      rows: [headerRow, ...dataRows],
    }));
    children.push(new Paragraph({ text: '', spacing: { after: 160 } }));
  } else if (b.type === 'image') {
    imageCount++;
    const file = path.join(FIG_DIR, `fig_04_0${b.n}.png`);
    const dim = pngSize(file);
    const maxWidthPx = 560; // ~ fits content width at 96dpi context used by docx image sizing
    let w = dim.width, h = dim.height;
    if (w > maxWidthPx) {
      const scale = maxWidthPx / w;
      w = Math.round(w * scale);
      h = Math.round(h * scale);
    }
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 80 },
      children: [new ImageRun({
        type: 'png',
        data: fs.readFileSync(file),
        transformation: { width: w, height: h },
      })],
    }));
  }
}

// ---------- document ----------
const doc = new Document({
  creator: 'SMIOT',
  title: docTitle,
  styles,
  numbering,
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH_DXA, height: 16838 }, // A4
          margin: { top: MARGIN_DXA, bottom: MARGIN_DXA, left: MARGIN_DXA, right: MARGIN_DXA },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ children: [PageNumber.CURRENT] })],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log('WROTE', OUT_PATH, buf.length, 'bytes');
  console.log('Counts:', { h1Count, h2Count, h3Count, tableCount, imageCount, mermaidCount });
}).catch(err => {
  console.error('BUILD ERROR', err);
  process.exit(1);
});
