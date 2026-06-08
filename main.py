import os
import random
import string
import smtplib
import threading
import hashlib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from db import SessionLocal, engine
from model import Base, License, UsageLog, Transaction
from license_service import calculate_expiry

Base.metadata.create_all(bind=engine)

# Tambah kolom baru jika belum ada (untuk upgrade database lama)
with engine.connect() as conn:
    for ddl in [
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS notes VARCHAR",
        "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
    ]:
        try:
            conn.execute(__import__("sqlalchemy").text(ddl))
            conn.commit()
        except Exception:
            pass

# =========================================================
# CONFIG
# =========================================================

API_SECRET     = os.getenv("API_SECRET", "rahasia-dari-desktop-ke-server")
PROCESS_SECRET = os.getenv("PROCESS_SECRET", "zomet-secret-2026")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SMTP_USER  = os.getenv("SMTP_USER")   # Gmail address, e.g. you@gmail.com
SMTP_PASS  = os.getenv("SMTP_PASS")   # Gmail App Password (16 chars)
NOTIFY_TO  = os.getenv("NOTIFY_TO", SMTP_USER)  # recipient, defaults to sender

MIDTRANS_SERVER_KEY   = os.getenv("MIDTRANS_SERVER_KEY", "")
MIDTRANS_CLIENT_KEY   = os.getenv("MIDTRANS_CLIENT_KEY", "")
MIDTRANS_IS_PRODUCTION = os.getenv("MIDTRANS_IS_PRODUCTION", "false").lower() == "true"

MIDTRANS_BASE = (
    "https://app.midtrans.com" if MIDTRANS_IS_PRODUCTION
    else "https://app.sandbox.midtrans.com"
)

PRICES = {
    "daily":   80000,
    "weekly":  130000,
    "monthly": 210000,
    "yearly":  650000,
}

# =========================================================
# APP
# =========================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# DEPENDENCIES
# =========================================================

def verify_token(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Akses ditolak")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================================================
# HELPERS
# =========================================================

USAGE_LIMITS = {
    "demo":    5,
    "daily":   100,
    "weekly":  700,
    "monthly": 3000,
    "yearly":  999999
}

def generate_license_key(plan: str = ""):
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(random.choices(chars, k=6)) for _ in range(3)]
    prefix = plan.upper() if plan else "ZOMET"
    return prefix + "-" + "-".join(parts)

def send_demo_notification(phone: str, license_key: str):
    if not SMTP_USER or not SMTP_PASS or not NOTIFY_TO:
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "🎉 Demo Baru - ZOMET AI"
            msg["From"]    = SMTP_USER
            msg["To"]      = NOTIFY_TO

            now = datetime.now().strftime("%d %b %Y %H:%M:%S")
            body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#222;">
  <h2 style="color:#00dcb4;">Demo License Baru</h2>
  <table>
    <tr><td><b>Waktu</b></td><td>: {now}</td></tr>
    <tr><td><b>No. HP</b></td><td>: {phone}</td></tr>
    <tr><td><b>License Key</b></td><td>: <code>{license_key}</code></td></tr>
  </table>
</body></html>"""

            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.sendmail(SMTP_USER, NOTIFY_TO, msg.as_string())
        except Exception as e:
            print("Email notification failed:", e)

    threading.Thread(target=_send, daemon=True).start()


def send_license_email(to_email: str, license_key: str, plan: str):
    if not SMTP_USER or not SMTP_PASS:
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Your ZOMET AI License Key"
            msg["From"]    = SMTP_USER
            msg["To"]      = to_email

            body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#222;max-width:520px;margin:auto;">
  <h2 style="color:#00dcb4;">ZOMET AI — License Key</h2>
  <p>Thank you for purchasing ZOMET AI!</p>
  <table style="margin:12px 0;">
    <tr><td><b>Plan</b></td><td>: {plan.capitalize()}</td></tr>
  </table>
  <p><b>Your License Key:</b></p>
  <div style="background:#111;color:#00dcb4;padding:16px;font-family:monospace;
              font-size:1.15rem;letter-spacing:3px;border-radius:8px;word-break:break-all;">
    {license_key}
  </div>
  <p style="margin-top:20px;">
    Download ZOMET.exe at
    <a href="https://zomet.my.id" style="color:#00dcb4;">zomet.my.id</a>
  </p>
  <hr style="border-color:#eee;margin:24px 0;">
  <p style="font-size:.85rem;color:#999;">
    Need help? Contact us via
    <a href="https://wa.me/6282153533164" style="color:#00dcb4;">WhatsApp</a>.
  </p>
</body></html>"""

            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.sendmail(SMTP_USER, to_email, msg.as_string())
        except Exception as e:
            print("License email failed:", e)

    threading.Thread(target=_send, daemon=True).start()

