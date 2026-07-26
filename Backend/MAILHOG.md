# MailHog se local email check karna

MailHog ek **local fake SMTP server** hai. Jab app user ko one-time password wali email "bhejti" hai, woh email asli inbox (Gmail etc.) mein **nahi** jati – MailHog use **catch** karta hai aur aap **http://localhost:8025** par browser mein dekh sakte ho. Development/testing ke liye yehi se email "get" hoti hai.

## 1. MailHog chalao

**Windows (PowerShell / CMD):**
```bash
# Agar MailHog executable path pe hai
MailHog.exe
```
Ya double-click `MailHog.exe` (jahan bhi install kiya ho).

**Chocolatey se install kiya ho to:**
```powershell
mailhog
```

Web UI: **http://localhost:8025**  
SMTP: **localhost:1025** (port 1025)

## 2. Flask ke liye .env set karo

`vendor dashboard` folder mein `.env` file kholo aur email wale variables MailHog ke hisaab se set karo:

```env
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=0
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@genspark.local
```

- **MAIL_USE_TLS=0** zaroori hai (MailHog TLS use nahi karta).
- **MAIL_USERNAME** aur **MAIL_PASSWORD** khali chhod do (MailHog auth nahi leta).

## 3. Flask run karo

```bash
cd "vendor dashboard"
python run.py
```

## 4. Email trigger karo

- Admin panel kholo → **Users** → **Add User** (name, email, role) → Save  
  ya  
- **Vendors** → **Add Vendor** (name, email, shop name, …) → Save  

Jo email aapne form mein dala (e.g. `test@example.com`), usi par “one-time password” wali email bheji jayegi – lekin actually woh MailHog mein catch ho jayegi.

## 5. Email dekhna

Browser mein jao: **http://localhost:8025**

- Inbox mein woh email dikhegi (subject: “GenSpark – Your User/Vendor account & one-time password”).
- Click karke body, HTML, one-time password sab dekh sakte ho.

---

**Short:** MailHog on (port 1025) → .env mein `MAIL_SERVER=localhost`, `MAIL_PORT=1025`, `MAIL_USE_TLS=0` → Flask run → Add User/Vendor → http://localhost:8025 pe email check karo.
