from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from datetime import datetime
from db import SessionLocal, engine
from model import Base, License
from license_service import calculate_expiry

Base.metadata.create_all(bind=engine)
API_SECRET = "rahasia-dari-desktop-ke-server"

app = FastAPI()

# 1. DEFINISIKAN FUNGSI INI DI ATAS
def verify_token(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Akses ditolak")

# =========================
# REQUEST MODEL
# =========================
class LicenseRequest(BaseModel):
    license_key: str
    hwid: str = None

# =========================
# VERIFY LICENSE
# =========================
# 2. SEKARANG DEKORATOR BISA MENEMUKAN FUNGSI verify_token
@app.post("/verify-license", dependencies=[Depends(verify_token)])
def verify(data: LicenseRequest):
    # ... isi fungsi tetap sama ...
    db = SessionLocal()
    lic = db.query(License).filter(License.license_key == data.license_key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
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

# =========================
# INCREMENT USAGE
# =========================
@app.post("/increment-usage", dependencies=[Depends(verify_token)])
def increment(data: LicenseRequest):
    db = SessionLocal()

    lic = db.query(License).filter(
        License.license_key == data.license_key
    ).first()

    if not lic:
        raise HTTPException(status_code=404, detail="Not found")

    # demo limit
    if lic.plan == "demo" and lic.usage_count >= lic.usage_limit:
        return {"valid": False, "reason": "demo limit reached"}

    lic.usage_count += 1
    db.commit()

    return {"success": True, "usage_count": lic.usage_count}


# =========================
# CREATE LICENSE (ADMIN)
# =========================
@app.post("/create-license", dependencies=[Depends(verify_token)])
def create_license(data: LicenseRequest, plan: str):
    db = SessionLocal()

    expires = calculate_expiry(plan)

    lic = License(
        license_key=data.license_key,
        plan=plan,
        expires_at=expires.date() if expires else None,
        usage_limit=5 if plan == "demo" else 999999
    )

    db.add(lic)
    db.commit()

    return {"message": "created", "plan": plan}

def verify_token(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Akses ditolak")