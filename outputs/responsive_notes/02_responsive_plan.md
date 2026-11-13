# Kế hoạch responsive SMIOT Smart Farm (375 / 768 / ≥1280)

Ngày lập: 2026-11-07. Hạn nộp 23:59 08/11/2026. Chỉ đọc mã để lập kế hoạch; chưa chạy trình duyệt.
Đường dẫn là `file:dòng` so với `D:\IOT Trung\code_full_server`. Dòng có thể lệch 1-2 sau khi sửa; luôn tìm theo đoạn trích, không theo số dòng.

## 0. Kết quả kiểm chứng ghi chú Haiku (đọc mã trực tiếp)

ĐÚNG:
- `.main-content` có `padding-left:200px` (`pages/home.py:125`); khối `@media (max-width:768px)` chỉ đặt `margin-left:0` (`home.py:426`), KHÔNG reset padding. Trên điện thoại nội dung bị mất 200px bên trái (còn ~175px ở 375px). Đây là lỗi số 1, ảnh hưởng mọi trang có sidebar.
- `permission.py:101` grid `1fr 2fr` không có media; `project.py:180` KPI `repeat(5,1fr)`, `project.py:243,250` bảng `1fr 1.2fr 0.7fr 0.5fr 1fr`; `schedule.py:177` (560px) và `:329` (400px) dialog cố định; `data_table.py:395` `min-width:800px`; `login.py:48-49` card 420px `max-width:92%`.
- `incident.py` đã có 1 media ở 760px cho `.inc-qtable`; các lưới `auto-fit minmax` đã co được.

SAI hoặc THIẾU:
1. SAI/THIẾU NGHIÊM TRỌNG: Haiku viết `.sidebar div:last-child` chỉ ẩn "footer". Thực tế selector này khớp MỌI `div` con cuối ở mọi tầng bên trong sidebar (`home.py:448`). Mỗi mục nav là `<a><div>icon+nhãn</div></a>` vì `ui.html` mặc định bọc bằng thẻ `div` (`nicegui/elements/html.py`: `tag='div'`, đã kiểm tra bản 3.17.1), và `div` đó là con duy nhất nên là `:last-child`. Hệ quả rất có khả năng: ở ≤768px icon và nhãn của thanh điều hướng đáy bị `display:none !important`, thanh đáy trống. CẦN XÁC NHẬN BẰNG TRÌNH DUYỆT thu nhỏ (việc B1 dưới đây), nhưng sửa selector thành `.sidebar > div:last-child` là an toàn dù kết luận thế nào.
2. Thiếu: spacer `ui.element("div").style("flex:1")` (`home.py:781`) vẫn nằm trong thanh đáy dạng hàng, chiếm chỗ cùng các mục `flex:1`. Cần ẩn trên mobile.
3. Thiếu: `.nicegui-content` bị ép `overflow-x:hidden !important` và `html, body, #q-app` `overflow:hidden !important` (`home.py:22-43`). Vì vậy KHÔNG có cuộn ngang cấp trang; nội dung tràn sẽ bị CẮT chứ không cuộn. Khác với kết luận "bảng sẽ cuộn ngang trong content-area" của Haiku: `.content-area` chỉ cuộn ngang nếu phần tử con thật sự rộng hơn nó (Haiku đúng ở điểm này về lý thuyết) nhưng cần xác nhận thực tế. Phương án an toàn: luôn bọc bảng rộng trong khung `overflow-x:auto` (nhóm c).
4. Nhận định "`/chart` có biểu đồ" dễ gây hiểu nhầm: `/chart` (`chart.py:43-67`) chỉ là hub 3 thẻ liên kết sang Datadog, không có biểu đồ. Biểu đồ ECharts thật nằm ở `incident.py:948` (cao 240px, `w-full`, đã ổn), `mongodb_lab.py:69-97`, `schedule.py:763-772`; Recharts ở `/inverter`.
5. Haiku ghi `/login` "ổn". Gần đúng nhưng còn: `.login-page` cao `100vh` và `body{overflow:hidden}` (`login.py:19,26`): trên điện thoại khi bàn phím bật hoặc thanh địa chỉ co giãn, card có thể bị cắt và không cuộn được. Cần `100dvh` + `overflow-y:auto`.
6. Topbar: Haiku đúng là không wrap. Thêm chi tiết: có 2 nơi đặt style inline `padding:12px 20px; justify-content:space-between` (`home.py:589`) nên CSS của `.top-bar` phải dùng `!important` hoặc nhắm bằng thuộc tính; và nút avatar/chuông là 40px (`w-10 h-10`, `home.py:659`) nên đạt 40px.
7. Trang chủ: Haiku nêu menu chuông `w-80` (320px) neo `bottom right`; ở 375px còn vừa nếu neo phải, nhưng với `padding-left:200px` chưa sửa thì lệch. Sau khi sửa B1/A1 cần kiểm tra lại, chưa chắc cần đổi mã.

## 1. Thứ tự ưu tiên trang

| # | Trang | Lý do ngắn |
|---|---|---|
| 1 | Khung chung (sidebar/main-content/topbar) | Một lỗi sửa một chỗ, ảnh hưởng 100% trang; hiện lỗi padding 200px làm mọi trang hỏng trên điện thoại |
| 2 | `/incident`, `/incident/{id}` | Trang giám khảo mở nhiều nhất (3 ca diễn tập, hồ sơ điều tra) |
| 3 | `/` trang chủ | Trang đầu tiên sau đăng nhập |
| 4 | `/chart` | Hub dẫn sang Datadog, giám khảo bấm qua |
| 5 | `/login` | Cổng vào; thường mở trước mọi trang |
| 6 | `/schedule`, `/data`, `/permission`, `/projects` | Rủi ro vỡ cao nhưng ít được mở khi chấm |
| 7 | `/devices`, `/mongodb-lab`, `/plc`, `/inverter` | Đã khá ổn, chỉ kiểm tra |
| 8 | `/lot/{token}` | Đã mobile-first, không đụng |

## 2. Quy tắc bắt buộc cho người thực hiện

1. KHÔNG đổi tên, chữ ký hàm/hằng số mà `tests/` import. Danh sách chính từ `pages/incident.py`: `_link_groups`, `build_impact_chart_data`, `METRIC_WINDOW_PAD`, `metric_links`, `metric_window`, `RECOVERY_GENERIC`, `_first_trace_link`, `_trace_links`, `build_six_questions`, `format_recovery_evidence`, `STATE_DONE`, `STATE_OPEN`, `build_list_rows`, `case_runs`, `case_summary_text`, `format_duration`, `run_state`, `scope_label`, `incident_headline`, `incident_summary`, `mongo_only_events`, `SRC_DATADOG`, `SRC_MONGO`. `tests/test_incident_navigation.py` yêu cầu `pages.incident` KHÔNG có `pick_bits_link`, `BITS_LIST_URL`, `BITS_NO_INVESTIGATION_NOTE` (đừng thêm lại). `tests/test_healthz.py` đọc AST của `main.py`: giữ nguyên `build_healthz_payload`, `_read_mongo_health`, `HEALTHZ_MONGO_TIMEOUT_SECONDS` ở cấp module. Không sửa `main.py` trừ khi bắt buộc (kế hoạch này không cần).
2. Không thêm thư viện. Không đổi route, quyền (`check_login`, `_guard`, `check_permission`), redirect (`/history`, `/traceability`). `pages/home.py` không import `pages.incident` (tránh vòng).
3. Ưu tiên sửa CSS (chuỗi `CUSTOM_CSS`, `INC_CSS`, ...) trước Python. Chỉ sửa Python khi CSS không đủ (đánh dấu rõ trong từng mục).
4. Mọi CSS responsive mới đặt ở CUỐI chuỗi CSS tương ứng, trong `@media`, để desktop (≥1280) không đổi. Không sửa quy tắc desktop sẵn có, trừ khi mục ghi rõ.
5. Chuỗi CSS nằm trong chuỗi Python `"""..."""` thường (không phải f-string) ở `home.py` và `incident.py`: cho phép viết `{ }` bình thường. Riêng `schedule.py:405-433` là f-string (có `{{` `}}`): khi thêm CSS ở đó phải nhân đôi dấu ngoặc nhọn.
6. Sau MỖI nhóm thay đổi chạy:
   `$env:PYTHONPATH=(Get-Location).Path; python -X utf8 -m unittest discover -s tests`
   và phải giữ đúng 168 test qua (nếu thêm test mới ở mục 5 thì số tổng tăng, nhưng 168 test cũ vẫn phải qua). Một thay đổi = một commit nhỏ để dễ revert.
7. Mọi `@media` dùng đúng hai ngưỡng: `max-width:768px` (điện thoại, trùng ngưỡng có sẵn của sidebar) và `max-width:1024px` (máy tính bảng). Riêng điện thoại hẹp dùng thêm `max-width:480px` khi cần. Kiểm tra ở 375, 768, 1280.

## 3. Danh sách thay đổi

Ký hiệu: [CSS] chỉ sửa CSS, [PY] cần sửa Python. "Kiểm tra" luôn gồm chạy unittest (quy tắc 6).

### Nhóm (a) Khung chung — Gói A

