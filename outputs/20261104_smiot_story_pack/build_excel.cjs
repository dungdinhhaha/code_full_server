const fs = require('node:fs/promises');
const { Workbook, SpreadsheetFile } = require('@oai/artifact-tool');
(async () => {
const outDir = 'D:/IOT Trung/code_full_server/outputs/20261104_smiot_story_pack';
const wb = Workbook.create();
const sh = wb.worksheets.add('Danh gia');
sh.showGridLines = false;
sh.tabColor = '#167D8D';
sh.mergeCells('A1:F1'); sh.getRange('A1').values = [['SMIOT | ĐỐI CHIẾU TIÊU CHÍ, CÔNG VIỆC VÀ BẰNG CHỨNG']];
sh.mergeCells('A2:F2'); sh.getRange('A2').values = [['Đối chiếu theo bằng chứng hiện có ngày 04/11/2026']];
sh.mergeCells('A3:F3'); sh.getRange('A3').values = [['Mỗi dòng cho biết điều đã làm, nơi xem bằng chứng và phần cần hoàn thiện.']];
sh.getRange('A5:F5').values = [['Nền tảng','Tiêu chí','Đã làm được / minh chứng cụ thể','Trạng thái','Bằng chứng mở nhanh','Giới hạn / việc còn thiếu']];
const rows = [
['MongoDB','MongoDB là kho dữ liệu vận hành chính','Ứng dụng cloud dùng MongoDB Community 8.0.34 trên EC2; telemetry và nghiệp vụ nằm trong DB smiot.',8.5,'Có bằng chứng','Biên bản cloud · mục 2','MongoDB cùng EC2 nên chung failure domain; chưa chuyển sang Atlas.'],
['MongoDB','Mô hình dữ liệu và truy cập hiệu quả','Time Series smiot.telemetry có timeField/meta ổn định; collections nghiệp vụ cho incidents, action ledger, schedules, traceability.',8,'Có bằng chứng','Biên bản cloud · mục 2','Cần đo index/query trên nhiều kích thước tải.'],
['MongoDB','Aggregation Pipeline gắn với bài toán','Aggregation tính độ đầy đủ, khoảng trống mẫu và GDD trên 30 ngày dữ liệu; không bù ngày thiếu.',8.5,'Có bằng chứng','telemetry_quality_report.py · mục 2','GDD/ngày trồng là giả định demo, chưa hiệu chuẩn nông học.'],
['MongoDB','Time Series và window functions','$setWindowFields tính GDD tích lũy theo node; raw và aggregation khớp thống kê trong benchmark 1 giờ.',9,'Nổi bật được','Benchmark · mục 10','Một lần chạy; chưa chứng minh lợi thế phổ quát hoặc giảm docs examined.'],
['MongoDB','Hiệu năng và lượng dữ liệu','Raw 240 docs, 28,533 bytes, 23.701 ms; aggregation 2 dòng, 301 bytes, 2.712 ms; payload giảm ~98.9%.',8,'Một workload','Benchmark · mục 10','Một cửa sổ, một lần chạy; cả hai đường examined 4 docs.'],
['MongoDB','Backup và khôi phục','Backup logic tách collection nghiệp vụ và Time Series, lưu S3; restore thử 154.618/154.618 mẫu telemetry và 1/1 incident.',8.5,'Restore logic đã xác minh','Biên bản backup/restore 03/11','Chưa thử khôi phục snapshot EBS hoặc point-in-time recovery.'],
['Datadog','Dashboard vận hành','Dashboard US1 được kiểm tra lại 04/11 có 8 widgets, gồm biểu đồ, giá trị tổng hợp và SLO.',8,'Có bằng chứng','Dashboard US1 · nkc-685-vw8','Số widget lấy từ kiểm tra trực tiếp; giá trị SLO thay đổi theo thời gian.'],
['Datadog','Monitor gắn với rủi ro','Có monitor flatline Node 2 và monitors cho app EC2, MongoDB, MQTT, telemetry stale.',8.5,'Có hai ca','Ảnh Node2/EC2 monitor','Node 2 là lỗi luồng synthetic; không kết luận đầu dò vật lý hỏng.'],
['Datadog','Logs và APM','Tìm cùng incident ID trong Logs/APM; ảnh hiện tại cho thấy 239 logs và 242 indexed spans.',8.5,'Có liên kết ID','Ảnh Logs + APM','Số lượng phụ thuộc thời gian/index; không phải mọi log/span đều cùng ID.'],
['Datadog','Metrics, logs, traces và bối cảnh','Node2 nối incident, farm/node, publisher, monitor, HOLD/CLEAR trong hồ sơ ứng dụng. EC2 nối alert → workflow → HTTP/Mongo readback.',8,'Một phần sâu','Kịch bản demo; hai ca tách riêng','Chưa nối đầy đủ mọi sự kiện với lot; không gộp incident Node2 và EC2.'],
['Datadog','Bits Investigation','Bits kết luận đúng đây là injected synthetic flatline và nêu impact; panel hiện nói recovery check chưa được Bits xác nhận.',7,'Điều tra có giới hạn','Ảnh Bits','App verifier/monitor là bằng chứng recovery độc lập; không nói Bits xác nhận CLEAR.'],
['Datadog','Workflow phục hồi guarded','EC2 service outage kích workflow; chỉ start smiot.service sau prechecks; xác minh HTTP 200 và telemetry Mongo mới.',8.5,'Execution xác minh','Ảnh workflow; report cloud','Không restart EC2/Mongo/MQTT. Success log chưa xác nhận được index trong Logs.'],
['Datadog','SLO','Dashboard hiện hiển thị Trusted Telemetry Pipeline Availability rolling 7d = 98.62%, target 99%.',7,'Đã cấu hình; số đang hiển thị','Ảnh dashboard · widget SLO','Đây là giá trị UI tại lúc chụp; cần kiểm tra chi tiết SLO và lịch sử trước khi gọi là SLA đã kiểm toán hoặc kết quả dài hạn.'],
['Cloud','Chi phí cloud','Đã kiểm tra Cost Explorer và nhận diện dữ liệu estimated; có định hướng cost trên mỗi bản tin hợp lệ.',4,'Chưa đủ bằng chứng','Biên bản cloud · mục 5','Chưa có chi phí actual, CUR/Datadog bill đối chiếu hay cost/1,000 bản tin.']
];
sh.getRange('A6:F19').values = rows.map(([platform,criterion,done,_score,status,evidence,gap]) => [platform,criterion,done,status,evidence,gap]);
sh.tables.add('A5:F19', true, 'EvidenceTable');
sh.freezePanes.freezeRows(5);
sh.getRange('A1:F1').format = {fill:'#123047',font:{bold:true,color:'#FFFFFF',size:16},verticalAlignment:'center'};
sh.getRange('A2:F2').format = {fill:'#DCEEF2',font:{color:'#123047',size:10,italic:true},wrapText:true,verticalAlignment:'center'};
sh.getRange('A3:F3').format = {fill:'#F2F6F8',font:{color:'#475569',size:10},wrapText:true,verticalAlignment:'center'};
sh.getRange('A5:F5').format = {fill:'#167D8D',font:{bold:true,color:'#FFFFFF',size:10},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
sh.getRange('A6:F19').format = {font:{name:'Aptos',size:10,color:'#1F2937'},wrapText:true,verticalAlignment:'top'};
sh.getRange('D6:D19').format = {font:{bold:true,size:9},wrapText:true,verticalAlignment:'center'};
sh.getRange('A1:F1').format.rowHeight = 32; sh.getRange('A2:F3').format.rowHeight = 28; sh.getRange('A5:F5').format.rowHeight = 38; sh.getRange('A6:F19').format.rowHeight = 68;
for (const [c,w] of [['A',14],['B',30],['C',55],['D',20],['E',32],['F',46]]) sh.getRange(c+':'+c).format.columnWidth = w;
const file = await SpreadsheetFile.exportXlsx(wb); await file.save(outDir+'/Bang_doi_chieu_tieu_chi_va_minh_chung.xlsx');
const p = await wb.render({sheetName:'Danh gia',range:'A1:F9',scale:1,format:'png'}); await fs.writeFile(outDir+'/evidence/excel-preview.png',Buffer.from(await p.arrayBuffer()));
console.log(JSON.stringify(await wb.inspect({kind:'workbook,sheet,table',maxChars:2000,tableMaxRows:3,tableMaxCols:7})));
})();
