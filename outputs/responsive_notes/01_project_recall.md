# SMIOT — ghi nhớ dự án để làm giao diện responsive

Ngày khảo sát: 2026-11-07. Chỉ đọc mã, không sửa file nào khác. Không đọc `.env`. Đường dẫn dạng `file:dòng` tương đối với `D:\IOT Trung\code_full_server`.

## Tóm tắt 10 dòng

1. App là NiceGUI 3.17.1 (Python 3.12, `requirements.txt` không ghim phiên bản), chạy `main.py` ở cổng 8080.
2. Khung chung gồm `CUSTOM_CSS` (`pages/home.py:16-481`), `sidebar` (`home.py:731`) và `global_topbar` (`home.py:562`); hầu hết trang gọi `ui.add_head_html(...)` rồi dựng `.sidebar` + `.main-content` + `.content-area`.
3. Viewport đã có sẵn: NiceGUI mặc định `width=device-width, initial-scale=1` (`nicegui/ui_run.py:54`), `main.py` không ghi đè. Không cần thêm meta.
4. Sidebar cố định 200px trên desktop; dưới 768px chuyển thành thanh điều hướng đáy có tới 11 mục (8 mục cho người thường, thêm 3 cho admin). Topbar không `flex-wrap`, dễ tràn ở 375px.
5. Nghi ngờ lỗi: ở `@media (max-width:768px)` chỉ đặt `margin-left:0` mà không reset `padding-left:200px` của `.main-content` (`home.py:124-127` và `home.py:424-428`), nên nội dung có thể chỉ còn khoảng 175px. Cần xác nhận trên trình duyệt.
6. Breakpoint có sẵn: 1200px (home, schedule), 768px (home, plc dùng min-width), 760px (incident), 640px (public_lot), và Tailwind `md/lg/xl` ở data, mongodb-lab, inverter.
7. Trang nguy cơ cao nhất: `/permission` (grid `1fr 2fr` không có media), `/projects` (KPI `repeat(5,1fr)`, bảng 5 cột cố định), `/data` (bảng flow `min-width:800px`), `/schedule` (dialog 560px/400px cố định).
8. `/lot/{token}` đã là mobile-first và là trang an toàn nhất; `/login` và `/chart` ổn ở mức phổ thông.
9. Test: 168 hàm `test_` trong `tests/`, chạy bằng `$env:PYTHONPATH=(Get-Location).Path; python -X utf8 -m unittest discover -s tests`. Test import trực tiếp nhiều tên trong `pages/incident.py`, và `tests/test_healthz.py` đọc AST của `main.py` để lấy `build_healthz_payload`, `_read_mongo_health`, `HEALTHZ_MONGO_TIMEOUT_SECONDS`.
10. Chạy thử: `py -3.12 -X utf8 main.py` rồi mở `http://localhost:8080`; cần MongoDB và Mosquitto (README:170-176); `SMIOT_DEMO_MODE=true` mặc định tự nạp dữ liệu demo.

## 1. Danh sách trang và route

| Trang | Route | Đăng nhập | Nguồn |
|---|---|---|---|
| Smart Monitoring (trang chủ) | `/` | Có (`check_login`) | `pages/home.py:1344-1346` |
| Đăng nhập | `/login` | Công khai | `pages/login.py:202-208` |
| Thiết bị | `/devices` | Có | `pages/devices.py:458-460` |
| Projects | `/projects` | Có (route không kiểm tra admin; sidebar chỉ hiện cho admin) | `pages/project.py:111-113`, `home.py:744-745` |
| Inverter | `/inverter` | Có | `pages/inverter.py:30-32` |
| PLC | `/plc` | Có, quyền theo từng nút | `pages/plc.py:7-9`, `plc.py:66` |
| Schedule | `/schedule` | Có, quyền `manage_schedule` / `export_schedule_logs` | `pages/schedule.py:147-150`, `schedule.py:441-442` |
| Chart (hub chỉ dẫn sang Datadog) | `/chart` | Có | `pages/chart.py:43-45` |
| Chart (redirect) | `/history` | Không kiểm tra, chỉ chuyển sang `/chart` | `chart.py:38-40` |
| Dữ liệu thô | `/data` | Có | `pages/data_table.py:10-12` |
| Mùa vụ & truy xuất | `/mongodb-lab` | Có | `pages/mongodb_lab.py:17-20` |
| Traceability (redirect) | `/traceability` → `/mongodb-lab` | Không kiểm tra | `pages/traceability.py:6-8` |
| Permission | `/permission` | Có + (admin hoặc `manage_users`) | `pages/permission.py:73-83` |
| Incident (danh sách) | `/incident` | Có + admin (`_guard`) | `pages/incident.py:725-727`, `incident.py:138-145` |
| Incident (chi tiết) | `/incident/{incident_id}` | Như trên | `pages/incident.py:787-790` |
| Trang khách hàng theo lô | `/lot/{token}` | Công khai (theo token) | `pages/public_lot.py:8-18` |
| Health | `/healthz` | Công khai | `main.py:182` |

