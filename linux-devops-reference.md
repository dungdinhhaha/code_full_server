# Linux & DevOps — Tra theo tình huống

## Cách dùng file này

File này không phải để học thuộc. Nó được tổ chức theo câu hỏi "tôi đang muốn làm gì / đang gặp vấn đề gì" → "thì cần công cụ/khái niệm nào". Khi gặp tình huống thật, bạn mở file, tìm đúng mục, nhớ lại tên công cụ, rồi tra cú pháp chi tiết (man page, --help, hoặc search). Mục tiêu là xây bản đồ trong đầu: thấy triệu chứng → biết đi tìm ở đâu. Không cần nhớ hết cú pháp.

Mỗi mục có 4 phần: **Tình huống** (dấu hiệu nhận biết), **Cần biết gì** (khái niệm nền), **Công cụ** (lệnh cụ thể), **Mẹo nhớ** (cách liên kết để không quên).

---

# PHẦN 1 — LINUX

## 1. "Server có vẻ không ổn, nhưng chưa biết bị gì" (chẩn đoán tổng quát)

**Tình huống:** app chậm, user báo lỗi, bạn chưa biết bắt đầu từ đâu.

**Cần biết gì:** luôn đi theo thứ tự từ tổng quát → cụ thể: CPU/RAM/Disk/Network trước, rồi mới soi vào từng service.

**Công cụ:**
- `top` / `htop` — tổng quan CPU, RAM, process nào đang ăn tài nguyên
- `uptime` — load average (1, 5, 15 phút) để biết máy quá tải từ bao lâu
- `df -h` — disk còn trống bao nhiêu
- `free -h` — RAM còn bao nhiêu, có đang swap không
- `vmstat 1` — xem CPU/memory/IO theo thời gian thực, phát hiện bottleneck
- `uptime` + `w` — máy chạy bao lâu, ai đang login

**Mẹo nhớ:** thứ tự chẩn đoán luôn là **CPU → RAM → Disk → Network → Application logs**. Đây là trình tự loại trừ từ hạ tầng vật lý lên tới logic app. 90% sự cố lộ ra ngay ở 1 trong 4 bước đầu.

---

## 2. "CPU hoặc RAM cao bất thường"

**Tình huống:** `top` cho thấy 1 process chiếm CPU/RAM cao, hoặc máy bị OOM kill.

**Cần biết gì:** mỗi process có PID, dùng resource riêng, kernel có thể giết process khi hết RAM (OOM killer).

**Công cụ:**
- `top`/`htop` sort theo %CPU hoặc %MEM (phím `P` / `M`)
- `ps aux --sort=-%mem` — list process sort theo RAM
- `kill -15 <PID>` (graceful) → `kill -9 <PID>` (force, chỉ dùng khi graceful không chết)
- `dmesg | grep -i "out of memory"` hoặc `journalctl -k | grep -i oom` — xác nhận có bị OOM kill không và process nào bị giết
- `/proc/<PID>/status`, `/proc/<PID>/limits` — xem chi tiết resource của 1 process
- `ulimit -a` — giới hạn resource hiện tại của shell/user

**Mẹo nhớ:** `kill -9` là biện pháp cuối, không phải mặc định — nó không cho process dọn dẹp (đóng file, flush buffer), dễ gây mất dữ liệu hoặc file lock kẹt lại.

---

## 3. "Disk đầy hoặc sắp đầy"

**Tình huống:** app không ghi được file, báo lỗi "No space left on device".

**Cần biết gì:** disk đầy có 2 loại: hết dung lượng (space) hoặc hết inode (số lượng file), kiểm tra riêng.

**Công cụ:**
- `df -h` — dung lượng còn trống theo từng partition
- `df -i` — số inode còn trống (hay bị quên, log tạo quá nhiều file nhỏ sẽ hết inode trước khi hết dung lượng)
- `du -sh /* 2>/dev/null | sort -rh` — tìm thư mục nào đang chiếm nhiều dung lượng nhất
- `find / -xdev -size +100M` — tìm file lớn cụ thể
- `logrotate` — cơ chế tự động xoay/xóa log cũ, kiểm tra config ở `/etc/logrotate.d/`
- Lưu ý: xóa file đang bị process giữ mở (`lsof | grep deleted`) không giải phóng dung lượng ngay — phải restart process đó

