import os
import uuid
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from modules.ocr import run_ocr

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
DB_FILES = {}


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    filename = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    DB_FILES[file_id] = {
        "file_path": file_path,
        "filename": filename,
        "document_type": document_type
    }

    return {
        "file_id": file_id,
        "document_type": document_type,
        "status": "uploaded"
    }


@app.post("/api/extract/{file_id}")
async def extract_document(file_id: str):
    file_info = DB_FILES.get(file_id)
    if not file_info:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    result = run_ocr(file_info["file_path"], file_info["document_type"])
    return result
