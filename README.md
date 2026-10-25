# Đề 18 – Billing System

Ứng dụng Flask + PostgreSQL + pgAdmin + Nginx + Prometheus + Grafana + Loki + Promtail.

## Chạy trên Windows / Ubuntu có Docker Compose

1. Sao chép `.env.example` thành `.env`. **Đổi tất cả mật khẩu và SECRET_KEY**. Chỉ dùng mật khẩu URL-safe (chữ, số, `_`, `-`) cho POSTGRES_PASSWORD vì được dùng trong database URL.
2. Chạy `docker compose up -d --build`.
3. Khởi tạo bảng và tài khoản quản trị: `docker compose exec web flask --app main init-db`.
4. Truy cập:
   - Website: http://localhost:8080/login
   - pgAdmin: http://localhost:5050
   - Grafana: http://localhost:3001
   - Prometheus: http://localhost:9090/targets
5. Trong pgAdmin, thêm Server: Host `db`, Port `5432`, User/Password lấy từ `.env`.
6. Tạo khách hàng -> sản phẩm -> hóa đơn -> ghi nhận thanh toán -> in PDF qua trình duyệt.

## Giám sát

Grafana đã tự cấu hình hai data source: Prometheus và Loki. Tạo dashboard mới, thêm các panel PromQL:

- `up`
- `sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) by (name)`
- `sum(container_memory_working_set_bytes{name!=""}) by (name)`
- `pg_up`
- `probe_success`
- `sum(rate(flask_http_request_total[5m]))`

Kiểm tra tên metrics thực tế ở giao diện Prometheus trước khi thêm panel. Nếu cAdvisor không có dữ liệu trên Docker Desktop/VMware, xem log cAdvisor và điều chỉnh quyền mount phù hợp host.

## LogQL

Trong Grafana -> Explore -> Loki, thử:

- `{container=~".*web.*"}`
- `{container=~".*nginx.*"}`
- `count_over_time({container=~".*web.*"}[5m])`

Lưu ý: Promtail đã hết vòng đời hỗ trợ và chỉ được giữ để đáp ứng yêu cầu môn học; không nên dùng stack này nguyên trạng cho production.

## Bảo mật

- Web chạy user non-root (UID 10001), bỏ Linux capabilities và chặn privilege escalation.
- Tách `backend` internal network; database không publish port.
- Nginx có security headers.
- Password hash Werkzeug, session HTTPOnly/SameSite, CSRF token cho thao tác POST sau đăng nhập.
- Không commit `.env`.
- Cổng quản trị bind localhost.

**Giới hạn bản demo:** Chưa cấu hình HTTPS và TLS nội bộ; chỉ chạy trên máy local hoặc mạng thử nghiệm tin cậy. cAdvisor cần đặc quyền để đọc metrics Docker, Promtail được mount Docker socket read-only nhưng socket vẫn nhạy cảm. Nên bổ sung rate limiting, migrations, test tự động, backup, audit log và HTTPS trước khi triển khai Internet.

## Minh chứng / Git

- Commit 1: `git add app nginx compose.yaml .env.example .gitignore README.md && git commit -m "feat: billing app database and nginx reverse proxy"`
- Commit 2: `git add prometheus grafana compose.yaml README.md && git commit -m "feat: prometheus grafana monitoring"`
- Commit 3: `git add loki promtail compose.yaml README.md && git commit -m "feat: loki promtail centralized logging"`

Các commit trên là **mốc triển khai gợi ý**: tạo commit trong lúc phát triển thực tế, không khẳng định chúng đã tồn tại trong ZIP. Chụp màn hình Git log, các màn hình website, pgAdmin, Nginx headers, Prometheus targets, Grafana panels, Loki queries, lệnh kiểm tra hardening.

## Kiểm tra

`docker compose ps`

`curl -I http://localhost:8080/login`

`curl http://localhost:8080/health`

`docker compose logs --tail=50 web nginx prometheus loki promtail`

`docker compose exec web id`

`docker compose exec db pg_isready -U billing_user -d billing`

Thay username/db trong lệnh cuối nếu `.env` khác ví dụ.
## Monitoring System

The Billing application uses Prometheus, Grafana,
Loki, and Promtail for monitoring.

### Start monitoring services

```bash
docker compose up -d
```

### Monitoring URLs

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

### Verify monitoring

Open Prometheus and navigate to Status > Targets.

Check that the monitoring targets are UP.

Open Grafana and select the
Billing System Monitoring dashboard.