**Mẹo nhớ:** disk đầy do log là nguyên nhân phổ biến nhất trong production. Luôn kiểm tra `/var/log` đầu tiên, và luôn đảm bảo mọi service có logrotate từ ngày đầu deploy, không phải đợi đầy mới cấu hình.

---

## 4. "Service/app không chạy, bị crash, hoặc crash loop"

**Tình huống:** app down, hoặc cứ restart liên tục.

**Cần biết gì:** trên Linux hiện đại, hầu hết service được quản lý bởi **systemd** — nó start/stop/restart service theo policy định nghĩa trong "unit file".

**Công cụ:**
- `systemctl status <service>` — trạng thái hiện tại, lý do crash gần nhất
- `systemctl start/stop/restart/enable <service>`
- `journalctl -u <service> -n 100 --no-pager` — 100 dòng log gần nhất của service đó
- `journalctl -u <service> -f` — tail log real-time (giống `tail -f`)
- `systemctl list-units --failed` — liệt kê mọi service đang failed
- File unit nằm ở `/etc/systemd/system/*.service` — xem `ExecStart`, `Restart=`, `User=`, `Environment=`
- Sau khi sửa unit file: `systemctl daemon-reload` rồi mới `restart`

**Mẹo nhớ:** crash loop gần như luôn có nguyên nhân nằm ngay trong vài dòng log đầu tiên sau mỗi lần start — đọc `journalctl -u <service>` từ dưới lên, không phải đọc hết từ trên.

---

## 5. "Không kết nối được network, hoặc DNS không resolve"

**Tình huống:** app không gọi được API ngoài, hoặc không truy cập được domain.

**Cần biết gì:** phân biệt lỗi ở layer nào: DNS (không resolve được tên), routing (resolve được nhưng không tới được IP), hay port/firewall (tới được IP nhưng bị chặn port).

**Công cụ:**
- `ping <host>` — kiểm tra connectivity cơ bản (nhiều server chặn ICMP, không thấy ping được chưa chắc là mất mạng)
- `dig <domain>` hoặc `nslookup <domain>` — kiểm tra DNS resolve
- `curl -v <url>` — xem chi tiết từng bước kết nối (DNS, TCP connect, TLS handshake, HTTP response)
- `ss -tulnp` (thay cho `netstat` cũ) — xem port nào đang listen, process nào đang giữ port
- `traceroute <host>` / `mtr <host>` — xem gói tin đi qua đâu, nghẽn ở đâu
- `iptables -L -n` hoặc `nft list ruleset` — kiểm tra firewall rule trên máy
- Trên AWS: Security Group và Network ACL là firewall ở tầng ngoài, kiểm tra trước khi nghi ngờ iptables trong máy

**Mẹo nhớ:** thứ tự debug network luôn là **DNS → TCP connect → TLS → HTTP**. `curl -v` cho bạn thấy chính xác dừng ở bước nào.

---

## 6. "Lỗi permission / access denied"

**Tình huống:** app không đọc/ghi được file, hoặc user không chạy được lệnh.

**Cần biết gì:** mỗi file có owner (user), group, và permission bits (read/write/execute) cho 3 nhóm: owner/group/others. Process chạy bằng user nào sẽ bị áp permission của user đó.

**Công cụ:**
- `ls -la` — xem owner, group, permission của file
- `chmod` — đổi quyền (ví dụ `chmod 644 file`, `chmod +x script.sh`)
- `chown user:group file` — đổi owner/group
- `whoami`, `id` — biết mình đang là user nào, thuộc group nào
- `ps aux | grep <service>` — xem service đang chạy bằng user nào (cột USER)
- `sudo -l` — xem user hiện tại có quyền sudo gì
- Nếu dùng SELinux (CentOS/RHEL) hoặc AppArmor (Ubuntu): đôi khi permission đúng nhưng vẫn bị chặn bởi security module này — kiểm tra bằng `getenforce`, `audit log` (`/var/log/audit/audit.log`) hoặc `dmesg | grep -i apparmor`

