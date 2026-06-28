# Registration / Login data DB me kaise dikhe

## 1) Pehle Flask ke liye sahi table banao (ek hi baar)

MySQL Workbench me ye chalao (sirf **users** table drop, taake init_db dobara bana sake):

```sql
USE genspark_erp;
DROP TABLE IF EXISTS users;
```

Phir terminal me (vendor dashboard folder se):

```bash
cd "C:\Users\MMT\Desktop\vite-react.js\vendor dashboard"
python init_db.py
```

Isse `users` table sahi columns ke saath ban jayega (password_hash, role_id, must_change_password, etc.) aur default admin/vendor bhi add ho sakte hain.

---

## 2) Registration data dekhne ke liye query

Jab app se register/verify/login karo, phir MySQL Workbench me:

```sql
USE genspark_erp;

SELECT id, name, email, status, must_change_password, created_at
FROM users
ORDER BY id DESC
LIMIT 20;
```

Yahan sab users (manual + registration wale) dikhenge.

---

## 3) Sirf verified/active users

```sql
USE genspark_erp;

SELECT id, name, email, status, created_at
FROM users
WHERE status = 'active'
ORDER BY created_at DESC;
```