Ngoài ra `main.py:119` có `/api/js_error` và `main.py:194` có endpoint nội bộ của recovery (dùng bearer token).

## 2. Cách giao diện được dựng chung

- **CSS toàn cục**: `CUSTOM_CSS` ở `pages/home.py:16-481`, có `@import` Google Fonts (Inter) và remixicon từ jsdelivr (`home.py:17-18`). Mỗi trang nối thêm CSS riêng, ví dụ `INC_CSS` (`incident.py:46`), `CHART_CSS` (`chart.py:10`), `SCHEDULE_CSS` (`schedule.py:16`), `PERM_CSS` (`permission.py:20`), `PROJECT_CSS` (`project.py:59`), `CARD_CSS` (`devices.py:276`).
- **html/body**: `overflow:hidden` và `height:100%` (`home.py:22-30`). Cuộn chỉ xảy ra trong `.content-area` (`home.py:149-155`, `overflow-y:auto`). Do `overflow-y` không phải `visible`, `overflow-x` của `.content-area` sẽ thành `auto`, nên bảng rộng sẽ cuộn ngang bên trong khung đó, không cuộn cả trang.
- **Sidebar**: `position:fixed; width:200px; min-height:100vh` (`home.py:59-68`). Dựng ở `home.py:762-785`, gồm logo, các mục `<a href>` và footer.
- **Vùng nội dung**: `.main-content` có `padding-left:200px; height:100vh; display:flex; column` (`home.py:124-134`).
- **Topbar**: `.top-bar` là flex, `justify-content:space-between`, không có `flex-wrap` (`home.py:136-142`). Trong code có dropdown farm `width:150px` (`home.py:610`), nhãn DEMO, chuông thông báo, avatar và tên người dùng (`home.py:589-729`). Dựng ở `home.py:589`.
- **Viewport**: có sẵn do NiceGUI tự chèn. `pages/public_lot.py:20` tự thêm meta (trùng lặp, vô hại).
- **Tailwind**: NiceGUI 3.17.1 có file `tailwindcss.min.js` trong `site-packages\nicegui\static`, nên các class Tailwind (`md:`, `lg:`, `xl:`, `min-w-80`, `flex-wrap`) hoạt động. `plc.py:129` và `inverter.py:224` còn tải thêm `cdn.tailwindcss.com` từ CDN.
- **CDN ngoài**: React/Babel/prop-types từ unpkg (`plc.py:126-128`, `inverter.py:221-225`), Recharts từ cdnjs (`inverter.py:226`), Google Fonts (`login.py:10`, `plc.py:130`). Nếu mạng chậm hoặc offline thì style và trang React sẽ lỗi.
- **Chiều rộng cố định (px)**:
  - sidebar 200px (`home.py:60`)
  - padding vùng nội dung 200px (`home.py:125`)
  - dropdown farm 150px (`home.py:610`)
  - login card 420px, `max-width:92%` (`login.py:48-49`)
  - `.inc-wrap` 1280px (`incident.py:47`)
  - `.dd-hub` 980px (`chart.py:11`)
  - `.device-grid` tối đa 1200px (`devices.py:281`)
  - modal thiết bị 820px, `max-width:95vw` (`devices.py:370`)
  - dialog lịch 560px (`schedule.py:177`) và 400px (`schedule.py:329`), cố định, không có max-width
  - dialog phân quyền 380px (`permission.py:111`)
  - ECharts `h-72` và `min-w-80` (320px) (`mongodb_lab.py:75,85`)
  - ECharts `h-64` (`mongodb_lab.py:97`)
  - khung biểu đồ lịch `height:320px` (`schedule.py:763`)
  - bảng flow `min-width:800px` (`data_table.py:395`)
  - cột bảng incident cố định `150px + 2.4fr + 130px + 170px` (`incident.py:81`)