**Mẹo nhớ:** câu hỏi luôn là "process này chạy bằng user nào, và user đó có quyền gì trên file này" — không phải "tôi (SSH vào) có quyền gì". Permission denied khi chạy service gần như luôn là do service chạy bằng user khác với user bạn đang test bằng tay.

---

## 7. "Cần tìm log để biết nguyên nhân lỗi"

**Tình huống:** có lỗi xảy ra, cần tìm log liên quan.

**Cần biết gì:** log nằm ở nhiều nơi tùy loại: system log (systemd/journald), application log (do app tự viết ra file hoặc stdout), và log của container nếu dùng Docker.

**Công cụ:**
- `journalctl` — log của systemd services, hỗ trợ filter theo thời gian (`--since`, `--until`), theo service (`-u`), theo priority (`-p err`)
- `/var/log/` — nơi chứa log truyền thống (`syslog`, `auth.log`, `nginx/`, `mysql/`...)
- `tail -f /path/to/log` — theo dõi log real-time
- `grep`, `zgrep` (cho file đã gzip) — tìm keyword trong log
- `docker logs <container>` — nếu app chạy trong container
- Với log lớn: `less +F file.log` để vừa search vừa follow

**Mẹo nhớ:** luôn bắt đầu bằng việc xác định đúng **khung giờ** sự cố xảy ra trước khi đọc log, dùng `--since "10 minutes ago"` hoặc tương tự — đọc log không có mốc thời gian là lạc giữa biển chữ.

---

## 8. "Cần xử lý file/text (lọc, thay thế, thống kê nhanh)"

**Tình huống:** cần lọc log, đổi config bằng tay, hoặc thống kê nhanh từ file text.

**Cần biết gì:** đây là nhóm công cụ "Unix philosophy" — mỗi lệnh làm 1 việc, ghép lại bằng pipe `|`.

**Công cụ:**
- `grep` — tìm dòng khớp pattern (`grep -i` không phân biệt hoa thường, `grep -v` loại trừ, `grep -c` đếm)
- `sed` — thay thế text (`sed 's/old/new/g' file`)
- `awk` — xử lý theo cột (`awk '{print $1}'` in cột đầu)
- `cut`, `sort`, `uniq -c` — cắt cột, sắp xếp, đếm số lần xuất hiện
- `wc -l` — đếm số dòng
- `xargs` — lấy output của lệnh trước làm input cho lệnh sau

**Mẹo nhớ:** khi cần "lọc rồi đếm xem lỗi nào xảy ra nhiều nhất trong log", công thức kinh điển là `grep "ERROR" log | awk '{print $5}' | sort | uniq -c | sort -rn`. Đây là pattern dùng lại 80% các lần phân tích log bằng tay.

---

## 9. "Cần tự động hóa một việc lặp lại"

**Tình huống:** bạn vừa làm tay một việc 2-3 lần, nhận ra sẽ còn lặp lại.

**Cần biết gì:** bash script là bước đầu tiên, không cần ngôn ngữ phức tạp cho việc đơn giản. Khi logic phức tạp hơn (gọi API, xử lý JSON, retry logic) thì chuyển sang Python.

**Công cụ:**
- Bash script (`#!/bin/bash`, biến, if/for, exit code)
- `cron` — chạy job theo lịch (`crontab -e`)
- `systemd timer` — thay thế cron hiện đại hơn, có log qua journalctl
- Python với `subprocess`, `requests`, `argparse` cho script phức tạp hơn

**Mẹo nhớ:** nguyên tắc "rule of three" — làm tay 1 lần thì không cần tự động hóa, lần thứ 3 lặp lại thì bắt buộc viết script. Mọi script nên có exit code đúng (0 = thành công) để ghép vào pipeline sau này.

---

## 10. "Cần cài / update / gỡ phần mềm"

**Tình huống:** cần setup 1 công cụ mới trên server.

**Cần biết gì:** package manager khác nhau theo distro: Debian/Ubuntu dùng `apt`, RHEL/CentOS/Amazon Linux dùng `yum`/`dnf`.

