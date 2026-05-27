from fastapi import FastAPI, UploadFile, File
import uvicorn
import os

app = FastAPI()

# Root endpoint untuk mengecek status server
@app.get("/")
async def root():
    return {"status": "online", "message": "Server FastAPI sudah berjalan di Railway!"}

# Endpoint untuk memproses data atau gambar
@app.post("/process-image")
async def process_image(file: UploadFile = File(...)):
    # Di sini Anda bisa menambahkan logika pengolahan gambar atau AI
    # Contoh sederhana: menyimpan file
    filename = file.filename
    return {"message": "File diterima", "filename": filename}

if __name__ == "__main__":
    # Ini dijalankan jika Anda menjalankan server langsung dari terminal
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)