# Khắc phục ảnh sản phẩm – Billing18

## Đã sửa
- Dùng chung Docker named volume `billing18_product_images` cho Web (ghi) và Nginx (đọc).
- Thêm kiểm tra nội dung ảnh PNG/JPEG/WEBP, lưu bằng tên UUID và thông báo lỗi ghi file.
- Nâng giới hạn upload Flask + Nginx lên 10 MB.
- Giữ nguyên dữ liệu PostgreSQL, các chức năng còn lại và tên trường `image_filename`.

## Cài đặt trên Windows (PowerShell hoặc Terminal VS Code)
1. Sao lưu dự án và database trước khi thay đổi. **Không chạy `docker compose down -v`**.
2. Giải nén, dùng file dự án đã sửa (không ghi đè `.env` đang sử dụng nếu khác).
3. Trong thư mục billing18, chạy:

```powershell
docker compose config --quiet
```

4. Nếu volume cũ đã tồn tại nhưng thuộc root, cấp quyền cho UID 10001 bằng container tạm. Lệnh này chỉ đổi quyền, không xóa file:

```powershell
docker run --rm -v billing18_product_images:/images alpine:3.20 chown -R 10001:10001 /images
```

5. Tạo lại Web và Nginx:

```powershell
docker compose up -d --build --no-deps --force-recreate web nginx
```

6. Kiểm tra quyền ghi:

```powershell
docker compose exec web sh -c "touch /app/static/uploads/products/test.txt && rm /app/static/uploads/products/test.txt"
```

7. Vào `http://localhost:8080/products`, chọn Sửa sản phẩm, chọn ảnh PNG/JPG/WEBP nhỏ hơn 10 MB, Lưu sửa. Kiểm tra:

```powershell
docker compose exec web ls -lah /app/static/uploads/products
docker compose exec nginx ls -lah /app/static/uploads/products
```

Nếu vẫn lỗi, kiểm tra:

```powershell
docker compose logs --tail=100 web nginx
```

## Về ảnh cũ
**File ZIP được gửi không chứa bất kỳ file ảnh sản phẩm nào**. Việc sửa code không thể tự khôi phục ảnh đã mất. Tên file trong database vẫn được giữ; có thể khôi phục từ backup hoặc tải lại ảnh qua chức năng Sửa sản phẩm.

## Ghi chú
Cảnh báo `volume already exists but was not created by Docker Compose` không ngăn volume hoạt động. Nếu cần loại bỏ cảnh báo có thể khai báo volume là external, nhưng không bắt buộc. Không xóa volume hoặc database.
