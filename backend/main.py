import os
import uuid
import numpy as np
import librosa
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Multi-Track Audio Editor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

WAVEFORM_POINTS = 2000


def compute_waveform(file_path: str, n_points: int = WAVEFORM_POINTS) -> dict:
    y, sr = librosa.load(file_path, sr=None, mono=True)
    duration = float(len(y) / sr)

    chunk_size = max(1, len(y) // n_points)
    waveform = []
    for i in range(n_points):
        start = i * chunk_size
        end = min(start + chunk_size, len(y))
        if start >= len(y):
            waveform.append(0.0)
        else:
            chunk = y[start:end]
            peak = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0
            waveform.append(peak)

    return {
        "waveform": waveform,
        "sample_rate": sr,
        "duration": duration,
        "samples": len(y),
    }


@app.post("/api/upload")
async def upload_audio(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp3", ".wav", ".ogg", ".flac")):
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        info = compute_waveform(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")

    return JSONResponse(content={
        "id": unique_name,
        "filename": file.filename,
        "waveform": info["waveform"],
        "sample_rate": info["sample_rate"],
        "duration": info["duration"],
        "samples": info["samples"],
    })


@app.get("/api/audio/{audio_id}")
async def get_audio(audio_id: str):
    file_path = os.path.join(UPLOAD_DIR, audio_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    from fastapi.responses import FileResponse
    return FileResponse(file_path, media_type="audio/mpeg", filename=audio_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
