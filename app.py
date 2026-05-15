
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from bson import ObjectId
import os

# ─── CONFIG ───────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "pulse-super-secret-change-in-production")
ALGORITHM   = "HS256"
TOKEN_DAYS  = 7
MONGO_URL   = os.getenv("MONGO_URL", "mongodb://localhost:27017")

# ─── APP ──────────────────────────────────────────────────
app = FastAPI(title="Pulse Messenger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── DATABASE ─────────────────────────────────────────────
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.pulse_messenger

# ─── SECURITY ─────────────────────────────────────────────
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(password: str) -> str:
    return pwd.hash(password)

def check_pw(plain: str, hashed: str) -> bool:
    return pwd.verify(plain, hashed)

def make_token(username: str) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

async def auth(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        user = await db.users.find_one({"username": username})
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

# ─── WEBSOCKET MANAGER ────────────────────────────────────
class WSManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, ws: WebSocket):
        await ws.accept()
        self.connections[username] = ws

    def disconnect(self, username: str):
        self.connections.pop(username, None)

    async def send(self, username: str, data: dict):
        ws = self.connections.get(username)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(username)

    def online_users(self) -> list[str]:
        return list(self.connections.keys())

ws_manager = WSManager()

# ─── MODELS ───────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class SendMessageRequest(BaseModel):
    to: str
    text: str

# ─── HELPERS ──────────────────────────────────────────────
def convo_key(a: str, b: str) -> str:
    return "::".join(sorted([a, b]))

def serialize_user(u: dict) -> dict:
    return {"id": str(u["_id"]), "name": u["name"], "username": u["username"]}

def serialize_msg(m: dict) -> dict:
    return {
        "id": str(m["_id"]),
        "from": m["from"],
        "to": m["to"],
        "text": m["text"],
        "convo_key": m["convo_key"],
        "ts": m["created_at"].isoformat(),
    }

# ─── ROUTES ───────────────────────────────────────────────

@app.post("/auth/register")
async def register(data: RegisterRequest):
    data.username = data.username.strip().lower()
    data.name = data.name.strip()

    if len(data.username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not data.name:
        raise HTTPException(400, "Display name is required")
    if await db.users.find_one({"username": data.username}):
        raise HTTPException(400, "Username already taken")

    doc = {
        "name": data.name,
        "username": data.username,
        "password": hash_pw(data.password),
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    token = make_token(data.username)
    return {
        "token": token,
        "user": {"id": str(result.inserted_id), "name": data.name, "username": data.username},
    }


@app.post("/auth/login")
async def login(data: LoginRequest):
    user = await db.users.find_one({"username": data.username.strip().lower()})
    if not user or not check_pw(data.password, user["password"]):
        raise HTTPException(401, "Invalid username or password")
    return {"token": make_token(user["username"]), "user": serialize_user(user)}


@app.get("/users")
async def list_users(token: str):
    current = await auth(token)
    online = ws_manager.online_users()
    result = []
    async for u in db.users.find({"username": {"$ne": current["username"]}}, {"password": 0}):
        u_out = serialize_user(u)
        u_out["online"] = u_out["username"] in online
        result.append(u_out)
    return result


@app.get("/conversations")
async def list_conversations(token: str):
    current = await auth(token)
    username = current["username"]

    pipeline = [
        {"$match": {"participants": username}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$convo_key",
            "last": {"$first": "$$ROOT"},
        }},
        {"$sort": {"last.created_at": -1}},
    ]

    convos = []
    async for doc in db.messages.aggregate(pipeline):
        parts = doc["_id"].split("::")
        other_uname = next((p for p in parts if p != username), None)
        if not other_uname:
            continue
        other = await db.users.find_one({"username": other_uname}, {"password": 0})
        if not other:
            continue
        lm = doc["last"]
        convos.append({
            "convo_key": doc["_id"],
            "other": serialize_user(other),
            "last_message": {
                "text": lm["text"],
                "from": lm["from"],
                "ts": lm["created_at"].isoformat(),
            },
            "other_online": other_uname in ws_manager.online_users(),
        })
    return convos


@app.get("/messages/{key}")
async def get_messages(key: str, token: str):
    current = await auth(token)
    if current["username"] not in key.split("::"):
        raise HTTPException(403, "Access denied")
    msgs = []
    async for m in db.messages.find({"convo_key": key}).sort("created_at", 1):
        msgs.append(serialize_msg(m))
    return msgs


@app.post("/messages")
async def send_message(data: SendMessageRequest, token: str):
    current = await auth(token)
    to_user = await db.users.find_one({"username": data.to})
    if not to_user:
        raise HTTPException(404, "Recipient not found")

    key = convo_key(current["username"], data.to)
    doc = {
        "convo_key": key,
        "participants": [current["username"], data.to],
        "from": current["username"],
        "to": data.to,
        "text": data.text,
        "created_at": datetime.utcnow(),
    }
    result = await db.messages.insert_one(doc)
    doc["_id"] = result.inserted_id
    msg_out = serialize_msg(doc)

    # Push to recipient via WebSocket
    await ws_manager.send(data.to, {"type": "new_message", "message": msg_out})
    # Also echo to sender's other sessions
    await ws_manager.send(current["username"], {"type": "sent_echo", "message": msg_out})

    return msg_out


@app.websocket("/ws/{username}")
async def websocket_endpoint(ws: WebSocket, username: str, token: str):
    try:
        user = await auth(token)
        if user["username"] != username:
            await ws.close(code=4001)
            return
    except HTTPException:
        await ws.close(code=4001)
        return

    await ws_manager.connect(username, ws)

    # Broadcast online status
    await ws_manager.send(username, {"type": "status", "status": "connected"})

    try:
        while True:
            await ws.receive_text()   # keep-alive ping/pong
    except WebSocketDisconnect:
        ws_manager.disconnect(username)


# ─── SERVE FRONTEND ───────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")


# ─── STARTUP: CREATE INDEXES ──────────────────────────────
@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("username", unique=True)
        await db.messages.create_index("convo_key")
        await db.messages.create_index("participants")
        print("✅ Pulse Messenger started")
    except Exception as e:
        print(f"⚠️ Startup warning: {e}")
