from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path

ROOT = Path(r"D:\IOT Trung\code_full_server\outputs\20261104_smiot_story_pack")
E = ROOT / "evidence"
OUT1 = ROOT / "Bao_cao_cau_chuyen_MongoDB_Datadog.docx"
OUT2 = ROOT / "Kich_ban_demo_Datadog_theo_bang_chung.docx"

NAVY="15324B"; TEAL="137C8B"; BLUE="DCEEF2"; LIGHT="F3F6F8"; DARK="263746"; GRAY="5B6770"; WHITE="FFFFFF"

def shade(cell, fill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),fill); tcPr.append(shd)
def set_cell_text(cell, text, bold=False, color=DARK, size=9):
    cell.text=""
    p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(2)
    r=p.add_run(str(text)); r.bold=bold; r.font.name="Aptos"; r.font.size=Pt(size); r.font.color.rgb=RGBColor.from_string(color)
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
def add_hyperlink(paragraph, text, url):
    part=paragraph.part; r_id=part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    hyperlink=OxmlElement('w:hyperlink'); hyperlink.set(qn('r:id'),r_id)
    new=OxmlElement('w:r'); props=OxmlElement('w:rPr')
    c=OxmlElement('w:color'); c.set(qn('w:val'),'0563C1'); props.append(c)
    u=OxmlElement('w:u'); u.set(qn('w:val'),'single'); props.append(u)
    new.append(props); t=OxmlElement('w:t'); t.text=text; new.append(t); hyperlink.append(new); paragraph._p.append(hyperlink)
def setup(doc, title):
    sec=doc.sections[0]; sec.top_margin=Inches(.72); sec.bottom_margin=Inches(.7); sec.left_margin=Inches(.78); sec.right_margin=Inches(.78)
    normal=doc.styles['Normal']; normal.font.name='Aptos'; normal.font.size=Pt(10.5); normal.font.color.rgb=RGBColor.from_string(DARK)
    normal.paragraph_format.space_after=Pt(6); normal.paragraph_format.line_spacing=1.12
    for name,size,col in [('Title',28,NAVY),('Heading 1',18,NAVY),('Heading 2',13,TEAL),('Heading 3',11,DARK)]:
        st=doc.styles[name]; st.font.name='Aptos Display' if name!='Heading 3' else 'Aptos'; st.font.size=Pt(size); st.font.bold=True; st.font.color.rgb=RGBColor.from_string(col)
    header=sec.header.paragraphs[0]; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    rr=header.add_run("SMIOT  |  HỒ SƠ DỰ ÁN"); rr.font.name="Aptos"; rr.font.size=Pt(8); rr.font.color.rgb=RGBColor.from_string(GRAY)
    footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    fr=footer.add_run(title+"  ·  "); fr.font.size=Pt(8); fr.font.color.rgb=RGBColor.from_string(GRAY)
    fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
def cover(doc, eyebrow, title, subtitle):
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(80); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(eyebrow.upper()); r.bold=True; r.font.size=Pt(11); r.font.color.rgb=RGBColor.from_string(TEAL)
    p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(10); p.add_run(title)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(6)
    r=p.add_run(subtitle); r.font.size=Pt(13); r.font.color.rgb=RGBColor.from_string(GRAY)
    doc.add_paragraph()
    t=doc.add_table(rows=1,cols=1); t.alignment=WD_TABLE_ALIGNMENT.CENTER
    c=t.cell(0,0); shade(c,BLUE); set_cell_text(c,"Thông điệp cốt lõi: biến dữ liệu cảm biến thành quyết định canh tác có căn cứ; khi hệ thống gặp lỗi, nối phát hiện → điều tra → xử lý an toàn → xác nhận bằng dữ liệu.",True,NAVY,11)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(55)
    rr=p.add_run("Tài liệu làm việc · 04/11/2026 · AWS ap-southeast-2 · Datadog US1"); rr.font.size=Pt(9); rr.font.color.rgb=RGBColor.from_string(GRAY)
    doc.add_page_break()
def bullet(doc, text):
    p=doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after=Pt(3); p.add_run(text); return p
def numbered(doc, text):
    p=doc.add_paragraph(style='List Number'); p.paragraph_format.space_after=Pt(3); p.add_run(text); return p
def table(doc, headers, rows, widths=None, font=8.5):
    t=doc.add_table(rows=1, cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    for i,h in enumerate(headers): shade(t.rows[0].cells[i],NAVY); set_cell_text(t.rows[0].cells[i],h,True,WHITE,9)
    for row in rows:
        cells=t.add_row().cells
        for i,val in enumerate(row):
            if len(t.rows)%2==0: shade(cells[i],LIGHT)
            set_cell_text(cells[i],val,False,DARK,font)
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t
def pic(doc, name, caption, width=6.8):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(3); p.paragraph_format.space_after=Pt(2)
    p.add_run().add_picture(str(E/name),width=Inches(width))
    cp=doc.add_paragraph(); cp.alignment=WD_ALIGN_PARAGRAPH.CENTER; cp.paragraph_format.space_after=Pt(8)
    rr=cp.add_run(caption); rr.italic=True; rr.font.size=Pt(8.5); rr.font.color.rgb=RGBColor.from_string(GRAY)

# Report
d=Document(); setup(d,"Báo cáo câu chuyện MongoDB và Datadog")
cover(d,"Báo cáo thiết kế & giá trị","Từ dữ liệu vườn đến vận hành có bằng chứng","Vì sao MongoDB và Datadog phù hợp với SMIOT, và được dùng sâu như thế nào")
d.add_heading("Tóm tắt điều hành",1)
d.add_paragraph("SMIOT kết hợp hai câu chuyện có quan hệ nhưng được trình diễn thành hai ca riêng. MongoDB biến telemetry theo thời gian thành dữ liệu có thể kiểm tra chất lượng và dùng để tính tổng nhiệt hữu hiệu (GDD) cho dưa lưới. Datadog giúp đội vận hành nhận ra một luồng cảm biến bị đứng hoặc ứng dụng web trên EC2 ngừng hoạt động, lần theo tín hiệu và chỉ chạy hành động phù hợp với bằng chứng.")
table(d,["Câu chuyện","Câu hỏi vận hành","Kết quả có thể chỉ ra"],[
["MongoDB · kế hoạch thu hoạch","Dữ liệu có đủ mới, đủ đều và đủ tin cậy để tính GDD không?","Time Series, aggregation, window function, chất lượng dữ liệu, raw-vs-rollup và khôi phục snapshot."],
["Datadog · Node 2","Một node vẫn gửi dữ liệu nhưng số đo độ ẩm không đổi: có phải mất kết nối không, và hệ thống có giữ an toàn không?","Monitor, incident context, logs/APM, Bits investigation, HOLD ảo và xác minh phục hồi."],
["Datadog · EC2","Ứng dụng ngừng phục vụ trong khi MongoDB/MQTT còn khỏe: có cần khởi động lại cả máy chủ không?","Monitor → workflow → chỉ start dịch vụ ứng dụng → HTTP 200 và telemetry Mongo mới."]
], [1.35,2.55,3.0],8.5)
d.add_heading("Luận điểm kinh doanh",2)
bullet(d,"Không để dữ liệu thiếu âm thầm làm sai ước tính phát triển dưa: phép tính GDD đi kèm độ đầy đủ và khoảng trống lấy mẫu.")
bullet(d,"Không phản ứng quá mức khi web lỗi: ca EC2 chứng minh chỉ khởi động dịch vụ ứng dụng sau pre-check, thay vì restart cả máy hoặc database.")
bullet(d,"Không tuyên bố cảm biến thật hỏng: ca Node 2 là flatline được đưa vào nguồn dữ liệu mô phỏng; bằng chứng chỉ hỗ trợ kết luận luồng số bị giữ giá trị và hệ thống xử lý an toàn.")
d.add_heading("Bối cảnh triển khai",1)
d.add_paragraph("Ứng dụng SMIOT chạy trên EC2 tại ap-southeast-2. MongoDB Community 8.0.34 trên cùng máy là cơ sở dữ liệu vận hành; MQTT/Mosquitto, bridge nguồn dữ liệu, ứng dụng, Datadog Agent và Nginx cũng nằm trong môi trường đó. Datadog dùng US1. Thiết kế gọn cho một demo nhưng có rủi ro chung failure domain: nếu EC2 hoặc ổ đĩa lỗi, app và MongoDB có thể cùng bị ảnh hưởng.")
d.add_paragraph("Nguồn telemetry dùng publisher synthetic chạy trên cloud; nó cho phép diễn tập có thể lặp lại và đo được. Đây là mô phỏng luồng cảm biến, không phải số đo từ đầu dò hay bơm vật lý.")
d.add_page_break()
d.add_heading("1. MongoDB làm nổi bật bài toán dưa lưới",1)
d.add_heading("Từ mẫu cảm biến tới tổng nhiệt",2)
d.add_paragraph("Mỗi mẫu có thời gian đo, farm, node và các trị số môi trường. Time Series collection phù hợp với nhịp ghi liên tục vì MongoDB tổ chức dữ liệu theo timeField và nhóm metadata ổn định. Trong SMIOT, farm/node/source là các chiều lọc vận hành; những thông tin thường thay đổi theo phép đo nằm ở phần readings.")
d.add_paragraph("Aggregation xử lý gần nơi dữ liệu đang lưu: lọc theo lô hoặc node và khoảng thời gian, kiểm tra độ mới, đếm mẫu và khoảng mất dữ liệu; sau đó mới tính GDD. $setWindowFields cộng dồn GDD theo thời gian để trả lời “đang tích lũy được bao nhiêu nhiệt hữu hiệu?”. Nếu thiếu ngày, báo thiếu thay vì nội suy để tạo một con số đẹp.")
table(d,["Năng lực MongoDB","Cách dùng trong SMIOT","Vì sao phù hợp"],[
["Document model","Một mẫu telemetry chứa nhóm phép đo; hồ sơ sự cố, lô và action ledger là document nghiệp vụ riêng.","Có thể bổ sung loại sensor/metadata mà không ép mọi loại dữ liệu vào một bảng quan hệ phẳng."],
["Time Series","TimeField + meta ổn định cho farm, node, source; truy vấn theo thiết bị và thời gian.","Dữ liệu cảm biến vốn là chuỗi thời gian; lọc đúng meta và time range giúp truy vấn đúng phạm vi."],
["Aggregation Pipeline","Tính completeness, gap và thống kê rồi mới tính GDD.","Không tải toàn bộ raw về Python để tự nhóm; giữ quy tắc phân tích sát dữ liệu."],
["$setWindowFields","GDD cộng dồn theo node/ngày.","Thể hiện xu hướng mùa vụ theo cửa sổ thời gian, không chỉ giá trị cuối."],
["Bằng chứng đo","Cửa sổ 1 giờ: 240 raw docs / 28,533 bytes / 23.701 ms; aggregation 2 dòng / 301 bytes / 2.712 ms.","Trong phép đo này payload giảm ~98.9%; cần giới hạn tuyên bố ở workload đã đo."]
],[1.25,3.05,2.6],8.3)
d.add_heading("Cách kể với ban giám khảo",2)
d.add_paragraph("“Nếu tôi lấy raw telemetry rồi mới tính trên app, tôi phải kéo từng mẫu về, tự nhóm từng ngày và tự phát hiện ngày thiếu. Ở đây MongoDB giữ chuỗi cảm biến theo thời gian; pipeline kiểm tra dữ liệu trước, rồi dùng window function tính GDD tích lũy. Trong cửa sổ đã đo, màn hình chỉ cần 2 kết quả tổng hợp thay vì 240 mẫu raw. Tôi vẫn giữ raw để đối chiếu và không biến ngày thiếu thành ngày có dữ liệu.”")
d.add_heading("Giới hạn phải nói rõ",2)
bullet(d,"GDD base 10°C, ngày trồng và lịch sử 30 ngày là giả định dữ liệu minh họa; con số dự báo thu hoạch chưa được hiệu chuẩn với giống, điều kiện địa phương và quan sát thực tế.")
bullet(d,"Benchmark chỉ có một cửa sổ, một lần chạy; raw và aggregation đều examined 4 docs. Kết quả chứng minh giảm payload/thời gian quan sát trong lần đó, không chứng minh scan ít hơn hay nhanh hơn với mọi tải.")
bullet(d,"Đã khôi phục EBS snapshot vào môi trường cô lập và đọc 113,046 documents. Đây chưa phải logical mongodump/restore hoặc PITR.")
d.add_page_break()
d.add_heading("2. Datadog: Node 2 flatline có kiểm soát",1)
d.add_paragraph("Tình huống: Node 2 của greenhouse_a tiếp tục phát bản tin, nhưng độ ẩm đất bị cố định ở 2.4%. Câu hỏi điều tra không phải “đầu dò vật lý đã hỏng chưa?” mà là “publisher còn gửi không, Mongo có lưu mẫu mới không, và có nên cho phép tưới dựa vào kênh số đo đáng ngờ không?”.")
table(d,["Bước","Bằng chứng vận hành","Kết luận được phép"],[
["Phát hiện","Datadog monitor 339977691 / metric sensor_flatline báo trạng thái; hiện monitor đang OK.","Tín hiệu flatline đã được phát hiện và có timeline Alert/OK; ảnh chụp là trạng thái hiện tại."],
["Khoanh vùng","Node 2 gửi các mẫu 2.4% liên tiếp trong khi sequence tăng và Mongo vẫn ghi nhận mẫu; Node 1 tiếp tục biến thiên.","Đây là giá trị bị giữ đứng ở luồng synthetic, không giống mất publisher hay mất toàn bộ DB."],
["Điều tra","Logs và APM có thể lọc cùng incident ID INC-SMIOT-20261103T114321-BD19A22C, farm greenhouse_a, node 2.","Có thể chuyển từ metric sang log và trace theo cùng bối cảnh. Ảnh hiện tại hiển thị 239 logs và 242 spans trong cửa sổ truy vấn."],
["Phản ứng","Workflow safe mode ghi HOLD được ACK; virtual outputs giữ OFF; verifier chỉ CLEAR sau mẫu mới dao động, monitor OK và ACK.","Bằng chứng phục hồi luồng telemetry và trạng thái an toàn ảo; không phải sửa đầu dò hoặc điều khiển bơm thật."],
["Bits","Bits nêu đúng tình huống flatline synthetic và tác động; panel ghi lần xác nhận recovery chưa được Bits xác nhận.","Dùng Bits để điều tra/hypothesis; dùng verifier và dữ liệu app làm bằng chứng recovery độc lập."]
],[.85,3.4,2.65],8.2)
d.add_heading("Điểm sáng tạo",2)
d.add_paragraph("Monitor không chỉ nhìn một ngưỡng độ ẩm. Nó dùng tín hiệu flatline riêng, có tag farm/node/source để phân biệt “không đổi nhưng vẫn gửi” với “không có bản tin”. Hệ thống không cho một kênh nghi ngờ tự biến thành lệnh tưới: trạng thái ảo HOLD là biện pháp an toàn, còn CLEAR cần dữ liệu mới và kiểm tra trạng thái. Đây là logic phản ứng vận hành có kiểm chứng, không phải tự động hóa mù.")
d.add_heading("3. Datadog: EC2 app outage, phục hồi đúng thành phần",1)
d.add_paragraph("Ca thứ hai độc lập với Node 2. Dịch vụ smiot.service trên EC2 bị dừng có chủ đích trong diễn tập, còn MongoDB và MQTT đang hoạt động. Monitor “SMIOT | EC2 app service inactive” chuyển Alert. Datadog workflow chạy predefined script có giới hạn quyền.")
numbered(d,"Kiểm tra trước: MongoDB/MQTT healthy, root disk dưới ngưỡng và trạng thái systemd cho thấy app unit dừng.")
numbered(d,"Chỉ gọi systemctl start smiot.service; không restart EC2, MongoDB, MQTT hoặc Datadog Agent.")
numbered(d,"Xác minh systemd active, endpoint HTTP 200 và telemetry mới đọc lại được từ MongoDB.")
numbered(d,"Workflow execution cho run_id 20261104T121846Z-161767 ghi action=start, result=verified, reason=app_http_and_fresh_mongodb_telemetry. Monitor hiện OK.")
d.add_paragraph("Đây là câu chuyện cloud có tác động: giảm phạm vi gián đoạn và tránh restart database/máy chủ khi lỗi nằm ở riêng web service. Quy tắc được thiết kế fail-closed: nếu dependencies hoặc readback không khỏe, workflow từ chối hành động. Một success log chưa được xác nhận index trong Datadog Logs, nên bằng chứng chính là output của workflow cùng kiểm tra SSM/HTTP/Mongo.")
d.add_heading("4. Vì sao hai sản phẩm bổ sung cho nhau",1)
table(d,["Câu hỏi","MongoDB trả lời","Datadog trả lời"],[
["Dữ liệu có đáng tin để tính?","Time Series + aggregation kiểm tra coverage/gap và giữ raw đối chiếu.","Metrics/monitors phát hiện freshness, dependency hoặc flatline."],
["Làm sao tìm nguyên nhân?","Truy vấn telemetry, incident record, action ledger theo thời gian/node.","Từ monitor đi đến Logs/APM/Bits với cùng incident context."],
["Phản ứng có an toàn không?","Ledger ghi HOLD/CLEAR và kết quả verifier.","Workflow chọn đúng action, áp dụng pre-check và chống hành động quá mức."],
["Đã phục hồi chưa?","Mẫu Mongo mới phải xuất hiện và dao động hợp lệ.","Monitor trở OK; workflow/incident timeline chứng minh hành động."]
],[1.55,2.7,2.65],8.5)
d.add_heading("5. Mức hoàn thiện và việc cần tránh tuyên bố",1)
bullet(d,"Có nền tảng trình diễn sâu cho MongoDB: Time Series, aggregation/window GDD, benchmark raw-vs-aggregation và snapshot restore.")
bullet(d,"Có hai câu chuyện Datadog độc lập và dễ theo dõi: lỗi kênh telemetry Node 2 và lỗi dịch vụ web EC2.")
bullet(d,"Dashboard hiện ghi SLO 7 ngày 98.62% với target 99%. Đây là giá trị giao diện lúc chụp; cần trình bày như số liệu dashboard, không quảng cáo là cam kết SLA hay kết quả vận hành dài hạn đã kiểm toán.")
bullet(d,"Chưa có đối chiếu chi phí AWS actual với Datadog bill; chưa có cost/1,000 bản tin; chưa có thiết bị/actuator vật lý; lot correlation chỉ trình bày nếu mapping có căn cứ.")
bullet(d,"Bits điều tra có kết luận được hiệu chỉnh, nhưng UI hiện tại chưa xác nhận bước recovery; không ghi Bits là đã chứng minh CLEAR.")
d.add_heading("Tài liệu tham khảo",1)
refs=[
("MongoDB · Time Series best practices","https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/"),
("MongoDB · $setWindowFields","https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/"),
("Datadog · Monitor notifications / workflow trigger","https://docs.datadoghq.com/monitors/notify/"),
("Datadog · Workflow Automation","https://docs.datadoghq.com/getting_started/workflow_automation/"),
("Datadog · Monitor-based SLO","https://docs.datadoghq.com/service_level_objectives/monitor/"),
("Datadog · Private Actions","https://docs.datadoghq.com/actions/private_actions/")]
for label,url in refs:
    p=d.add_paragraph(style='List Bullet'); add_hyperlink(p,label,url)
d.save(OUT1)

# Demo script
d=Document(); setup(d,"Kịch bản demo Datadog")
cover(d,"Kịch bản thuyết trình · 7–9 phút","Một tín hiệu bất thường, một quyết định an toàn","Demo hai ca Datadog trên môi trường cloud: Node 2 telemetry và EC2 app service")
d.add_heading("Mục tiêu trình diễn",1)
d.add_paragraph("Giám khảo nhìn thấy rõ chuỗi Phát hiện → Điều tra → Phản ứng → Xác minh phục hồi. Node 2 và EC2 là hai ca độc lập; mỗi ca có incident/run ID riêng. Không gộp chúng thành một incident duy nhất.")
table(d,["Thời gian","Màn hình / thao tác","Thông điệp nói"],[
["0:00–0:40","Dashboard SMIOT · Farm Operations & Recovery","“Đây là vận hành farm trên AWS; biểu đồ đến từ telemetry publisher synthetic. Từ dashboard tôi phân biệt dữ liệu farm, dependencies, SLO và Mongo DBM.”"],
["0:40–3:45","Ca 1 · Node 2 flatline: monitor → logs → APM → Bits → HOLD/recovery","“Node 2 vẫn gửi mẫu nhưng độ ẩm đứng ở 2.4%. Ta cần phân biệt flatline với mất kết nối và ngăn quyết định tưới dựa trên kênh đáng ngờ.”"],
["3:45–6:30","Ca 2 · EC2 app outage: monitor → workflow output → kiểm tra phục hồi","“Lỗi ở web service không đồng nghĩa máy chủ hoặc database hỏng. Workflow chỉ khởi động đúng dịch vụ, rồi yêu cầu HTTP và dữ liệu Mongo mới để xác nhận.”"],
["6:30–7:30","SLO, giới hạn và kết luận","“Datadog biến quan sát thành xử lý có bằng chứng; MongoDB giữ lịch sử và dữ liệu phân tích. Tôi nói rõ phần nào đã xác nhận và phần nào chưa.”"]
],[1.05,2.55,3.3],8.5)
d.add_heading("Chuẩn bị trước khi trình bày",2)
bullet(d,"Mở sẵn dashboard, monitor Node 2, Logs query, APM query, Bits Investigation, EC2 monitor và workflow execution.")
bullet(d,"Đặt Datadog time range sao cho timeline Node 2 là Nov 3 và timeline EC2 là Nov 4; giao diện hiển thị UTC+07:00.")
bullet(d,"Không bật lại sự cố trong lúc thuyết trình nếu mục tiêu là xem bằng chứng đã lưu. Nếu chạy lại live, ghi lại run/incident ID mới và kiểm tra monitor, log, trace, ledger sau đó.")
bullet(d,"Không tuyên bố đầu dò/bơm thật được sửa; các kết quả actuator là virtual outputs. Không gộp incident Node 2 với EC2 run ID.")
d.add_page_break()
d.add_heading("Ca 1 · Node 2 phát dữ liệu nhưng số đo bị đứng",1)
d.add_paragraph("Incident: INC-SMIOT-20261103T114321-BD19A22C · Monitor: 339977691 · greenhouse_a / node 2 · nguồn synthetic.")
d.add_heading("1. Phát hiện trên monitor",2)
d.add_paragraph("Mở monitor Node 2. Chỉ vào query sensor_flatline theo farm/node/source và timeline Alert → OK/No Data hiện tại. Giải thích đây là detector riêng cho mẫu không đổi; monitor lúc chụp đang OK.")
numbered(d,"Nói: “Cảm biến mô phỏng vẫn phát đều, nhưng độ ẩm lặp 2.4%. Điều này khác với publisher chết: khi mất publisher, ta sẽ thấy telemetry stale/no-data.”")
pic(d,"smiot-node2-monitor-current.png","Ảnh 1. Monitor Node 2 hiện OK; query flatline lọc greenhouse_a, node 2 và source smiot_demo_stream.")
d.add_heading("2. Lần từ metric tới log và trace",2)
d.add_paragraph("Mở Logs đã lọc theo service, incident.id, farm.key và node.id. Ảnh đang có 239 logs trong cửa sổ truy vấn; đó là số kết quả UI tại thời điểm chụp, không phải tổng số log của cả incident.")
pic(d,"smiot-node2-logs.png","Ảnh 2. Log Explorer lọc cùng incident ID và bối cảnh farm/node; các log có event incident và dữ liệu theo thời gian.")
d.add_paragraph("Mở APM Traces bằng cùng incident ID. Ảnh đang hiện 242 indexed spans; bảng có các resource như farm/command/event, farm/command/ack và farm/sensor. Đây là cách chuyển từ triệu chứng sang đường xử lý.")
pic(d,"smiot-node2-apm.png","Ảnh 3. APM truy vấn service smiot-smart-farm với cùng incident.id; hiển thị requests, latency và các spans.")
d.add_heading("3. Bits điều tra và giới hạn kết luận",2)
d.add_paragraph("Mở Bits Investigation “Injected flatline scenario paused greenhouse Node 2 telemetry”. Chỉ vào kết luận injected flatline và impact virtual output paused. Sau đó chỉ rõ panel hội thoại ghi rằng Bits chưa xác nhận monitor recovery / safe-mode clear trong lượt nó đang xem. Không gán cho Bits xác nhận mà UI chưa đưa ra.")
pic(d,"smiot-bits-node2-investigation-latest.png","Ảnh 4. Bits xác định tình huống flatline synthetic; phần hội thoại vẫn yêu cầu xác nhận recovery riêng.")
d.add_heading("4. HOLD, phục hồi và CLEAR",2)
d.add_paragraph("Dùng evidence record của ứng dụng: ngày 03/11 publisher ACK chuyển chế độ, các mẫu Node 2 giữ 2.4% trong khi sequence tăng; HOLD ảo được ACK và mọi output giữ OFF. Sau khi publisher ACK về chế độ bình thường, mẫu Mongo mới dao động 39.3–41.0%; monitor OK; verifier kiểm tra dữ liệu mới và ACK rồi mới gửi CLEAR. Đây là phục hồi luồng telemetry và virtual safe state, không phải sửa đầu dò vật lý.")
d.add_paragraph("Presenter line: “Điều chúng tôi chứng minh là ứng dụng không tin mù vào một kênh đứng giá. Nó đưa output ảo về HOLD, chờ bản tin mới có biến thiên, đối chiếu monitor và ACK, rồi mới CLEAR. Mô phỏng này chứng minh logic; nó không chứng minh sửa phần cứng.”")
d.add_page_break()
d.add_heading("Ca 2 · Dịch vụ web EC2 dừng, dependencies vẫn khỏe",1)
d.add_paragraph("Workflow run: 20261104T121846Z-161767 · Execution: 41135755-2edd-429b-9c0f-9e73ae7c43a1 · EC2: i-00bf2d3591d3ee0a2 · service: smiot.service.")
d.add_heading("5. Phát hiện trên monitor EC2",2)
d.add_paragraph("Mở monitor “SMIOT | EC2 app service inactive”. Timeline có Alert và các lần trở về OK; trạng thái hiện tại OK. Query dựa trên systemd unit active của smiot.service.")
pic(d,"smiot-ec2-monitor.png","Ảnh 5. Monitor EC2 ghi các lần Alert/OK; lúc chụp monitor đang OK.")
d.add_heading("6. Cho thấy workflow xử lý đúng phạm vi",2)
d.add_paragraph("Mở execution có run ID trên. Chỉ vào hai bước thành công: monitor trigger và predefined script. Output ghi action=start, result=verified, reason=app_http_and_fresh_mongodb_telemetry, timestamp 2026-11-04T12:18:57Z.")
pic(d,"smiot-ec2-workflow-execution.png","Ảnh 6. Datadog Workflow execution chạy predefined recovery script; output đã xác minh app HTTP và telemetry Mongo mới.")
d.add_paragraph("Presenter line: “Workflow không khởi động lại cả EC2. Nó chỉ start service khi app unit dừng, Mongo/MQTT healthy, disk đạt điều kiện và Mongo readback được. Thành công chỉ được ghi sau systemd active, HTTP 200 và telemetry mới trong Mongo.”")
d.add_heading("7. Khép vòng và nêu lợi ích",2)
bullet(d,"Phạm vi sửa nhỏ hơn: một service thay vì cả máy, database hay broker.")
bullet(d,"Bằng chứng hậu kiểm: systemd, HTTP và bản tin mới từ Mongo; monitor trở OK.")
bullet(d,"Giới hạn: output thành công của workflow là bằng chứng chính; chưa xác nhận log thành công đã được index trong Datadog Logs.")
d.add_page_break()
d.add_heading("Màn hình tổng kết · nối hai luồng mà không trộn incident",1)
pic(d,"smiot-dashboard-us.png","Ảnh 7. Dashboard Datadog US1: telemetry theo node, Mongo/MQTT dependency, SLO và MongoDB DBM.")
table(d,["Khía cạnh","Node 2 flatline","EC2 app outage"],[
["ID","INC-SMIOT-20261103T114321-BD19A22C","Run 20261104T121846Z-161767 / execution 41135755-2edd-429b-9c0f-9e73ae7c43a1"],
["Lỗi","Luồng số synthetic giữ soil humidity ở 2.4%","Unit ứng dụng smiot.service bị dừng; MongoDB/MQTT khỏe"],
["Tự động hóa","SAFE HOLD ảo; CLEAR sau dữ liệu mới, monitor OK và ACK","Start riêng app service sau điều kiện; xác minh HTTP 200 + Mongo readback"],
["Điều đã chứng minh","Phát hiện, điều tra theo bối cảnh, xử lý an toàn và phục hồi telemetry","Giảm phạm vi khôi phục và xác minh dịch vụ"],
["Không khẳng định","Đầu dò vật lý hỏng/đã sửa hoặc bơm thật chạy","Log success chắc chắn đã index; restart toàn EC2"]
],[.9,2.8,3.1],8.2)
d.add_heading("Câu kết 20 giây",2)
d.add_paragraph("“MongoDB giúp chúng tôi giữ chuỗi telemetry và tính toán gần dữ liệu, đồng thời kiểm tra dữ liệu thiếu trước khi đưa ra ước tính mùa vụ. Datadog nối tín hiệu đó với log, trace và hành động vận hành. Điểm khác biệt là cả hai ca đều có hậu kiểm: không chỉ phát hiện lỗi, mà còn chứng minh đúng phạm vi đã xử lý và dữ liệu đã trở lại.”")
d.add_heading("Liên kết mở nhanh",2)
links=[
("Dashboard","https://app.datadoghq.com/dashboard/nkc-685-vw8"),
("Node 2 monitor","https://app.datadoghq.com/monitors/339977691"),
("Node 2 Bits Investigation","https://app.datadoghq.com/bits-ai/investigations/3de8802a-d62c-4983-b2d9-07c7dc3bdf1c?investigation-view__mode=tree"),
("EC2 app monitor","https://app.datadoghq.com/monitors/340356283"),
("EC2 workflow","https://app.datadoghq.com/workflow/b83453ff-e122-4148-9519-e698f2effa7f?debugItem=step%3ARun_Predefined_Script&instance=41135755-2edd-429b-9c0f-9e73ae7c43a1"),
("Incident evidence","https://app.datadoghq.com/logs?from_ts=1793706000000&live=false&query=service%3Asmiot-smart-farm%20%40incident.id%3AINC-SMIOT-20261103T114321-BD19A22C%20%40farm.key%3Agreenhouse_a%20%40node.id%3A2&stream_sort=asc&to_ts=1793713482142"),
("APM correlated traces","https://app.datadoghq.com/apm/traces?end=1793713483043&historicalData=true&paused=true&query=service%3Asmiot-smart-farm%20%40incident.id%3AINC-SMIOT-20261103T114321-BD19A22C&start=1793706000000")]
for label,url in links:
    p=d.add_paragraph(style='List Bullet'); add_hyperlink(p,label,url)
d.add_heading("Câu hỏi giám khảo có thể hỏi",1)
table(d,["Câu hỏi","Trả lời ngắn"],[
["Dữ liệu có phải từ cảm biến thật không?","Không. Đây là publisher synthetic trên cloud; câu chuyện kiểm chứng luồng phần mềm và phản ứng an toàn, không khẳng định thiết bị vật lý đã lỗi."],
["Bits đã xác nhận phục hồi chưa?","Chưa. Bits nêu đúng triệu chứng; app verifier, Mongo readback và monitor OK là các bằng chứng phục hồi độc lập."],
["Vì sao dùng MongoDB cho telemetry?","Time Series giữ dữ liệu theo thời gian với metadata node/farm; aggregation và window tính độ đầy đủ, khoảng trống và GDD gần dữ liệu."],
["Workflow có restart cả máy không?","Không. Ca EC2 chỉ start smiot.service sau khi MongoDB/MQTT và disk qua kiểm tra, rồi xác minh HTTP 200 và telemetry mới."],
["SLO 98.62% có phải SLA đã kiểm toán?","Không. Đó là rolling 7 ngày đang hiển thị trên dashboard tại lúc chụp; cần kiểm tra chi tiết định nghĩa và lịch sử trước khi diễn giải như cam kết."],
],[2.25,4.5],8.5)
d.add_heading("Nguồn dữ liệu và chú thích",1)
d.add_paragraph("Ảnh chụp được lấy trực tiếp từ Datadog US1 ngày 04/11/2026 và đính trong tài liệu. Mốc thời gian Node 2 tham chiếu hồ sơ diễn tập ngày 03/11/2026, giờ UTC; giao diện Datadog hiển thị UTC+07:00. Dữ liệu sensor và PLC trong các diễn tập là synthetic/virtual.")
d.add_paragraph("Thông tin về service recovery, Mongo readback, snapshot restore, GDD và giới hạn benchmark đối chiếu với reports/20261103_cloud_live_verification.md và docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md trong repository.")
d.save(OUT2)
print("created",OUT1,OUT2)