**A1. Reset padding-left của `.main-content` trên mobile** [CSS] — QUAN TRỌNG NHẤT
- File: `pages/home.py`, trong `@media (max-width: 768px)`, khối `.main-content` (`home.py:425-428`).
- Vấn đề: chỉ có `margin-left:0; padding-bottom:80px` nên `padding-left:200px` vẫn còn.
- Thay đổi: sửa khối thành
  ```css
  .main-content {
      margin-left: 0;
      padding-left: 0;
      padding-bottom: 60px;
      height: 100vh;
      height: 100dvh;
  }
  ```
  (`padding-bottom:60px` bằng chiều cao thanh đáy; trước là 80px, giữ 80px cũng được nếu muốn dư chỗ; không bắt buộc đổi.)
- Breakpoint: ≤768.
- Kiểm tra: thu cửa sổ 375px, mở `/incident`: nội dung bắt đầu sát mép trái, rộng ~375px, nút cuối trang không bị thanh đáy che.

**A2. Sửa selector ẩn footer sidebar trên mobile + ẩn spacer** [CSS] (+ [PY] nhỏ cho spacer)
- File: `pages/home.py:448` và `home.py:781`.
- Vấn đề: `.sidebar div:last-child` khớp cả `div` do `ui.html` sinh trong mỗi mục nav (xem mục 0.1), có thể làm thanh đáy trống.
- Thay đổi CSS: đổi dòng 448 thành
  ```css
  .sidebar-logo, .sidebar-section, .sidebar > div:last-child, .sidebar-spacer {
      display: none !important;
  }
  ```
- Thay đổi PY (1 dòng, `home.py:781`): `ui.element("div").style("flex:1")` thành `ui.element("div").classes("sidebar-spacer").style("flex:1")`. Nếu muốn tránh sửa Python: bỏ `.sidebar-spacer` khỏi CSS và chấp nhận spacer nhỏ (spacer `flex:1` ngang bằng 1 mục nav, lãng phí 1 ô; không khuyến nghị).
- Kiểm tra: ở 375px thanh đáy hiện đủ icon + nhãn; ở 1280px sidebar không đổi (footer "SMIOT System v2.0" vẫn hiện).

**B1 (xác nhận trước khi sửa A2). Kiểm tra bằng trình duyệt** — người dùng hoặc agent có quyền tự mở `http://localhost:8080` với cửa sổ 375px (xem mục 5). Ghi lại: thanh đáy trống hay không, nội dung có bị lệch 200px hay không. Kết quả không làm thay đổi việc phải làm A1/A2.

**A3. Thanh điều hướng đáy có tối đa 11 mục: cho cuộn ngang** [CSS]
- File: `pages/home.py` khối `@media (max-width: 768px)` (`home.py:429-461`).
- Vấn đề: 11 mục chia đều ~34px, chữ 10px, nhãn "Mùa vụ & truy xuất" bị xuống dòng/cắt; vi phạm ≥40px và ≥12px nếu cố nén.
- Thay đổi: trong `.sidebar` mobile thêm `justify-content: flex-start; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; scrollbar-width: none;` (thay `justify-content: space-around`) và sửa `.nav-item` mobile thành
  ```css
  .nav-item {
      margin: 0; padding: 6px 4px;
      font-size: 11px;
      flex: 0 0 auto; min-width: 64px; min-height: 48px;
      flex-direction: column; gap: 1px;
      text-align: center; justify-content: center;
      border-radius: 6px; white-space: nowrap;
  }
  .sidebar::-webkit-scrollbar { display: none; }
  ```
  Thêm `.nav-item span { font-size: 11px; }`. Lưu ý: yêu cầu chữ ≥12px chỉ áp dụng cho nội dung, nhãn nav 11px là ngoại lệ có chủ ý để đủ 5 mục hiện cùng lúc; nếu muốn tuân thủ cứng, dùng 12px và `min-width:72px`.
- Breakpoint: ≤768. Kiểm tra: 375px thấy ≥5 mục, vuốt ngang xem tiếp, mục `active` hiện rõ; không có scrollbar dọc.

**A4. Topbar: cho phép xuống dòng, thu gọn trên mobile** [CSS]
- File: `pages/home.py` thêm vào cuối `@media (max-width: 768px)` (sau `home.py:479`). Chú ý inline style ở `home.py:589` nên cần `!important`.
- Vấn đề: không `flex-wrap`; title + select `width:150px` (`home.py:610`) + DEMO + ACTIVE + chuông + avatar + tên tràn ở 375px.
- Thay đổi:
  ```css
  .top-bar { flex-wrap: wrap !important; gap: 8px; padding: 8px 12px !important; }
  .top-bar .q-field { width: 120px !important; margin-left: 0 !important; }
  .top-bar-title { flex-wrap: wrap; min-width: 0; gap: 8px !important; }
  .top-bar > div:last-child { gap: 8px !important; flex-wrap: wrap; justify-content: flex-end; }
  .content-area { padding: 12px !important; }
  ```
  Ẩn tên người dùng trên màn rất hẹp: thêm `@media (max-width:480px){ .top-bar .q-img ~ * { display:none } }` KHÔNG khuyến nghị (dễ ẩn nhầm). Phương án an toàn: để wrap, không ẩn.