# =========================================================
# REQUEST MODELS
# =========================================================

class LicenseRequest(BaseModel):
    license_key: str
    hwid: str = None

class CreateLicenseRequest(BaseModel):
    license_key: str
    plan: str

class BulkCreateRequest(BaseModel):
    plan: str
    quantity: int

class BulkDeleteRequest(BaseModel):
    license_keys: list[str]

class DemoClaimRequest(BaseModel):
    phone: str

class PaymentRequest(BaseModel):
    plan: str
    email: str

# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():
    return {"status": "online", "app": "Zomet API"}

# =========================================================
# CLAIM DEMO (PUBLIC)
# =========================================================

@app.post("/claim-demo")
def claim_demo(data: DemoClaimRequest, db=Depends(get_db)):
    phone = data.phone.strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    # Cek apakah nomor ini sudah pernah klaim demo
    existing = db.query(License).filter(
        License.plan == "demo",
        License.notes == phone
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Phone number already claimed a demo license")

    key = generate_license_key("demo")

    lic = License(
        license_key=key,
        plan="demo",
        expires_at=None,
        usage_limit=USAGE_LIMITS.get("demo", 5),
        notes=phone
    )

    db.add(lic)
    db.add(UsageLog(
        license_key=key,
        plan="demo",
        event="demo_claim",
        notes=phone
    ))
    db.commit()

    send_demo_notification(phone, key)

    return {"license_key": key}

# =========================================================
# PROCESS IMAGE
# =========================================================

@app.post("/process-image")
async def process_image(request: Request, db=Depends(get_db)):

    try:
        data = await request.json()

        image_base64 = data.get("image")
        license_key  = data.get("license_key")
        hwid         = data.get("hwid")

        if not image_base64:
            raise HTTPException(status_code=400, detail="Image not found")

        if not license_key:
            raise HTTPException(status_code=401, detail="License key required")

        # Validasi license
        lic = db.query(License).filter(License.license_key == license_key).first()
        if not lic:
            raise HTTPException(status_code=403, detail="License not found")
        if not lic.active:
            raise HTTPException(status_code=403, detail="License inactive")
        if lic.expires_at and datetime.now().date() > lic.expires_at:
            raise HTTPException(status_code=403, detail="License expired")
        if lic.hwid and hwid and lic.hwid != hwid:
            raise HTTPException(status_code=403, detail="Device not authorized")
        if lic.usage_count >= lic.usage_limit:
            raise HTTPException(status_code=403, detail="Usage limit reached")

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/gemini-2.5-flash:generateContent"
            f"?key={GEMINI_API_KEY}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Anda adalah AI OCR dan pembaca soal.\n\n"
                                "Jika soal pilihan ganda:\n"
                                "- pilih jawaban terbaik\n"
                                "- jelaskan singkat maksimal 1 kalimat\n\n"
                                "Jika coding:\n"
                                "- jelaskan error\n"
                                "- beri solusi\n\n"
                                "Jangan mendeskripsikan gambar.\n"
                                "Langsung jawab inti."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ]
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, json=payload)

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        # Increment usage setelah Gemini berhasil
        if license_key and response.status_code == 200:
            lic = db.query(License).filter(License.license_key == license_key).first()
            if lic:
                lic.usage_count += 1
                db.add(UsageLog(
                    license_key=license_key,
                    plan=lic.plan,
                    event="process_image",
                    notes=hwid
                ))
                db.commit()

        return response.json()

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================================================
# VERIFY LICENSE
# =========================================================

@app.post("/verify-license")
def verify(data: LicenseRequest, db=Depends(get_db)):

    lic = db.query(License).filter(
        License.license_key == data.license_key
    ).first()

    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    if not lic.active:
        return {"valid": False, "reason": "license inactive"}

    if lic.expires_at and datetime.now().date() > lic.expires_at:
        return {"valid": False, "reason": "expired"}

    # Transfer device: update HWID to new device, kicking the old one
    lic.hwid = data.hwid

    db.commit()

    return {
        "valid": True,
        "plan": lic.plan,
        "expires_at": str(lic.expires_at),
        "usage_count": lic.usage_count,
        "usage_limit": lic.usage_limit
    }

