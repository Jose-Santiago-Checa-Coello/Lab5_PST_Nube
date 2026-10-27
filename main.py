from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import sqlite3
import os

# Cargar variables de entorno desde el archivo .env (si existe localmente)
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
DB_NAME = "telemetria.db"

app = FastAPI(title="API Telemetria y Control con Token - Lab 5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

class LecturaIn(BaseModel):
    dispositivo: str
    temperatura: float
    humedad: float

class ComandoActuador(BaseModel):
    estado: int  # 0 = Apagado, 1 = Encendido

def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispositivo TEXT NOT NULL,
            temperatura REAL NOT NULL,
            humedad REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actuador (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            estado INTEGER NOT NULL DEFAULT 0,
            actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO actuador (id, estado) VALUES (1, 0)")
    conn.commit()
    conn.close()

inicializar_bd()

def verificar_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    if not API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error del servidor: API_TOKEN no configurado en variables de entorno"
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado (401): Token ausente. Envie encabezado Authorization: Bearer <TOKEN>"
        )
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado (401): Token invalido"
        )
    return credentials.credentials

@app.get("/")
def servir_dashboard():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "online", "mensaje": "API Telemetria Lab 5 activa en la nube."}

@app.post("/api/lecturas", status_code=201)
def guardar_lectura(lectura: LecturaIn, token: str = Depends(verificar_token)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lecturas (dispositivo, temperatura, humedad) VALUES (?, ?, ?)",
        (lectura.dispositivo, lectura.temperatura, lectura.humedad)
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return {"status": "guardado", "id": nuevo_id}

@app.get("/api/lecturas")
def obtener_lecturas(limite: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, dispositivo, temperatura, humedad, timestamp "
        "FROM lecturas ORDER BY id DESC LIMIT ?",
        (limite,)
    )
    filas = cursor.fetchall()
    conn.close()
    filas.reverse()
    return [
        {
            "id": f[0], "dispositivo": f[1],
            "temperatura": f[2], "humedad": f[3], "timestamp": f[4]
        }
        for f in filas
    ]

@app.get("/api/actuador")
def obtener_estado_actuador():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT estado, actualizado FROM actuador WHERE id = 1")
    fila = cursor.fetchone()
    conn.close()
    return {"estado": fila[0], "actualizado": fila[1]}

@app.post("/api/actuador")
def cambiar_estado_actuador(cmd: ComandoActuador):
    estado_limpio = 1 if cmd.estado else 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE actuador SET estado = ?, actualizado = CURRENT_TIMESTAMP WHERE id = 1",
        (estado_limpio,)
    )
    conn.commit()
    conn.close()
    return {"status": "actualizado", "estado": estado_limpio}