**Công cụ:**
- `apt update && apt install <pkg>` (Ubuntu/Debian)
- `dnf install <pkg>` (RHEL/CentOS/Amazon Linux 2023)
- `apt list --installed` / `dnf list installed` — xem đã cài gì
- `which <cmd>`, `whereis <cmd>` — tìm binary đang dùng nằm ở đâu
- Với phần mềm không có trong repo: build từ source, hoặc dùng container (Docker) để tránh làm bẩn hệ thống

**Mẹo nhớ:** luôn `update` trước khi `install` để tránh cài bản cũ từ cache lỗi thời. Trên production, tránh `apt upgrade` toàn bộ hệ thống bất ngờ — luôn kiểm soát version cụ thể.

---

## 11. "Cần quản lý user / quyền hạn trên server"

**Tình huống:** thêm user mới, giới hạn quyền, hoặc setup SSH key.

**Công cụ:**
- `useradd`, `usermod`, `passwd`, `userdel`
- `/etc/sudoers` (sửa bằng `visudo`, không sửa trực tiếp) — cấp quyền sudo có kiểm soát
- SSH key: `~/.ssh/authorized_keys` trên server, không dùng password login cho production
- `groups <user>` — xem user thuộc group nào

**Mẹo nhớ:** nguyên tắc **least privilege** — mỗi user/service chỉ nên có quyền tối thiểu cần để hoạt động, không bao giờ chạy app bằng `root` trừ khi bắt buộc.

---

## 12. "Cần bảo mật cơ bản cho một con server"

**Tình huống:** vừa dựng server mới, cần harden trước khi để production truy cập.

**Công cụ & checklist:**
- Tắt SSH login bằng password, chỉ cho phép SSH key (`PasswordAuthentication no` trong `/etc/ssh/sshd_config`)
- Đổi port SSH mặc định hoặc dùng bastion/VPN (tùy chính sách)
- Firewall: chỉ mở port cần thiết (AWS Security Group, hoặc `ufw`/`iptables` trong máy)
- Cập nhật bản vá bảo mật định kỳ (`apt upgrade` có kiểm soát, hoặc dùng unattended-upgrades)
- Không chạy service bằng root nếu không cần
- `fail2ban` — tự động block IP brute-force SSH

**Mẹo nhớ:** bảo mật là lớp phòng thủ (defense in depth) — không dựa vào 1 biện pháp duy nhất, kết hợp firewall + SSH key + least privilege + patch định kỳ.

---

# PHẦN 2 — DEVOPS

## 13. "Cần quản lý version code, làm việc nhóm"

**Tình huống:** code cần theo dõi lịch sử thay đổi, nhiều người cùng sửa.

**Công cụ:** Git — `clone`, `branch`, `commit`, `merge`, `rebase`, `pull request`. Workflow phổ biến: tạo branch riêng cho mỗi feature/fix, merge qua pull request sau khi review.

**Mẹo nhớ:** `rebase` viết lại lịch sử (dùng cho branch cá nhân chưa push, giữ lịch sử sạch), `merge` giữ nguyên lịch sử cả 2 bên (dùng khi merge vào branch chung). Không rebase branch người khác đang dùng chung.

---

## 14. "Cần đóng gói app để chạy ở đâu cũng giống nhau"

**Tình huống:** app chạy được trên máy bạn nhưng lỗi trên server khác ("works on my machine").

**Cần biết gì:** container đóng gói app cùng toàn bộ dependency vào 1 image, chạy giống nhau ở mọi nơi có Docker.

**Công cụ:**
- `Dockerfile` — định nghĩa cách build image (base image, copy code, install dependency, lệnh chạy)
- `docker build`, `docker run`, `docker ps`, `docker logs`, `docker exec -it <container> bash`
- `docker-compose` — chạy nhiều container liên kết nhau (app + database + cache) bằng 1 file YAML
- Image nên nhỏ (dùng base image `alpine` hoặc `slim` khi phù hợp) và không chứa secret trong layer

**Mẹo nhớ:** container không phải VM — nó chia sẻ kernel với host, chỉ đóng gói filesystem và process, nên khởi động nhanh hơn VM rất nhiều nhưng cách ly kém hơn VM thật.

---

## 15. "Cần tự động build/test/deploy mỗi khi push code"

**Tình huống:** muốn mỗi lần push code tự động chạy test, build, deploy mà không cần làm tay.

