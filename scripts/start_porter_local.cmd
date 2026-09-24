@echo off
setlocal
pushd "%~dp0.."

set "DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/test_db"
set "REDIS_URL=redis://:redissecret@127.0.0.1:6379/0"
set "ENVIRONMENT=local"
set "AUTH_PROVIDER=local"
set "UI_APP_URL=http://localhost:3022"
set "CORS_ALLOWED_ORIGINS=http://localhost:3022"
set "BACKEND_API_ENDPOINT=http://127.0.0.1:8001"
if not defined PORTER_STT_DEVICE set "PORTER_STT_DEVICE=cuda"
if not defined PORTER_STT_COMPUTE_TYPE set "PORTER_STT_COMPUTE_TYPE=float16"
if not defined PORTER_TTS_MODE set "PORTER_TTS_MODE=pocket"
if not defined PORTER_POCKET_TTS_VOICE set "PORTER_POCKET_TTS_VOICE=bill_boerst"
if not defined PORTER_SEMANTIC_FALLBACK_ENABLED set "PORTER_SEMANTIC_FALLBACK_ENABLED=true"
if not defined PORTER_SEMANTIC_MODEL set "PORTER_SEMANTIC_MODEL=qwen3:4b"
if not defined PORTER_SEMANTIC_TIMEOUT_SECONDS set "PORTER_SEMANTIC_TIMEOUT_SECONDS=2"
for /f "tokens=1,* delims==" %%A in ('findstr /b "OSS_JWT_SECRET=" ".env"') do set "%%A=%%B"
if not defined OSS_JWT_SECRET exit /b 1
set "MINIO_ENDPOINT=127.0.0.1:9000"
set "MINIO_PUBLIC_ENDPOINT=http://localhost:9000"
set "MINIO_ACCESS_KEY=minioadmin"
set "MINIO_SECRET_KEY=minioadmin"
set "MINIO_BUCKET=voice-audio"
set "MINIO_SECURE=false"

.\.venv313\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8001
