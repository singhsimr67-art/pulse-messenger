# 💬 Pulse Messenger

A full-stack real-time messaging platform built with **Python (FastAPI)** + **MongoDB** + vanilla HTML/CSS/JS.

## 🗂 Project Structure

```
pulse/
├── app.py              ← FastAPI backend (REST API + WebSockets)
├── requirements.txt    ← Python dependencies
├── static/
│   └── index.html      ← Frontend (served by FastAPI)
└── README.md
```

## ⚙️ Prerequisites

- Python 3.10+
- MongoDB running locally (or a MongoDB Atlas URI)

## 🚀 Setup & Run

### 1. Install MongoDB
**Ubuntu / Debian:**
```bash
sudo apt install mongodb
sudo systemctl start mongodb
```
**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```
**Windows:** Download from https://www.
.com/try/download/community

---

### 2. Create a virtual environment
```bash
cd pulse
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open in browser
```
http://localhost:8000
```

---

## 🌐 Environment Variables (optional)

| Variable     | Default                          | Description              |
|--------------|----------------------------------|--------------------------|
| `MONGO_URL`  | `://localhost:27017`      | MongoDB connection URI   |
| `SECRET_KEY` | `pulse-super-secret-...`         | JWT signing secret       |

Example with MongoDB Atlas:
```bash
MONGO_URL="mongodb+srv://user:pass@cluster.mongodb.net/pulse" uvicorn app:app --reload
```

---

## ✨ Features

- ✅ User registration & login (JWT auth)
- ✅ Password hashing with bcrypt
- ✅ Real-time messaging via WebSockets
- ✅ MongoDB persistence (users + messages)
- ✅ Online/offline presence indicators
- ✅ Conversation list with last-message previews
- ✅ Auto-reconnect on WebSocket disconnect
- ✅ Responsive dark-themed UI

## 📡 API Endpoints

| Method | Path                        | Description              |
|--------|-----------------------------|--------------------------|
| POST   | `/auth/register`            | Register new user        |
| POST   | `/auth/login`               | Login, receive JWT       |
| GET    | `/users?token=`             | List all other users     |
| GET    | `/conversations?token=`     | List your conversations  |
| GET    | `/messages/{key}?token=`    | Get messages in a convo  |
| POST   | `/messages?token=`          | Send a message           |
| WS     | `/ws/{username}?token=`     | WebSocket connection     |

Interactive API docs: https://pulse-messenger-ati5.onrender.com/