**Cần biết gì:** đây là CI/CD — Continuous Integration (tự động test/build khi có code mới) và Continuous Deployment (tự động đưa code đã qua kiểm tra lên production/staging).

**Công cụ:**
- GitHub Actions / GitLab CI — định nghĩa pipeline bằng file YAML trong repo (`.github/workflows/*.yml`)
- Pipeline điển hình: push code → chạy test → build image → push image lên registry → deploy
- Secret trong CI (API key, credential) lưu ở "Secrets" của platform, không hard-code trong file YAML

**Mẹo nhớ:** CI trả lời câu hỏi "code mới có làm hỏng gì không" (test tự động), CD trả lời câu hỏi "code đã qua kiểm tra có tự lên production không". Có thể có CI mà không có CD (vẫn deploy tay), nhưng không nên có CD mà không có CI.

---

## 16. "Cần dựng hạ tầng (server, network, database...) bằng code"

**Tình huống:** tạo hạ tầng bằng tay qua AWS Console dễ sai, khó lặp lại, khó review.

**Cần biết gì:** Infrastructure as Code (IaC) — định nghĩa hạ tầng bằng file code, apply để tạo/sửa, có thể version control và review như code thường.

**Công cụ:**
- Terraform — viết file `.tf` định nghĩa resource (EC2, security group, VPC...), `terraform plan` xem trước thay đổi, `terraform apply` thực thi, `terraform destroy` xóa sạch
- Ansible — thiên về configuration management (cài đặt, cấu hình phần mềm trên server đã tồn tại) hơn là tạo hạ tầng mới
- State file của Terraform (`terraform.tfstate`) là nguồn sự thật về hạ tầng hiện tại — không sửa tay, không xóa

**Mẹo nhớ:** luôn chạy `terraform plan` trước `apply` và đọc kỹ phần sẽ bị thay đổi/xóa — đây là bước cứu bạn khỏi việc vô tình xóa production.

---

## 17. "Cần biết hệ thống có đang khỏe không, theo thời gian thực"

**Tình huống:** muốn biết app down trước khi user báo, hoặc cần xem xu hướng resource theo thời gian.

**Cần biết gì:** 3 trụ cột observability là **metrics** (số liệu theo thời gian, ví dụ CPU%), **logs** (sự kiện chi tiết), **traces** (theo dõi 1 request đi qua nhiều service).

**Công cụ:**
- CloudWatch (AWS) — dễ bắt đầu nếu đang dùng AWS, tích hợp sẵn với EC2
- Prometheus + Grafana — chuẩn mở, Prometheus thu thập metrics (pull model), Grafana vẽ dashboard
- Alerting — đặt ngưỡng (ví dụ CPU > 90% trong 5 phút) để tự động báo qua Slack/email/PagerDuty
- ELK stack (Elasticsearch, Logstash, Kibana) hoặc Loki — tập trung log từ nhiều server về 1 chỗ để search

**Mẹo nhớ:** alert tốt phải **actionable** — nếu alert bắn ra mà không biết phải làm gì, đó là alert thừa, nên xóa hoặc viết lại kèm hướng xử lý (runbook).

---

## 18. "Cần chạy nhiều container, tự scale, tự phục hồi khi container chết"

**Tình huống:** Docker đơn lẻ không đủ khi cần chạy hàng chục container, tự scale theo load, tự restart khi fail.

**Cần biết gì:** Kubernetes (K8s) là bộ điều phối (orchestrator) cho container — chỉ nên học sau khi đã nắm chắc Docker và networking cơ bản.

**Công cụ:**
- Khái niệm cốt lõi: Pod (1 hoặc nhiều container chạy cùng nhau), Deployment (quản lý số lượng Pod mong muốn), Service (expose Pod ra ngoài), Ingress (route traffic HTTP vào cluster)
- `kubectl get pods`, `kubectl logs`, `kubectl describe`, `kubectl apply -f file.yaml`
- Managed K8s (EKS trên AWS) giúp bớt phải tự quản lý control plane

**Mẹo nhớ:** đừng học K8s khi chưa cần — nếu hệ thống chỉ có vài service, Docker Compose hoặc vài EC2 là đủ. K8s giải quyết vấn đề scale và tự phục hồi ở quy mô lớn, mang theo độ phức tạp tương ứng.