- **ECharts**: không đặt chiều rộng cứng. Chúng dùng `width:100%` hoặc `flex-1` trong `ui.echart` ở `mongodb_lab.py:69,82,94`, `incident.py:948` và `schedule.py:772`. Trang chủ không dùng ECharts.
- **Bảng**: dùng `ui.table` của Quasar ở `data_table.py:256-392` (5 bảng, `pagination rowsPerPage:20`, `max-height:500px`), `incident.py:774` (6 cột, `LIST_COLUMNS` tại `incident.py:695-702`) và `schedule.py:580`. Không có bảng nào tự ẩn cột trên màn hình nhỏ.

## 3. Các `@media` và breakpoint hiện có

| Vị trí | Điều kiện | Tác dụng |
|---|---|---|
| `home.py:413` | `max-width:1200px` | `.main-grid` 2 cột, `.sub-grid` 1 cột |
| `home.py:424` | `max-width:768px` | Sidebar thành thanh đáy 60px, nav `flex:1`, font 10px, ẩn logo và footer (`home.py:448` dùng `.sidebar div:last-child`), `.main-content` `margin-left:0; padding-bottom:80px`, `.main-grid` 1 cột |
| `incident.py:89` | `max-width:760px` | `.inc-qtable` 1 cột, ẩn `.inc-qhead` |
| `schedule.py:430` | `max-width:1200px` | `.schedule-grid` 1 cột (mặc định `1.5fr 1fr`, `schedule.py:405-411`) |
| `plc.py:157` | `min-width:768px` | `.pump-control-grid` 2 cột, thẻ thứ 7 chiếm cả hàng (mobile-first: 1 cột) |
| `public_lot.py:22` | `max-width:640px` | `.lot-image` cao 230px thay vì 280px |
| `chart.py:25` | `prefers-reduced-motion` | Tắt hiệu ứng |

Breakpoint Tailwind đang dùng: `data_table.py:248` (`xl:grid-cols-2`), `public_lot.py:23` (`md:p-8`), `static/test_inverter.html:193` (`lg:grid-cols-12`) và `:496` (`md:grid-cols-4`).

Không có media query nào ở `login.py`, `devices.py`, `permission.py`, `project.py`, `data_table.py` (ngoài Tailwind) hay `mongodb_lab.py` (chỉ Tailwind). Các trang này chỉ dựa vào `auto-fit`/`minmax` hoặc cột cố định.

Lưới co giãn tự động đã có: `incident.py:58,86,90`, `chart.py:14`, `public_lot.py:39`, `mongodb_lab.py:121`, `devices.py:279` (`minmax(240px,1fr)`).

## 4. Ước lượng độ dễ vỡ theo trang (màn hình hẹp)

**Chung (áp dụng cho mọi trang có sidebar):**
- Thanh đáy ở ≤768px có tối đa 11 mục (`home.py:739-760`: Home, Device, Inverter, PLC, Schedule, Chart, Data, Mùa vụ, cộng Projects, Incident, Permission cho admin). Mỗi mục rộng khoảng 34px khi có 11 mục, nhãn 10px như "Mùa vụ & truy xuất" sẽ xuống nhiều dòng.
- `padding-left:200px` còn nguyên trên mobile (nghi ngờ đã nêu ở mục 5).
- `height:100vh` trên iOS Safari bị tính theo thanh địa chỉ. Có thể cân nhắc `100dvh` (cần kiểm tra thêm).
- Topbar không wrap: ở 375px, title + select 150px + nhãn DEMO + badge ACTIVE + chuông + avatar/tên có khả năng tràn.
- Hover `translateY(-6px)` trên card (`home.py:216-218`) vô nghĩa trên cảm ứng nhưng không gây vỡ.

