# Green Canopy — Deployment Guide / 部署指南

## 方式 A：Docker Compose 一键部署 (Any cloud VM)

适合任意装有 Docker 的云服务器（AWS EC2, DigitalOcean, 阿里云 ECS 等）。

### 1. 准备环境变量

```bash
cp .env.example .env
# 编辑 .env，填入真实密钥
```

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（必填） |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase 项目 URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase Publishable Key |
| `NEXT_PUBLIC_API_URL` | 前端访问后端的地址（Docker 内网默认 `http://backend:8000`） |

> ⚠️ Docker 环境中，`NEXT_PUBLIC_API_URL` 应设为 `http://backend:8000`（容器间通信用 service name）。

### 2. 一键启动

```bash
docker compose up -d --build
```

### 3. 访问

- 前端：`http://你的服务器IP:3000`
- 后端 API 文档：`http://你的服务器IP:8000/docs`
- AI 聊天：`http://你的服务器IP:3000/chat`

---

## Deployment Method A: Docker Compose (Any cloud VM)

Suitable for any cloud VM with Docker installed (AWS EC2, DigitalOcean, etc.).

### 1. Prepare environment variables

```bash
cp .env.example .env
# Edit .env with your real credentials
```

> ⚠️ In Docker, set `NEXT_PUBLIC_API_URL=http://backend:8000` for inter-container communication.

### 2. One-command startup

```bash
docker compose up -d --build
```

### 3. Access

- Frontend: `http://your-server-ip:3000`
- API docs: `http://your-server-ip:8000/docs`
- AI Chat: `http://your-server-ip:3000/chat`

---

## 方式 B：免费 Serverless 部署 / Free Serverless Deployment

如果你不想购买云服务器，可以分别将前后端部署到免费平台。

### 前端 → Vercel（免费）

1. 将项目推送到 GitHub
2. 在 [vercel.com](https://vercel.com) 导入仓库
3. 在 Vercel 项目 Settings → Environment Variables 中添加：

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | 你的 Supabase URL |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | 你的 Supabase Key |
   | `NEXT_PUBLIC_API_URL` | 后端的公网地址（如 `https://your-app.onrender.com`） |

   > 💡 如果使用 Vercel 自带的 `api/backend.py` Serverless Function 作为后端，则不需要设置 `NEXT_PUBLIC_API_URL`（同源请求）。

4. 部署 → 访问 `https://你的项目名.vercel.app`

### 后端 → Render / Railway（免费额度）

**Render**（`render.com`）：
1. 新建 Web Service → 连接 GitHub 仓库
2. Build Command: `pip install -r backend/requirements.txt`
3. Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. 添加环境变量：
   - `DEEPSEEK_API_KEY`
   - `GREEN_CANOPY_ALLOWED_ORIGINS=https://你的vercel域名.vercel.app`
5. 获得公网 URL 如 `https://green-canopy.onrender.com`

**Railway**（`railway.app`）：
1. 新建 Project → 连接 GitHub
2. Root Directory 设为 `/`
3. 添加 `DEEPSEEK_API_KEY` 环境变量
4. 自动检测 Python 并构建

---

## B: Free Serverless (Vercel + Render / Railway)

### Frontend → Vercel (free)

1. Push to GitHub
2. Import repo at [vercel.com](https://vercel.com)
3. Add env vars in Vercel Settings:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | your Supabase URL |
   | `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | your key |

   > 💡 If using Vercel's built-in `api/backend.py` function, omit `NEXT_PUBLIC_API_URL` (same-origin).

### Backend → Render (free tier)

1. New Web Service → connect GitHub
2. Build: `pip install -r backend/requirements.txt`
3. Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Env vars: `DEEPSEEK_API_KEY`, `GREEN_CANOPY_ALLOWED_ORIGINS`

---

## 架构说明 / Architecture

```
┌──────────────┐     HTTP (8080)     ┌──────────────┐
│   Next.js    │ ──────────────────→ │   FastAPI    │
│  (Vercel /   │ ←────────────────── │  (Render /   │
│   Docker)    │     JSON responses  │   Docker)    │
└──────┬───────┘                     └──────┬───────┘
       │                                    │
       │  Supabase Auth / DB                │  yfinance
       ▼                                    ▼
┌──────────────┐                     ┌──────────────┐
│   Supabase   │                     │  Yahoo       │
│  (cloud)     │                     │  Finance     │
└──────────────┘                     └──────────────┘
```

---

## 所需环境变量清单 / Required Environment Variables

所有平台（Docker / Vercel / Render）都需要配置以下变量：

| 变量 | 必需 | 用途 |
|---|---|---|
| `DEEPSEEK_API_KEY` | ✅ | AI Copilot 对话功能 |
| `NEXT_PUBLIC_SUPABASE_URL` | 推荐 | 用户认证与数据持久化 |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | 推荐 | Supabase 客户端密钥 |
| `NEXT_PUBLIC_API_URL` | 视情况 | 前后端分离时设置；同源部署可不设 |
| `GREEN_CANOPY_ALLOWED_ORIGINS` | 可选 | 额外允许的跨域来源（逗号分隔） |