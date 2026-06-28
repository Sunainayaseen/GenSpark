# GenSpark – Admin & Vendor Dashboard Guide

Yeh guide batati hai **Admin** aur **Vendor** dashboard kis tarah kaam karte hain aur kaun kya kar sakta hai.

---

## Order flow (status) – sab ke liye same

Har order in steps se guzarta hai:

| Status      | Matlab |
|------------|--------|
| **pending**   | Order bana, abhi kisi vendor ne accept nahi kiya |
| **accepted**  | Vendor ne order accept kar liya |
| **assembly**  | Vendor PC assemble kar raha hai |
| **qa**        | Assembly complete, admin QA check karega |
| **shipped**   | QA pass, vendor ne ship kar diya |
| **delivered** | Delivery complete |

---

## 1. Admin dashboard – kaise kaam karta hai

**Login:** `admin@genspark.com` / `admin123`  
**URL:** `/admin/` ya `/admin/dashboard`

### Admin kya dekh sakta hai (Dashboard pe)

- **Total Users** – saare registered users
- **Vendors** – total vendor count
- **Total Orders** – saari orders
- **Revenue** – shipped/delivered orders ka total amount
- **Quick Stats** – Components, PC Builds, Pending Orders, Approved Vendors
- **Workflow** – short summary: Customer → Order → Vendor → QA → Ship

### Admin sidebar – sections

| Menu        | Kaam |
|------------|------|
| **Dashboard** | Overview numbers + workflow |
| **Users**     | Saare users list, kisi ko Active/Blocked karna |
| **Vendors**   | Saare vendors, **Approve** / **Block** (pending vendors ko approve karo) |
| **Categories**| Component categories (Processor, RAM, GPU, etc.) add/edit |
| **Components**| Inventory components add/edit |
| **PC Builds** | Predefined builds (Gaming/Office etc.) add/edit |
| **Orders**    | Saari orders list + har order ka detail |
| **QA**        | Jo orders **assembly** ya **qa** status mein hain – admin **Pass** / **Fail** karta hai (Pass = shipped, Fail = wapas assembly) |
| **Payments**  | Saare payments list |
| **Reports**   | Revenue, orders by status, top vendors – analytics |

### Admin order flow (short)

1. Orders list se koi bhi order dekh sakta hai (customer, vendor, amount, status).
2. QA section mein assembly/qa wali orders dikhti hain – admin **Pass** ya **Fail** karta hai.
3. Pass → order **shipped** ho jati hai (vendor ship karega).
4. Fail → order wapas **assembly** (vendor fix karke phir QA bhejega).

---

## 2. Vendor dashboard – kaise kaam karta hai

**Login:** Vendor apni email/password se (e.g. `vendor@genspark.com` / `vendor123`)  
**URL:** `/vendor/` ya `/vendor/dashboard`

### Pehli baar vendor (approval se pehle)

- Agar vendor **approved** nahi hai: dashboard pe sirf message dikhega – *“Vendor account pending approval”* + **Edit Profile** link.
- **My Profile** se shop name, city, address, phone bhar kar save karo → admin **Vendors** list se **Approve** karega.
- Approve ke baad vendor ko email bhi ja sakti hai (agar mail config ki hui ho).

### Approve ke baad – Vendor kya dekh sakta hai (Dashboard)

- **Total Orders** – aapke assigned orders
- **Pending** – aapke pending orders
- **In Assembly** – accepted/assembly wali orders
- **Earnings** – completed payments ka total (Rs. / PKR)
- **Quick Stats** – completed (shipped/delivered) count + **Manage Inventory** link

### Vendor sidebar – sections

| Menu         | Kaam |
|-------------|------|
| **Dashboard** | Overview (orders, pending, assembly, earnings) |
| **My Profile**| Shop name, city, address, phone edit + **Delete account** option |
| **Inventory** | Apne components (quantity, price) add/edit – admin ke components mein se select karke |
| **Orders**    | **Assigned orders** (aapke) + **Available to accept** (unassigned pending) – yahan **Accept** se order aapke paas assign hota hai |
| **Assembly**  | Jo orders **accepted** ya **assembly** mein hain – yahan **Update Assembly** se stage (in_assembly → testing → completed) + notes |
| **Shipment**  | Jo orders **qa** (QA pass) ho chuki hain – yahan **Mark Shipped** / shipment form |
| **Earnings**  | Aapke earnings summary |

### Vendor order flow (step by step)

1. **Orders** → **Available to accept** se koi **pending** order choose karo → **Accept** click.
2. Order aapke **Assigned orders** mein aa jata hai, status **accepted**.
3. **Assembly** → us order pe **Update Assembly** → stage update (e.g. in_assembly → testing → **completed**).  
   **Completed** select karoge to order **qa** status mein chala jata hai (admin QA karega).
4. Admin **QA** mein **Pass** karega → order **shipped** status mein.
5. **Shipment** list mein woh order aayega → **Mark Shipped** / shipment form bharo.
6. **Earnings** mein completed payments ka total dikhega.

### Vendor extra options

- **My Profile** ke neeche **Delete my account** – permanent account delete (confirm page + checkbox). Isse vendor + user delete ho jata hai, orders unassign ho jati hain.

---

## 3. Flow summary – ek line mein

- **Admin:** Vendors approve karta hai, inventory (categories, components, builds) manage karta hai, saari orders dekhta hai, **QA** Pass/Fail karta hai, **Reports** dekhta hai.
- **Vendor:** Pending orders **Accept** karta hai, **Assembly** update karta hai (completed = QA ke liye), **QA pass** ke baad **Shipment** mark karta hai, apna **Inventory** aur **Earnings** manage karta hai; zarurat ho to **account delete** bhi kar sakta hai.

---

## 4. Quick reference – URLs

| Role   | Dashboard URL        | Login URL     |
|--------|----------------------|---------------|
| Admin  | `/admin/`            | `/auth/login`  |
| Vendor | `/vendor/`            | `/auth/login`  |
| Home   | `/` (landing)         | –             |

Default logins:

- Admin: `admin@genspark.com` / `admin123`
- Vendor: `vendor@genspark.com` / `vendor123` (agar `init_db.py` se seed kiya ho)

---

## 5. Flask "not working" / "invalid response" fix

1. **KILL-PORT-5000.bat** double-click karo (sab processes port 5000 band).
2. **START-FLASK.bat** double-click karo – **sirf ek window** open rahe.
3. Browser me open karo: **http://127.0.0.1:5000** ya **http://127.0.0.1:5000/api/health** – "OK" ya GenSpark page dikhna chahiye.
4. Agar ab bhi na chale: **CHECK-FLASK.bat** chalao – agar "OK" print ho to app theek hai; phir step 1–2 dobara karo.
5. DB ke bina test: `python run_simple.py` – sirf "OK" wala minimal server; agar ye chal jaye to issue main app/DB me hai.
