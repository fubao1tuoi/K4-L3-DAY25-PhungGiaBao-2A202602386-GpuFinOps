# GPU FinOps Lab — Technical Write-up

**Sinh viên:** Phùng Gia Bảo — 2A202602386  
**Dữ liệu:** synthetic dataset, seed 25; đơn giá snapshot tháng 06/2026

## 1. Baseline và kết quả tối ưu

Pipeline phục vụ 7.533.027 token/ngày. Baseline giả định mọi request chạy trên model lớn,
không cache và không batch có chi phí **$48,87/ngày**, tương đương
**$6,488/1M-token**. Sau khi áp dụng model cascade, prompt caching và batch API, chi phí
còn **$8,48/ngày**, tương đương **$1,126/1M-token**, giảm **82,6%** cho inference.

Khi gộp inference và các workload GPU, baseline theo tháng là **$27.133**, optimized là
**$14.626**. Tổng tiền tiết kiệm dự kiến là **$12.507/tháng (46,1%)**.

| Đòn bẩy | Tiết kiệm/tháng | Nhận xét |
|---|---:|---|
| Purchasing (Spot/Reserved) | $10.040 | Lớn nhất; ghép loại cam kết với tính ổn định/khả năng gián đoạn của job |
| Inference (cascade/cache/batch) | $1.212 | Giảm đơn giá token mà không giảm traffic |
| Right-size util-lies | $655 | Loại bỏ năng lực tính toán đang trả tiền nhưng không chuyển thành FLOP hữu ích |
| Tắt GPU idle | $600 | Quick win, rủi ro thấp |

Purchasing đóng góp lớn nhất vì phần lớn baseline đến từ GPU-hours của workload dài hạn.
Spot phù hợp cho năm job có thể checkpoint/gián đoạn; Reserved phù hợp với ba workload
inference ổn định. Batch không nên dùng cho request tương tác nhạy latency.

## 2. GPU-Util lie và phân bổ chi phí

`gpu-h100-4` có GPU-Util **98,2%** nhưng MFU chỉ **19,4%**; `gpu-a10g-1` có
GPU-Util **96,9%** nhưng MFU **26,8%**. GPU-Util đo thời gian GPU có hoạt động, không đo
tỷ lệ FLOPS hữu ích. Memory stall, I/O wait hoặc kernel kém hiệu quả có thể làm GPU trông
rất bận dù hiệu suất tính toán thấp. Vì nhà cung cấp vẫn tính đủ GPU-hour, đây là vấn đề
chi phí thực tế. Ngoài ra, GPU idle làm thất thoát khoảng **$20/ngày, tức $600/tháng**.

Theo showback, `assistant` là team tốn nhiều nhất với **$2,59/ngày**, khoảng **30,6%**
tổng chi phí inference optimized. Tag coverage đạt **91,8%**, vượt gate 80%, nên dữ liệu
đủ để bắt đầu chargeback. FOCUS export giúp giữ cùng cấu trúc chi phí khi dùng nhiều nhà
cung cấp cloud.

## 3. Extension 4 — Ngân sách Reasoning

| Nhóm | Request | Token | Chi phí/ngày | Điện năng/ngày |
|---|---:|---:|---:|---:|
| Standard | 2.199 | 6.291.871 | $7,09 | 1.887,56 Wh |
| Reasoning | 201 | 1.241.156 | $1,40 | 29.787,74 Wh |

Reasoning chỉ chiếm **8,38% request** nhưng chiếm **16,46% chi phí optimized** và
**94,04% điện năng ước tính**. Phép tính năng lượng sử dụng hệ số 80× đã được cung cấp
trong `finops/sustainability.py`.

Ngưỡng đề xuất là tối đa 10% request. Dataset hiện đã dưới ngưỡng, nên savings đo được
khi áp cap là **$0 và 0 Wh**. Tôi không giả định giảm output hoặc đổi model để tạo savings
không có trong dữ liệu. Policy đề xuất là chỉ bật reasoning cho task phức tạp hoặc khi
confidence đã hiệu chỉnh thấp hơn threshold; theo dõi đồng thời chất lượng, chi phí và Wh.

## 4. Extension 5 — Carbon-aware Scheduling

Năm job `interruptible=1` tiêu thụ ước tính **1.789 kWh** trong đúng số ngày ghi ở
`workloads.csv`. Phép tính giữ nguyên workload và dùng `watts × GPU-hours`.

| Region | USD/kWh | gCO2/kWh | Chi phí điện | Carbon (kgCO2e) |
|---|---:|---:|---:|---:|
| us-east-1 | $0,120 | 380 | $214,68 | 679,82 |
| us-west-2 | $0,070 | 120 | $125,23 | 214,68 |
| europe-north1 | $0,090 | 30 | $161,01 | 53,67 |
| europe-central2 | $0,180 | 660 | $322,02 | 1.180,74 |
| us-east-wa | $0,055 | 90 | $98,39 | 161,01 |

Di chuyển các job đủ điều kiện từ `us-east-1` sang vùng sạch nhất `europe-north1` giảm
carbon từ **679,82 xuống 53,67 kgCO2e**, tiết kiệm **626,15 kgCO2e (92,1%)**.
`us-east-wa` lại là vùng có điện rẻ nhất. Vì vậy “tối ưu” phụ thuộc mục tiêu: carbon,
chi phí, latency tới người dùng và yêu cầu data residency. Không nên chuyển vùng chỉ dựa
trên một chỉ số.

## 5. Ba hành động ưu tiên cho NimbusAI

1. Triển khai Spot cho job checkpointable và Reserved cho workload ổn định; đây là lever
   có tác động tài chính lớn nhất trong dữ liệu.
2. Áp reasoning gate với cap 10%, alert theo tỷ trọng cost/energy và kiểm tra chất lượng
   trước mỗi lần hạ cap.
3. Tự động tắt GPU idle, right-size GPU có MFU thấp và lập lịch training interruptible ở
   vùng carbon thấp khi latency và governance cho phép.

Các con số là kết quả mô phỏng theo snapshot tháng 06/2026; cần re-baseline giá, carbon
intensity và interruption rate trước khi áp dụng vào production.
