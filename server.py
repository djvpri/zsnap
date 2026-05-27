from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import requests
import os

app = FastAPI()

# ======================================================
# CORS
# ======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# GEMINI API KEY
# ======================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ======================================================
# ROOT
# ======================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "app": "Zomet API"
    }

# ======================================================
# PROCESS IMAGE
# ======================================================

SECRET_KEY = "zomet-secret-2026"

@app.post("/process-image")
async def process_image(request: Request):

    # =========================
    # VALIDASI TOKEN
    # =========================

    client_key = request.headers.get("X-API-KEY")

    if client_key != SECRET_KEY:

        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    try:

        # ==============================================
        # GET JSON
        # ==============================================

        data = await request.json()

        image_base64 = data.get("image")

        if not image_base64:

            raise HTTPException(
                status_code=400,
                detail="Image not found"
            )

        # ==============================================
        # GEMINI API
        # ==============================================

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
                            "text": """
Anda adalah AI OCR dan pembaca soal.

Jika soal pilihan ganda:
- pilih jawaban terbaik
- jelaskan singkat

Jika coding:
- jelaskan error
- beri solusi

Jangan mendeskripsikan gambar.
Langsung jawab inti.
"""
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

        response = requests.post(
            url,
            json=payload,
            timeout=90
        )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        return response.json()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )