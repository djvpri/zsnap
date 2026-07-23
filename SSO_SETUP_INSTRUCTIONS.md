# ZSnap — Setup Login SSO Z One (instruksi untuk Claude di laptop)

> Ditulis 2026-07-23. Konteks: **cara login ZSnap diubah dari license key → SSO Z One**.
> Semua user yang punya akun **Z One** boleh pakai (gating paket/Midtrans dilewati; kode
> license lama tetap ada sebagai fallback). Perubahan sudah ada di branch `main`
> (`git pull` dulu).

## Apa yang berubah (sudah di-commit)
- **Backend `main.py`** (FastAPI, Railway): endpoint baru `GET /desktop-login` & `GET /sso`
  (SSO Z One via browser + loopback), token sesi ZSnap (JWT HS256 stdlib), dan
  `/process-image` kini menerima header `Authorization: Bearer <token>` (user Z One → boleh,
  tanpa kuota). License key lama masih diterima sebagai fallback.
- **Desktop `zomet5.py`** (PyQt6): dialog license diganti **login SSO** (buka browser →
  loopback tangkap token → simpan ke `~/.zsnap_token`, auto-login 30 hari). Request pakai
  Bearer token. Heartbeat/HWID license dihapus.

Ada **3 bagian** yang harus dikerjakan: (A) rebuild .exe, (B) env backend Railway,
(C) daftarkan app di Z One. Ketiganya perlu agar login jalan.

---

## A. Rebuild aplikasi desktop (.exe)

**Prasyarat:** Windows + Python 3.11/3.12 (hindari 3.13+ kalau wheel PyQt6 belum ada).
`build.bat` sudah otomatis meng-install dependency (pyinstaller, pyqt6, requests, mss, pillow).

```powershell
cd <path>\zsnap
git pull origin main
# Tutup ZOMET.exe kalau sedang berjalan
.\build.bat
```

- Output: **`dist\ZOMET.exe`** (single-file, windowed, icon `zomet.ico`).
- Entry point = `zomet5.py`, spec = `zomet.spec` (jangan diubah).

**Uji cepat setelah build** (butuh backend & Z One sudah siap — bagian B & C):
1. Jalankan `dist\ZOMET.exe` → muncul info "Login diperlukan" → **browser terbuka**.
2. Login Z One (kalau belum) → browser menampilkan "Login berhasil" → aplikasi lanjut.
3. Snap area layar berisi soal → jawaban muncul.

---

## B. Backend (Railway — service ZSnap)

Set **Environment Variables** (Railway → service → Variables):
- `CROSS_APP_SECRET` = **sama persis** dengan nilai di Z One (WAJIB, untuk verifikasi token SSO).
- `NEXT_PUBLIC_ZONE_URL` = `https://zone.zomet.my.id`
- (opsional) `ZSNAP_JWT_SECRET` = biarkan kosong → default pakai `PROCESS_SECRET`.

Lalu **redeploy**. Pastikan endpoint hidup:
- `GET https://<backend>/` → `{"status":"online"}`
- `GET https://<backend>/desktop-login?port=12345` → harus **redirect** ke Z One SSO.

> Catatan: `<backend>` = origin FastAPI, mis. `https://zomet-production.up.railway.app`.
> Ini harus sama dengan host di `BASE_URL`/`BACKEND` pada `zomet5.py`.

---

## C. Z One — daftarkan app `zsnap`

`/api/sso/zsnap` di Z One mengambil **URL app dari database**, jadi app harus terdaftar:

1. Buka Z One **`/manage`** (atau admin app).
2. Tambah/registrasi app dengan:
   - **slug** = `zsnap`
   - **url** = origin backend FastAPI (tempat `/sso` berada), mis.
     `https://zomet-production.up.railway.app`
3. (opsional) Tambah `zsnap` ke `SSO_ENABLED_SLUGS` di `src/app/dashboard/page.tsx` **hanya**
   kalau mau ikon launcher di dashboard Z One — tidak wajib untuk login desktop
   (desktop memanggil `/api/sso/zsnap` langsung).

Alur token: desktop → `{backend}/desktop-login` → `{zone}/api/sso/zsnap` (user login) →
`{backend}/sso?token=` → loopback `127.0.0.1:<port>/callback?token=` → desktop simpan token.

---

## Gotcha / troubleshooting
- **Browser mendarat di halaman login Z One lalu berhenti** → user belum punya sesi Z One.
  Login dulu di `zone.zomet.my.id`, lalu jalankan ulang login dari aplikasi. (Keterbatasan v1.)
- **"Token SSO tidak valid"** di halaman `/sso` → `CROSS_APP_SECRET` backend ≠ Z One, atau
  app `zsnap` belum terdaftar / url salah.
- **Desktop tak menerima token** → cek firewall tak memblokir server loopback lokal
  (`127.0.0.1`), atau pakai fallback: halaman `/sso` menampilkan token untuk disalin manual.
- **401 saat snap** → token kedaluwarsa (30 hari): hapus `~/.zsnap_token` atau tutup–buka
  aplikasi untuk login ulang.
- Reset login: hapus file `%USERPROFILE%\.zsnap_token`.

## Distribusi
Kirim `dist\ZOMET.exe`. Pengguna cukup punya akun Z One → jalankan → login sekali.