**Từng trang:**
- **`/` (trang chủ)**: grid 3 cột → 2 cột (1200px) → 1 cột (768px) (`home.py:397-422`). Có các thẻ thời tiết, cảm biến, AI, `.flow-lines` 2 cột cố định (`home.py:331`), `.weather-hourly` 3 cột (`home.py:364`). Menu chuông `w-80` (320px) neo phải dễ bị lệch trái khỏi màn hình (`home.py:673`).
- **`/login`**: ổn. Card 420px với `max-width:92%`, input cao 56px, `.login-page` cao `100vh` (`login.py:23-26`).
- **`/devices`**: lưới `minmax(240px,1fr)` (`devices.py:279`) co tốt. Modal 820px có `max-width:95vw` (`devices.py:370`). Không có vấn đề lớn.
- **`/projects`** (rủi ro cao): KPI `repeat(5,1fr)` (`project.py:180`), thẻ nhiều cột `repeat(num_cols,1fr)` tối đa 4 cột (`project.py:193-194`), bảng `1fr 1.2fr 0.7fr 0.5fr 1fr` (`project.py:243,250`), chữ không có `min-width:0`. Trên 375px sẽ rất chật, không có media nào.
- **`/inverter`** (rủi ro trung bình): React + Babel + Recharts. Layout nằm trong `static/test_inverter.html` và được nạp bằng regex (`inverter.py:308-313`). Bố cục dùng Tailwind `lg:grid-cols-12` (`test_inverter.html:193`) nên phần lớn ổn ở mobile. Biểu đồ Recharts cần chiều rộng co giãn, nên cần kiểm tra. Nếu CDN lỗi thì trang trắng.
- **`/plc`** (rủi ro thấp đến trung bình): mobile-first (1 cột, 2 cột từ 768px, `plc.py:151-167`). Nút điều khiển bơm và thẻ có thể cần kiểm tra kích thước chạm. Phụ thuộc React/Tailwind CDN.
- **`/schedule`** (rủi ro trung bình đến cao): `.schedule-grid` co 1 cột ở 1200px (`schedule.py:405-433`). Hai dialog có width cố định 560px và 400px (`schedule.py:177, 329`), có thể tràn ở 375px. Bảng `ui.table` ở `schedule.py:573-580` nhiều cột. Khung biểu đồ `height:320px` (`schedule.py:763`).
- **`/chart`** (rủi ro thấp): chỉ là hub gồm 3 thẻ; `.dd-grid` là `auto-fit minmax(250px)` (`chart.py:14`), `.dd-hub` có `max-width:980px`.
- **`/data`** (rủi ro cao ở bảng flow): filter `ui.row` (`data_table.py:51`) có wrap mặc định (NiceGUI `Row` mặc định `wrap=True`). Lưới 2 bảng cột ở `xl` (`data_table.py:248`), còn lại 1 cột. Bảng flow có `min-width:800px` (`data_table.py:395`), sẽ cuộn ngang trong `.content-area`. Năm bảng đều `max-height:500px`.
- **`/mongodb-lab`** (rủi ro thấp đến trung bình): hàng thẻ `flex-1 min-w-44` và biểu đồ `flex-1 min-w-80` có `flex-wrap` (`mongodb_lab.py:54, 61, 66, 75, 85`). Select lô `w-80` (320px, `mongodb_lab.py:44`). Ảnh giai đoạn `grid auto-fit minmax(210px)` (`mongodb_lab.py:121`), ảnh `h-64`. Mã QR `w-36 h-36` (`mongodb_lab.py:107`).
- **`/permission`** (rủi ro cao): `grid-template-columns:1fr 2fr` (`permission.py:101`) không có media, nên danh sách người dùng và chi tiết bị ép thành 2 cột trên phone. Các form `1fr 1fr` (`permission.py:297, 354, 395`). Dialog 380px (`permission.py:111`).
- **`/incident`** (rủi ro trung bình): bảng 6 cột (`incident.py:695-702`) không ẩn cột. Lưới case `minmax(260px)` (`incident.py:90`) vừa với 335px. `.inc-facts` `minmax(200px)` (`incident.py:58`) và `.inc-qtable` đã có media ở 760px. Link Datadog có `word-break:break-all` (`incident.py:49-50`), tốt. Biểu đồ ECharts (`incident.py:948`) có grid 3%/4%, ổn.
- **`/incident/{id}`**: cùng bộ CSS. Khung `holder` `width:100%` (`incident.py:797`). Dải chi tiết dùng `.inc-dd-row` có `flex-wrap` (`incident.py:77`). Ổn.
- **`/lot/{token}`** (rủi ro thấp nhất): đã có viewport, `max-w-6xl`, `p-4 md:p-8`, lưới `auto-fit minmax(220px)`, ảnh 280/230px ở ≤640px (`public_lot.py:20-39`). Trang này không có sidebar hay topbar.