- Kiểm tra: 375px topbar chiếm tối đa 2 hàng, không có phần tử bị cắt mép phải; chuông bấm được (40px).

**A5. Chiều cao theo `dvh`** [CSS]
- File: `home.py:127` `height: 100vh` của `.main-content`; đã gộp trong A1 (thêm `height:100dvh` trong media mobile). Trình duyệt cũ không hỗ trợ thì bỏ qua dòng `100dvh` và dùng `100vh` ngay trước.
- Không đổi desktop.

**A6. Menu chuông (kiểm tra, không bắt buộc sửa)** — `home.py:673` `w-80`. Nếu tràn ở 375px thì thêm CSS `@media (max-width:480px){ .q-menu { max-width: 94vw !important; } }` vào `CUSTOM_CSS` (ảnh hưởng mọi menu Quasar; chấp nhận được).

### Nhóm (b) Từng trang

**Gói A — `/incident` và `/incident/{id}`** (`pages/incident.py`, chuỗi `INC_CSS` dòng 46-117; thêm vào cuối chuỗi, trước `"""` đóng ở dòng 117)

**I1. Cỡ chữ và nút cho điện thoại** [CSS]
- Vấn đề: `.inc-fact-k` 11px (`:59`), `.inc-qhead` 11px (`:83`), `.inc-src` 10.5px (`:71`), `.inc-dd-btn` padding 5px 10px (~28px cao) (`:78`), `.inc-case-link` 12.5px không có vùng bấm, `.inc-link` padding 4px.
- Thay đổi (thêm cuối `INC_CSS`):
  ```css
  @media (max-width:768px) {
    .inc-wrap { max-width:100%; }
    .inc-panel, .inc-top { padding:12px; }
    .inc-fact-k, .inc-qhead, .inc-src { font-size:12px; }
    .inc-dd-btn { display:inline-flex; align-items:center; min-height:40px; padding:8px 14px; font-size:13px; }
    .inc-case-link { display:inline-flex; align-items:center; min-height:40px; font-size:13px; }
    .inc-link { padding:10px 0; font-size:13px; }
    .inc-case-grid { grid-template-columns:1fr; }
    .inc-id { font-size:15px; }
    .inc-card-v { font-size:18px; }
  }
  ```
- Kiểm tra: 375px, `/incident`: ba thẻ ca xếp 1 cột, link "Monitor/Workflow" bấm dễ; `/incident/{id}`: các nút Datadog cao ≥40px, không tràn ngang.

**I2. Bảng danh sách sự cố (6 cột) cuộn ngang trong khung** [PY nhỏ] — xem nhóm (c) mục C1.

**I3. Bảng "6 câu hỏi" (`.inc-qtable`) ở 761-1024px** [CSS]
- Vấn đề: lưới `minmax(150px,1fr) minmax(0,2.4fr) 130px 170px` = tối thiểu 450px cột cố định + 150; ở 768px (ngay trên 760px) cột giữa chỉ còn ~100px.
- Thay đổi: đổi ngưỡng media hiện có `@media (max-width:760px)` (`incident.py:89`) thành `@media (max-width:900px)` (sửa số duy nhất). Test `tests/` không so chuỗi CSS này (cần chạy test để chắc).
- Kiểm tra: 768px bảng chuyển 1 cột, không bị bóp; ≥1280 không đổi.

**I4. Biểu đồ trong `/incident/{id}`** — `incident.py:948-958` `ui.echart` đã `w-full`, cao 240px: giữ nguyên. Thêm trong media 768: `.inc-panel .echarts { min-height:220px; }` KHÔNG cần. Chỉ kiểm tra legend/trục không đè nhau ở 375px; nếu đè, đổi `"legend": {"bottom": 0, ...}` thêm `"type": "scroll"` (đổi dữ liệu tùy chọn, an toàn; nhưng `build_impact_chart_data` KHÔNG được đổi).

**Gói B — Trang chủ** (`pages/home.py`)