# =========================================================
# HEARTBEAT (cek apakah device masih aktif)
# =========================================================

@app.post("/heartbeat")
def heartbeat(data: LicenseRequest, db=Depends(get_db)):
    lic = db.query(License).filter(
        License.license_key == data.license_key
    ).first()

    if not lic or not lic.active:
        return {"valid": False, "reason": "license inactive"}

    if lic.expires_at and datetime.now().date() > lic.expires_at:
        return {"valid": False, "reason": "expired"}

    if lic.hwid != data.hwid:
        return {"valid": False, "reason": "device transferred"}

    return {"valid": True}

# =========================================================
# INCREMENT USAGE
# =========================================================

@app.post("/increment-usage", dependencies=[Depends(verify_token)])
def increment(data: LicenseRequest, db=Depends(get_db)):

    lic = db.query(License).filter(
        License.license_key == data.license_key
    ).first()

    if not lic:
        raise HTTPException(status_code=404, detail="Not found")

    if lic.plan == "demo" and lic.usage_count >= lic.usage_limit:
        return {"valid": False, "reason": "demo limit reached"}

    lic.usage_count += 1
    db.commit()

    return {"success": True, "usage_count": lic.usage_count}

# =========================================================
# LIST LICENSES (ADMIN)
# =========================================================

@app.get("/list-licenses", dependencies=[Depends(verify_token)])
def list_licenses(db=Depends(get_db)):
    licenses = db.query(License).all()
    return [
        {
            "license_key": lic.license_key,
            "plan": lic.plan,
            "hwid": lic.hwid,
            "expires_at": str(lic.expires_at) if lic.expires_at else "-",
            "usage_count": lic.usage_count,
            "usage_limit": lic.usage_limit,
            "active": lic.active
        }
        for lic in licenses
    ]

# =========================================================
# DELETE LICENSE (ADMIN)
# =========================================================

