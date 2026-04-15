# Thư mục này chứa DỮ LIỆU MẪU HƯ CẤU

**Không phải là ký ức thật.** Các file JSON trong thư mục này được sinh
ra cho mục đích **minh hoạ pipeline** và **chạy test**. Nội dung hoàn
toàn hư cấu:

- Sự kiện "Lũ làng A" không có thật.
- Ba người kể (witness, authority, victim) không có thật.
- Tất cả chi tiết thời gian, địa điểm, nhân vật đều là tưởng tượng.

## Vì sao có thư mục này?

Một dự án về ký ức lịch sử cần có cách **kiểm chứng pipeline** mà không
phải đụng vào dữ liệu ký ức thật (vì ký ức thật là bất biến — không thể
sửa để test). Ba memory mẫu ở đây dùng để:

1. Chạy `generate_historical_entry()` và xem output có hợp lý không.
2. Test integration trong CI.
3. Giúp người mới đóng góp hiểu cấu trúc một memory thật sẽ như thế nào.

## Quy ước

- Mọi `event_id` mẫu đều có hậu tố `-demo` hoặc `-example-` để dễ phân
  biệt với event thật.
- `_index.json` có cờ `"is_sample_data": true`.
- Khi engine tổng hợp lịch sử, sample data **sẽ được bao gồm** — nên nếu
  bạn triển khai instance thật, hãy xoá thư mục `*-demo` này trước.