**H1. Lưới và thẻ trang chủ** [CSS]
- Hiện có: `.main-grid` 3 cột → 2 cột (≤1200, `home.py:413`) → 1 cột (≤768, `:476`). Đủ cho 768/375.
- Cần thêm (kiểm tra bằng trình duyệt trước, chỉ thêm nếu thấy tràn): `.flow-lines` (2 cột cố định, `home.py:331`) và `.weather-hourly` (3 cột, `home.py:364`) đặt `@media (max-width:480px){ .flow-lines{ grid-template-columns:1fr } .weather-hourly{ grid-template-columns:repeat(3,minmax(0,1fr)); font-size:12px } }`. Đọc đoạn 320-395 để xác nhận tên class và thuộc tính trước khi sửa.
- Thêm vô hiệu hover trên cảm ứng: `@media (hover:none){ .card:hover { transform:none } }` (tùy chọn, `home.py:216-218`).
- Kiểm tra: 375px không có thẻ nào rộng hơn màn; các nút bật/tắt (nếu có) cao ≥40px.

**Gói B — `/chart`** (`pages/chart.py`, `CHART_CSS` dòng 10-26)

**CH1.** [CSS] cuối `CHART_CSS` thêm:
```css
@media (max-width:768px){
  .dd-hub{ margin:12px 0 0; padding:16px 14px; border-radius:12px; }
  .dd-hub-title{ font-size:18px; }
  .dd-tile{ min-height:48px; padding:14px; }
  .dd-grid{ grid-template-columns:1fr; }
}
```
- Lý do: `.dd-hub` có `padding:26px 28px` và `margin:24px auto 0`, lãng phí chỗ ở 375px; `minmax(250px,1fr)` đã vừa nhưng ở 1 cột gọn hơn. `.dd-hint` 12px đạt.
- Kiểm tra: 375px ba thẻ xếp dọc, toàn bộ chữ đọc được, không cắt.

**Gói B — `/login`** (`pages/login.py`, `GLOBAL_CSS`)

**L1.** [CSS] sửa `.login-page` (`login.py:23-31`): `height:100vh;` thêm dòng `height:100dvh;` và `overflow-y:auto;` (đổi `overflow:hidden` thành `overflow-x:hidden; overflow-y:auto`). Thêm cuối `GLOBAL_CSS`:
```css
@media (max-width:480px){
  .login-card{ padding:24px 18px; border-radius:24px; }
  .title{ font-size:24px; }
}
```
- Vì `body{overflow:hidden}` (`login.py:19`) vẫn giữ, chỉ `.login-page` cuộn. Không đổi form hay nút.
- Kiểm tra: 375px×667 (màn thấp), thử thu nhỏ chiều cao còn 500px: vẫn cuộn tới nút Đăng nhập. Input giữ cao ≥40px (hiện 56px, đạt).

**Gói C — các trang còn lại** (làm sau Gói B)

**P1. `/permission`** [PY nhỏ + CSS]
- `permission.py:100-102` grid `1fr 2fr` inline. Thay bằng class: thêm `.perm-layout{display:grid;grid-template-columns:1fr 2fr;gap:24px;align-items:start}` và `@media (max-width:1024px){ .perm-layout{grid-template-columns:1fr; gap:16px} }` vào `PERM_CSS` (`permission.py:20-62`), rồi đổi `.style("display:grid;...")` thành `.classes("perm-layout")`. Tương tự grid `1fr 1fr` ở `:297`, `:354`, `:395`: thêm class `perm-grid2` + `@media (max-width:480px){ .perm-grid2{grid-template-columns:1fr} }` (khi inline style có `gap` khác nhau, giữ `gap` inline, chỉ chuyển `grid-template-columns` sang class, hoặc dùng `!important` trong media với selector thuộc tính: `@media(max-width:480px){ div[style*="grid-template-columns:1fr 1fr"]{grid-template-columns:1fr !important} }` — phương án KHÔNG sửa Python, được ưu tiên).
- Dialog: `permission.py:111` `width:380px` đổi thành `width:380px;max-width:92vw` (một chuỗi style).
- Kiểm tra: 768 và 375, danh sách user trên, form dưới, không cắt checkbox.

**P2. `/projects`** [CSS bằng selector thuộc tính, tránh sửa Python]
- Thêm vào `PROJECT_CSS` (`project.py:59`) cuối chuỗi:
  ```css
  @media (max-width:1024px){
    div[style*="repeat(5,1fr)"]{ grid-template-columns:repeat(2,minmax(0,1fr)) !important; }
    div[style*="grid-template-columns:repeat(4,1fr)"], div[style*="grid-template-columns:repeat(3,1fr)"]{ grid-template-columns:repeat(2,minmax(0,1fr)) !important; }
    div[style*="grid-template-columns:1.2fr 2fr"]{ grid-template-columns:1fr !important; }
  }
  @media (max-width:480px){
    div[style*="repeat(5,1fr)"], div[style*="repeat(4,1fr)"], div[style*="repeat(3,1fr)"], div[style*="repeat(2,1fr)"]{ grid-template-columns:1fr !important; }
    div[style*="1fr 1.2fr 0.7fr 0.5fr 1fr"]{ min-width:520px; }
  }
  ```
  Lưu ý chuỗi `repeat(N,1fr)` ở dòng 194 là f-string nên đầu ra là `repeat(3,1fr)` (không khoảng trắng); xác nhận bằng DevTools trước. Bảng "USER ONLINE STATUS" (`project.py:243-264`) bọc card: thêm class cuộn ngang (xem C2).