@app.delete("/delete-license/{license_key}", dependencies=[Depends(verify_token)])
def delete_license(license_key: str, db=Depends(get_db)):
    lic = db.query(License).filter(License.license_key == license_key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    db.delete(lic)
    db.commit()
    return {"message": "deleted"}

# =========================================================
# BULK DELETE LICENSE (ADMIN)
# =========================================================

@app.post("/bulk-delete-licenses", dependencies=[Depends(verify_token)])
def bulk_delete_licenses(data: BulkDeleteRequest, db=Depends(get_db)):
    deleted = []
    not_found = []

    for key in data.license_keys:
        lic = db.query(License).filter(License.license_key == key).first()
        if lic:
            db.delete(lic)
            deleted.append(key)
        else:
            not_found.append(key)

    db.commit()
    return {"deleted": deleted, "not_found": not_found, "count": len(deleted)}

# =========================================================
# CREATE LICENSE (ADMIN)
# =========================================================

@app.post("/create-license", dependencies=[Depends(verify_token)])
def create_license(data: CreateLicenseRequest, db=Depends(get_db)):

    expires = calculate_expiry(data.plan)

    lic = License(
        license_key=data.license_key,
        plan=data.plan,
        expires_at=expires.date() if expires else None,
        usage_limit=USAGE_LIMITS.get(data.plan, 999999)
    )

    db.add(lic)
    db.commit()

    return {"message": "created", "plan": data.plan}

# =========================================================
# BULK CREATE LICENSE (ADMIN)
# =========================================================

@app.post("/bulk-create-licenses", dependencies=[Depends(verify_token)])
def bulk_create_licenses(data: BulkCreateRequest, db=Depends(get_db)):
    if data.quantity < 1 or data.quantity > 100:
        raise HTTPException(status_code=400, detail="Quantity harus antara 1 dan 100")

    expires = calculate_expiry(data.plan)
    created = []

    for _ in range(data.quantity):
        key = generate_license_key(data.plan)
        lic = License(
            license_key=key,
            plan=data.plan,
            expires_at=expires.date() if expires else None,
            usage_limit=USAGE_LIMITS.get(data.plan, 999999)
        )
        db.add(lic)
        created.append(key)

    db.commit()
    return {"created": created, "count": len(created)}

# =========================================================
# PAYMENT CONFIG (PUBLIC — client key only)
# =========================================================

@app.get("/payment-config")
def payment_config():
    return {
        "client_key":    MIDTRANS_CLIENT_KEY,
        "is_production": MIDTRANS_IS_PRODUCTION,
    }

# =========================================================
# CREATE PAYMENT
# =========================================================

@app.post("/create-payment")
async def create_payment(data: PaymentRequest, db=Depends(get_db)):
    plan = data.plan.lower()

    if plan not in PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan")

    if not MIDTRANS_SERVER_KEY:
        raise HTTPException(status_code=503, detail="Payment not configured")

    amount   = PRICES[plan]
    order_id = f"ZOMET-{plan}-{int(datetime.now().timestamp())}-{random.randint(1000, 9999)}"

    payload = {
        "transaction_details": {
            "order_id":    order_id,
            "gross_amount": amount
        },
        "customer_details": {
            "email": data.email
        },
        "item_details": [{
            "id":       plan,
            "price":    amount,
            "quantity": 1,
            "name":     f"ZOMET AI — {plan.capitalize()} License"
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{MIDTRANS_BASE}/snap/v1/transactions",
            json=payload,
            auth=(MIDTRANS_SERVER_KEY, "")
        )

    if res.status_code != 201:
        print("MIDTRANS ERROR:", res.status_code, res.text)
        raise HTTPException(status_code=502, detail="Failed to create payment transaction")

    snap_token = res.json().get("token")

    tx = Transaction(
        order_id=order_id,
        email=data.email,
        plan=plan,
        amount=amount,
        status="pending"
    )
    db.add(tx)
    db.commit()

    return {"snap_token": snap_token, "order_id": order_id}

# =========================================================
# PAYMENT WEBHOOK (called by Midtrans)
# =========================================================

@app.post("/payment-webhook")
async def payment_webhook(request: Request, db=Depends(get_db)):
    body = await request.json()

    order_id      = body.get("order_id", "")
    status_code   = body.get("status_code", "")
    gross_amount  = body.get("gross_amount", "")
    signature_key = body.get("signature_key", "")

    expected = hashlib.sha512(
        f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}".encode()
    ).hexdigest()

    if signature_key != expected:
        raise HTTPException(status_code=403, detail="Invalid signature")

    tx = db.query(Transaction).filter(Transaction.order_id == order_id).first()
    if not tx or tx.status == "paid":
        return {"ok": True}

    transaction_status = body.get("transaction_status")
    fraud_status       = body.get("fraud_status", "accept")

    if transaction_status in ("capture", "settlement") and fraud_status == "accept":
        tx.status = "paid"
    elif transaction_status in ("cancel", "deny", "expire"):
        tx.status = "failed"

    if tx.status == "paid" and not tx.license_key:
        key     = generate_license_key(tx.plan)
        expires = calculate_expiry(tx.plan)

        lic = License(
            license_key=key,
            plan=tx.plan,
            expires_at=expires.date() if expires else None,
            usage_limit=USAGE_LIMITS.get(tx.plan, 999999)
        )
        db.add(lic)
        tx.license_key = key

        send_license_email(tx.email, key, tx.plan)

    db.commit()
    return {"ok": True}

# =========================================================
# PAYMENT STATUS (polled by frontend after snap success)
# =========================================================

@app.get("/payment-status/{order_id}")
def payment_status(order_id: str, db=Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.order_id == order_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "status":      tx.status,
        "license_key": tx.license_key if tx.status == "paid" else None,
        "plan":        tx.plan,
    }

# =========================================================
# VISITOR LOGS (ADMIN)
# =========================================================

@app.get("/visitor-logs", dependencies=[Depends(verify_token)])
def visitor_logs(limit: int = 200, event: str = None, db=Depends(get_db)):
    q = db.query(UsageLog).order_by(UsageLog.id.desc())
    if event:
        q = q.filter(UsageLog.event == event)
    logs = q.limit(limit).all()
    return [
        {
            "id":          log.id,
            "time":        str(log.created_at)[:19] if log.created_at else "-",
            "event":       log.event,
            "license_key": log.license_key,
            "plan":        log.plan or "-",
            "notes":       log.notes or "-",
        }
        for log in logs
    ]
