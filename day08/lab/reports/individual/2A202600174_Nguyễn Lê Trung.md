# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Lê Trung  
**Vai trò trong nhóm:** Documentation Owner  
**Ngày nộp:** 13/4/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Em đảm nhiệm vai trò Documentation Owner, tập trung chủ yếu ở Sprint 4 và hỗ trợ ghi nhận kết quả từ các sprint trước. Em hoàn thiện tài liệu `architecture.md` để mô tả tổng quan hệ thống RAG, gồm luồng indexing từ raw docs, preprocess, chunking, embedding, lưu vào ChromaDB, sau đó retrieval và generation trong `rag_answer.py`. Em cũng bổ sung sơ đồ Mermaid cho hai luồng retrieval: baseline dense và variant hybrid. Ngoài ra,em cập nhật `tuning-log.md` bằng kết quả evaluation thực tế: baseline dense và variant hybrid đều đạt Faithfulness 4.50, Relevance 4.20, Context Recall 5.00 và Completeness 3.80. Công việc của em kết nối phần implement của nhóm với báo cáo cuối, giúp giải thích rõ quyết định kỹ thuật và kết quả scorecard.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, em hiểu rõ hơn vòng lặp evaluation trong RAG. Ban đầu em nghĩ nếu đổi từ dense sang hybrid thì điểm sẽ tăng rõ, vì hybrid kết hợp semantic search và keyword search. Tuy nhiên kết quả cho thấy variant hybrid không cải thiện điểm trung bình so với baseline. Điều này giúp em hiểu rằng retrieval strategy chỉ là một biến trong pipeline; nếu dữ liệu không có đủ evidence, hoặc answer thiếu chi tiết, điểm vẫn không tăng. Em cũng hiểu rõ hơn về citation trong context: số `[1]`, `[2]` là thứ tự chunk được đưa vào prompt, không phải thứ tự source file. Vì vậy có trường hợp log chỉ hiện context `[1]`, nhưng answer cite `[2]` do prompt thật có nhiều chunk hơn phần preview.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều em ngạc nhiên nhất là variant hybrid không tạo ra chênh lệch điểm so với baseline, dù lý thuyết hybrid phù hợp với corpus có cả policy tự nhiên và keyword như SLA, P1, Level 3, ERR-403, Approval Matrix. Baseline đã có Context Recall 5.00 nên retrieval nhìn chung không phải điểm nghẽn lớn nhất. Một khó khăn khác là phân tích output citation: câu hỏi "Ai phải phê duyệt để cấp quyền Level 3?" ở baseline trả lời đúng nhưng cite `[2]`, trong khi log chỉ hiện context `[1]`. Sau khi đọc `rag_answer.py`, em hiểu nguyên nhân là verbose chỉ in `prompt[:500]`, còn LLM vẫn nhận full context. Ngoài ra, lỗi q09 cho thấy không phải lúc nào tuning retrieval cũng giải quyết được nếu tài liệu thiếu thông tin về mã lỗi.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q07 - Approval Matrix để cấp quyền hệ thống là tài liệu nào?

**Phân tích:**

Đây là câu hỏi thú vị vì nó kiểm tra khả năng xử lý alias. Trong tài liệu `access_control_sop.txt`, phần ghi chú nói tài liệu này trước đây có tên "Approval Matrix for System Access". Baseline dense trả lời đúng hướng rằng Approval Matrix liên quan đến tài liệu quy trình cấp quyền hệ thống, nguồn là `it/access-control-sop.md`. Điểm của baseline là Faithfulness 5, Relevance 5, Context Recall 5 nhưng Completeness chỉ 2. Điều này nghĩa là answer không bịa và retrieve đúng source, nhưng câu trả lời chưa đủ hoàn chỉnh vì chưa nêu rõ alias cũ và tên tài liệu hiện tại là Access Control SOP.

Variant hybrid cũng không cải thiện câu này, điểm vẫn là 5/5/5/2. Nguyên nhân chính không nằm ở context recall vì expected source đã được retrieve, mà nằm ở generation hoặc prompt: model trả lời quá chung, chưa khai thác đầy đủ evidence trong chunk. Nếu muốn cải thiện, em nghĩ nên điều chỉnh prompt để yêu cầu trả lời rõ "tên hiện tại" và "tên cũ/alias" khi context có ghi chú đổi tên.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, em sẽ thử query transform dạng expansion cho các câu có alias như q07, ví dụ mở rộng "Approval Matrix" thành "Access Control SOP" và "Approval Matrix for System Access". Em cũng muốn chỉnh grounded prompt để yêu cầu trả lời đầy đủ hơn khi context có điều kiện, ngoại lệ hoặc tên cũ của tài liệu. Lý do là scorecard cho thấy Context Recall đã cao, nhưng Completeness vẫn thấp ở q04 và q07.

---