- Kiểm tra: 375px KPI 1 cột, thẻ dự án 1 cột, bảng user cuộn ngang trong card, trang không tràn.

**S1. `/schedule`** [PY nhỏ cho dialog]
- `schedule.py:177` `width:560px` → `width:560px;max-width:94vw`; `schedule.py:329` `width:400px` → `width:400px;max-width:94vw`. Hai ô `width:120px` (`:256,:260`) giữ nguyên (ô giờ), nhưng nếu nằm cùng hàng thì thêm `flex-wrap:wrap` trên hàng cha (đọc đoạn 245-265 trước).
- Lịch lưới `.schedule-grid` đã 1 cột ≤1200 (`schedule.py:430`). Thẻ lịch ngày `min-height:160px` (`:737`) có thể cao: ở ≤480 thêm trong `SCHEDULE_CSS` (f-string: dấu ngoặc nhân đôi) nếu thấy lưới 7 cột ngày quá chật.
- Biểu đồ `height:320px;width:100%` (`:763`) giữ.
- Kiểm tra: 375px mở dialog tạo/sửa lịch, nút Lưu/Hủy nhìn thấy đủ, bàn phím không che.

**D1. `/data`** — xem nhóm (c) mục C2 (bảng flow). Bộ lọc `ui.row` đã wrap. `xl:grid-cols-2` (`data_table.py:248`) giữ.

**M1. `/mongodb-lab`** [CSS]
- Thay `w-80` của select (`mongodb_lab.py:44`) bằng `w-80 max-w-full` (đổi class, PY 1 chỗ), `min-w-80` của biểu đồ (`:75,:85`) thành `min-w-[min(20rem,100%)]`; hoặc bỏ qua nếu 375px vừa (cột 375-24=351px > 320px nên VỪA). Kết luận: KHÔNG sửa, chỉ kiểm tra.

**V1. `/devices`**: lưới `minmax(240px,1fr)` + modal `max-width:95vw` đã đạt. Không sửa; chỉ kiểm tra nút trong thẻ ≥40px.
**PL1. `/plc`, `/inverter`**: không sửa trước hạn (phụ thuộc CDN React/Babel). Chỉ kiểm tra bằng mắt.

### Nhóm (c) Bảng rộng cuộn ngang trong khung — Gói A (C1) và Gói C (C2, C3)

Mẫu CSS dùng chung (đặt vào cuối `CUSTOM_CSS`, ngoài media, `home.py` trước dòng `"""` kết thúc ở 481):
```css
.tbl-scroll { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tbl-scroll > .q-table__container, .tbl-scroll > table { min-width: 640px; }
```
Giá trị 640px chỉ áp dụng cho bảng có nhiều cột. Quasar `q-table` thường đã có vùng cuộn riêng; nếu thấy cuộn đôi, bỏ `min-width` ngoài và dùng `.props("flat dense")`.

**C1. Bảng danh sách sự cố** [PY]
- `incident.py:774`: `table = ui.table(...).props("flat dense").style("width:100%")` → bọc: tạo `with ui.element("div").classes("tbl-scroll"):` quanh dòng 774 và các `add_slot`/`on` (dòng 774-778 chuyển vào trong khối `with`, thụt lề thêm 4 chữ cách) và đổi `.style("width:100%")` thành `.style("width:100%;min-width:560px")`.
- Rủi ro: thụt lề sai làm test import fail; chạy `unittest` ngay sau khi sửa.
- Kiểm tra: 375px bảng cuộn ngang trong khung, trang không cuộn ngang; nhấn một dòng vẫn vào `/incident/{id}`; ở 1280px hiển thị như cũ.

**C2. Bảng flow `/data`** [PY nhỏ]
- `data_table.py:395` `min-width: 800px;` có thể làm tràn `.content-area`; bọc `t_flow` (`:392-396`) trong `ui.element("div").classes("tbl-scroll")` hoặc, không đổi cấu trúc, thay CSS bằng `@media(max-width:1024px){ .flow-table{ min-width:640px !important } }` và thêm `.content-area{ overflow-x:auto }` trong media mobile (A4). Ưu tiên bọc `tbl-scroll`. Kiểm tra mục `add_online_slot(t_flow)` (`:396`) vẫn nằm đúng.
- Kiểm tra: 375px chỉ bảng cuộn ngang, bộ lọc ở trên cố định.