## 5. Cách chạy ứng dụng và kiểm tra

- Cài thư viện: `py -3.12 -m pip install -r requirements.txt` (README:164-166).
- Chạy: `py -3.12 -X utf8 main.py`, mở `http://localhost:8080` (README:173-176; cổng cố định ở `main.py:268`).
- Trước khi chạy cần có MongoDB (Atlas hoặc local, cho phép IP) và Mosquitto (README:170). Có thể đổi `SMIOT_DEMO_MODE` và `SMIOT_DEMO_INTERVAL_SECONDS` (README:180, 193). Không đọc `.env` khi làm việc này.
- Xem trước responsive trong Browser pane: `resize_window` với preset `mobile` (375x812) hoặc `tablet` (768x1024), rồi đặt lại `desktop`. Có thể dùng `preview_start` khi có `launch.json`.
- Test: `$env:PYTHONPATH=(Get-Location).Path; python -X utf8 -m unittest discover -s tests` (168 hàm `test_`, theo đếm trong `tests/`).

## 6. Ràng buộc cần giữ

- Không đổi chức năng, route, quyền truy cập (`check_login`, `_guard`, `check_permission`) hay redirect (`/history`, `/traceability`).
- Test import trực tiếp từ `pages/incident.py`: `_link_groups`, `build_impact_chart_data`, `METRIC_WINDOW_PAD`, `metric_links`, `metric_window`, `RECOVERY_GENERIC`, `_first_trace_link`, `_trace_links`, `build_six_questions`, `format_recovery_evidence`, `STATE_DONE`, `STATE_OPEN`, `build_list_rows`, `case_runs`, `case_summary_text`, `format_duration`, `run_state`, `scope_label`, `incident_headline`, `incident_summary`, `mongo_only_events`, `SRC_DATADOG`, `SRC_MONGO`. Không được đổi tên các hàm này.
- `tests/test_incident_navigation.py:52-55` yêu cầu module `pages.incident` KHÔNG có `pick_bits_link`, `BITS_LIST_URL`, `BITS_NO_INVESTIGATION_NOTE`.
- `tests/test_healthz.py:18` đọc AST của `main.py` để lấy `build_healthz_payload`, `_read_mongo_health`, `HEALTHZ_MONGO_TIMEOUT_SECONDS`. Các tên này phải còn trong `main.py` ở cấp module.
- `pages/home.py` không được import lại `pages.incident` (tránh vòng import; `chart.py:4` đã import `DD_BASE` từ incident).
- Không thêm thư viện mới. Có thể dùng Tailwind (đã bundle trong NiceGUI) hoặc CSS thuần trong `add_head_html`.
- Nếu đổi CSS dùng chung trong `CUSTOM_CSS`, các trang khác (`devices`, `plc`, `schedule`, `incident`, `permission`, `project`, `data_table`, `mongodb_lab`) sẽ bị ảnh hưởng. Nên đặt CSS responsive riêng theo trang, hoặc thêm media query vào cuối `CUSTOM_CSS` có kiểm tra từng trang.
- Chưa kiểm tra bằng trình duyệt: mọi nhận định về tràn ngang và dialog đều dựa trên đọc mã. Cần xác nhận trước khi sửa.
