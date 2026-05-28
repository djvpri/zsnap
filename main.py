import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from db import SessionLocal, engine
from model import Base, License
from license_service import calculate_expiry

Base.metadata.create_all(bind=engine)

# =========================================================
# CONFIG
# =========================================================

API_SECRET     = os.getenv("API_SECRET", "rahasia-dari-desktop-ke-server")
PROCESS_SECRET = os.getenv("PROCESS_SECRET", "zomet-secret-2026")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
# REQUEST MODELS
# =========================================================

class LicenseRequest(BaseModel):
    license_key: str
    hwid: str = None

class CreateLicenseRequest(BaseModel):
    license_key: str
    plan: str

# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():
    return {"status": "online", "app": "Zomet API"}

# =========================================================
# PROCESS IMAGE
# =========================================================

@app.post("/process-image")
async def process_image(request: Request):

    client_key = request.headers.get("X-API-KEY")

    if client_key != PROCESS_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = await request.json()

        image_base64 = data.get("image")

        if not image_base64:
            raise HTTPException(status_code=400, detail="Image not found")

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
                                "- jelaskan singkat\n\n"
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

    if lic.hwid and lic.hwid != data.hwid:
        return {"valid": False, "reason": "HWID mismatch"}

    if not lic.hwid:
        lic.hwid = data.hwid

    if lic.expires_at and datetime.now().date() > lic.expires_at:
        return {"valid": False, "reason": "expired"}

    db.commit()

    return {
        "valid": True,
        "plan": lic.plan,
        "expires_at": str(lic.expires_at),
        "usage_count": lic.usage_count,
        "usage_limit": lic.usage_limit
    }

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
# CREATE LICENSE (ADMIN)
# =========================================================

@app.post("/create-license", dependencies=[Depends(verify_token)])
def create_license(data: CreateLicenseRequest, db=Depends(get_db)):

    expires = calculate_expiry(data.plan)

    usage_limits = {
        "demo":    5,
        "daily":   100,
        "weekly":  700,
        "monthly": 3000,
        "yearly":  999999
    }

    lic = License(
        license_key=data.license_key,
        plan=data.plan,
        expires_at=expires.date() if expires else None,
        usage_limit=usage_limits.get(data.plan, 999999)
    )

    db.add(lic)
    db.commit()

    return {"message": "created", "plan": data.plan}