**C3. Bảng `/schedule`** (`schedule.py:573-580`): bọc tương tự C1, `min-width:560px`.

### Nhóm (d) Dialog cố định px

| Dialog | Vị trí | Sửa |
|---|---|---|
| Lịch (tạo/sửa) | `schedule.py:177` | `width:560px;max-width:94vw` |
| Lịch (xóa/xác nhận) | `schedule.py:329` | `width:400px;max-width:94vw` |
| Thêm user | `permission.py:111` | `width:380px;max-width:92vw` |
| Xác nhận user | `permission.py:412` | thêm `max-width:92vw` |
| Thiết bị | `devices.py:369-370` | đã có `max-width:95vw`, giữ |

Quasar dialog đã có `max-width` mặc định ~560px trên desktop nhưng khi dùng `ui.card()` có `width` inline thì tràn; vì vậy cần `max-width`. Kiểm tra: mở từng dialog ở 375px, 4 cạnh đều thấy trong màn.

### Nhóm (e) Biểu đồ

- `incident.py:948-958` (ECharts, cao 240px, `w-full`): giữ. Chỉ kiểm tra legend; tùy chọn `"legend": {"type": "scroll"}`.
- `mongodb_lab.py:69-97`: `min-w-80` vừa 375px; giữ, kiểm tra.
- `schedule.py:763-772`: khung 320px cao, rộng 100%: giữ.
- `/inverter` (Recharts) và `/chart` (không có biểu đồ): không đụng.
- Nếu ECharts không co khi xoay màn hình: NiceGUI đã gắn ResizeObserver; không thêm mã.

## 4. Tiêu chí hoàn thành theo breakpoint

| Tiêu chí | 375px | 768px | ≥1280px |
|---|---|---|---|
| Không tràn ngang trang (`document.documentElement.scrollWidth <= innerWidth`, và `.content-area.scrollWidth <= clientWidth` trừ khung cuộn ngang có chủ ý) | Bắt buộc | Bắt buộc | Bắt buộc |
| Điều hướng | Thanh đáy hiện icon + nhãn, vuốt được, mục active rõ, không che nội dung cuối trang | Thanh đáy (≤768) hoặc sidebar (>768), cùng chuẩn | Sidebar 200px như cũ, KHÔNG đổi |
| Vùng bấm | Nút, link, mục nav ≥ 40px chiều cao | ≥ 40px | Giữ nguyên |
| Cỡ chữ nội dung | ≥ 12px (nhãn nav ≥ 11px chấp nhận) | ≥ 12px | Giữ nguyên |
| Không cắt nội dung | Dialog, menu, bảng, topbar thấy đủ; bảng rộng cuộn ngang trong khung | Như vậy | Như cũ |
| Chức năng | Đăng nhập, mở sự cố, bấm ca, mở link Datadog, đổi farm, chuông, đăng xuất đều dùng được | Như vậy | Như cũ |
| Test | 168 test qua | | |

## 5. Cách kiểm tra khi chưa chạy được app đầy đủ

1. **Test CSS nhỏ (tự động)** — thêm file `tests/test_responsive_css.py` (file MỚI duy nhất ngoài mã giao diện; không import hàm cần Mongo):
   ```python
   import unittest
   from pages.home import CUSTOM_CSS
   from pages.incident import INC_CSS
   from pages.chart import CHART_CSS

   class ResponsiveCssTest(unittest.TestCase):
       def test_mobile_resets_padding(self):
           block = CUSTOM_CSS.split("@media (max-width: 768px)")[-1]
           self.assertIn("padding-left: 0", block)
       def test_sidebar_hide_selector_is_direct_child(self):
           self.assertIn(".sidebar > div:last-child", CUSTOM_CSS)
           self.assertNotIn(".sidebar div:last-child", CUSTOM_CSS)
       def test_topbar_wraps_on_mobile(self):
           self.assertIn("flex-wrap: wrap", CUSTOM_CSS)
       def test_incident_has_mobile_media(self):
           self.assertIn("@media (max-width:768px)", INC_CSS)
       def test_chart_has_mobile_media(self):
           self.assertIn("@media (max-width:768px)", CHART_CSS)
   ```
   Chạy bằng `python -X utf8 -m unittest tests.test_responsive_css`. Lưu ý: import `pages.home` có thể kéo theo module khác; nếu import fail trong môi trường test thì đọc file bằng `Path.read_text()` và kiểm tra chuỗi thay vì import.
