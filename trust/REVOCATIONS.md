# Revocations log

Mỗi khi một reviewer bị revoke (status đổi từ `active` → `revoked`
trong `reviewers.json`), thêm entry vào đây.

**Không xoá entry khỏi file này** (nguyên tắc 5).

Format:

```markdown
## <handle> — <ngày revoke>

- PR: <link>
- Quorum: <list handle của reviewer đã approve revoke>
- Lý do: <ngắn gọn, không doxx, không phán xét cá nhân>
- Ảnh hưởng: <N review cũ của reviewer này; reader có thể tự cân nhắc>
```

---

*(Chưa có revocation nào. File này được tạo sẵn để phản ánh commitment
về minh bạch, không phải vì đã có sự cố.)*