---

## 19. "Cần quản lý secret/password/API key an toàn"

**Tình huống:** app cần connection string database, API key, nhưng không được hard-code trong code hoặc commit lên Git.

**Công cụ:**
- Environment variables cho development đơn giản
- AWS Secrets Manager / Parameter Store — lưu secret, app đọc qua API lúc chạy, có audit log ai đọc khi nào
- HashiCorp Vault — giải pháp mạnh hơn nếu multi-cloud hoặc cần rotate secret tự động
- `.gitignore` phải luôn chặn file `.env`, credential file — kiểm tra lại trước mỗi lần commit

**Mẹo nhớ:** nếu secret vô tình bị commit lên Git, xóa file trong commit mới KHÔNG đủ — secret vẫn còn trong lịch sử Git, phải revoke/rotate secret đó ngay lập tức, coi như đã bị lộ.

---

## 20. "Có sự cố xảy ra — quy trình xử lý"

**Tình huống:** alert bắn ra, hoặc user báo lỗi, hệ thống đang gặp vấn đề thật.

**Quy trình chuẩn (incident response):**
1. **Xác nhận và đánh giá mức độ** — có thật không, ảnh hưởng bao nhiêu user, có cần escalate không
2. **Ổn định trước, tìm nguyên nhân gốc sau** — nếu có cách rollback/restart nhanh để ngừng ảnh hưởng, làm trước khi đào sâu nguyên nhân
3. **Chẩn đoán** — dùng trình tự ở mục 1 (CPU/RAM/Disk/Network/Logs)
4. **Fix và xác nhận đã hết sự cố**
5. **Viết postmortem** — nguyên nhân gốc (root cause, không phải triệu chứng), timeline, cách phát hiện, cách đã fix, hành động để ngăn tái diễn

**Mẹo nhớ:** nguyên tắc "stop the bleeding first" — khôi phục dịch vụ luôn ưu tiên hơn hiểu rõ nguyên nhân ngay lúc đó. Hiểu sâu nguyên nhân là việc làm sau khi hệ thống đã ổn, trong lúc viết postmortem, không phải lúc đang cháy nhà.

---

# PHẦN 3 — Bản đồ tổng hợp (tra cứu nhanh)

| Muốn làm gì | Đi tìm ở đâu |
|---|---|
| Server chậm, chưa biết vì sao | `top`, `uptime`, `df -h`, `free -h` |
| CPU/RAM cao | `ps aux --sort=-%mem`, `dmesg \| grep -i oom` |
| Disk đầy | `df -h`, `df -i`, `du -sh`, logrotate |
| Service crash | `systemctl status`, `journalctl -u` |
| Mạng/DNS lỗi | `curl -v`, `dig`, `ss -tulnp` |
| Permission denied | `ls -la`, `ps aux \| grep`, user của process |
| Tìm nguyên nhân qua log | `journalctl --since`, `grep`/`awk`/`sed` |
| Tự động hóa việc lặp lại | bash script, cron/systemd timer |
| Cài phần mềm | `apt`/`dnf` |
| Đóng gói app | Docker, Dockerfile |
| Auto build/test/deploy | GitHub Actions/GitLab CI |
| Dựng hạ tầng bằng code | Terraform |
| Theo dõi hệ thống real-time | CloudWatch, Prometheus + Grafana |
| Scale nhiều container | Kubernetes |
| Lưu secret an toàn | AWS Secrets Manager / Vault |
| Có sự cố | stop the bleeding → chẩn đoán → fix → postmortem |

---

# Cách luyện để nhớ thật, không phải nhớ chữ

Đọc file này 1 lần không đủ. Cách để nó thành phản xạ: lên EC2, tự gây ra từng tình huống ở Phần 1 và Phần 2 (disk đầy thật, service crash loop thật, permission sai thật), rồi tự chẩn đoán chỉ dựa vào trí nhớ về "bản đồ tổng hợp" này, không mở lại file ngay. Khi bí mới tra. Lặp lại với tình huống khác nhau cho tới khi không cần tra nữa — đó là lúc kiến thức đã chuyển từ file này vào phản xạ của bạn.