2. **Kiểm tra cú pháp**: `python -X utf8 -c "import pages.home, pages.incident, pages.chart, pages.login"` (chỉ import) sau mỗi nhóm.
3. **Người dùng tự kiểm tra trước khi nộp** (Chrome/Edge, `F12` > bật Device Toolbar Ctrl+Shift+M):
   - Đặt 375×812 rồi 768×1024 rồi cửa sổ thường 1366×768.
   - Mỗi trang: `/login`, `/`, `/chart`, `/incident`, một `/incident/{id}` (ca 1, 2, 3), rồi `/schedule`, `/data`, `/permission`, `/projects`.
   - Quan sát: thanh đáy có nhãn; không thanh cuộn ngang cấp trang; topbar không cắt; mở thử dialog ở `/schedule` và `/permission`; xoay ngang.
   - Chạy trong Console: `document.documentElement.scrollWidth - innerWidth` phải ≤ 0.
   - Có thể chạy demo: `py -3.12 -X utf8 main.py` (cần MongoDB và Mosquitto; `SMIOT_DEMO_MODE=true` đã tự nạp dữ liệu). Nếu thiếu MongoDB, chỉ `/login` và vài trang tĩnh xem được; `/incident` sẽ báo lỗi đọc DB nhưng vẫn kiểm tra được khung.
   - Nếu có điện thoại thật cùng mạng LAN: mở `http://<IP máy>:8080`.

## 6. Rủi ro, cách lùi lại, và những gì KHÔNG nên đụng

Rủi ro:
- Sửa `CUSTOM_CSS` ảnh hưởng mọi trang. Giảm thiểu: chỉ thêm trong `@media (max-width: 768px)`, không sửa quy tắc desktop.
- Selector thuộc tính `div[style*="..."]` (P2, P1) phụ thuộc chuỗi inline: nếu đổi chuỗi sẽ không còn khớp (hỏng nhẹ, không gãy).
- Sửa thụt lề Python (C1, C2) có thể gây SyntaxError: chạy import + unittest ngay.
- `100dvh` ở trình duyệt cũ: có dòng `100vh` đứng trước làm dự phòng.
- Menu/thanh đáy cuộn ngang có thể gây trượt nhầm: kiểm tra trên thiết bị thật nếu có.

Lùi lại:
- Mỗi mục = một commit (`git commit -m "resp: A1 reset padding-left mobile"`). Lùi: `git revert <hash>`.
- Trước khi bắt đầu mỗi gói: `git tag resp-before-A` (và B, C). Lùi nguyên gói: `git reset --hard resp-before-A` CHỈ khi chắc chắn không còn thay đổi chưa commit khác (tốt hơn: `git revert` từng commit).
- Hạn nộp gấp: nếu một gói chưa xong/chưa ổn trước 20:00 ngày 08/11, lùi về tag gần nhất đã ổn và nộp bản đó.

KHÔNG đụng trước hạn nộp:
- Toàn bộ logic Python ngoài thay đổi class/style nêu trên: `core/`, `main.py`, MQTT, Mongo, AI, quyền, hàm tính toán trong `pages/incident.py` (xem danh sách quy tắc 1).
- `/inverter` và `/plc` (React/Babel/CDN), `static/test_inverter.html`.
- `/lot/{token}` (đã đạt).
- Cấu trúc sidebar thành "hamburger drawer" (thay đổi lớn; thanh đáy cuộn ngang đủ dùng).
- Thay font, đổi màu, đổi bố cục desktop, nâng cấp NiceGUI/Quasar, đổi `requirements.txt`.
- `.env` và khóa API.

## 7. Ba gói việc tuần tự

**Gói A (khung chung + /incident)** — làm đầu tiên, ~1,5-2 giờ
1. B1 xác nhận bằng trình duyệt (15 phút). 2. A1, A2, A3, A4, A5 (chỉ `home.py`). 3. I1, I3, C1 (`incident.py`). 4. Thêm test CSS (mục 5.1). 5. unittest (168 + test mới), tự kiểm tra `/incident`, `/incident/{id}` ở 375/768/1280. 6. Commit + tag `resp-after-A`.
Dừng, kiểm tra tay trước khi sang Gói B.

**Gói B (trang chủ, /chart, /login)** — ~1 giờ
1. H1 (chỉ thêm nếu thấy lỗi), A6 (nếu cần). 2. CH1. 3. L1. 4. unittest + kiểm tra tay ba trang ở 375/768/1280. 5. Commit + tag `resp-after-B`.

**Gói C (các trang còn lại)** — chỉ làm nếu còn thời gian, mỗi trang một commit
Thứ tự: S1 + dialog schedule (d) → C2 (`/data`) → P1 (`/permission`) → P2 (`/projects`) → C3. Bỏ qua M1, V1, PL1 (chỉ kiểm tra). unittest sau mỗi trang. Tag `resp-after-C`.

Gói A là mức tối thiểu phải xong; Gói B nên xong; Gói C tùy thời gian.
