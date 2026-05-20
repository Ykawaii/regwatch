import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RegWatch démarrage...")
    start_scheduler()
    yield
    logger.info("RegWatch arrêt.")

app = FastAPI(title="RegWatch", lifespan=lifespan)
app.include_router(api_router)
app.include_router(auth_router)

from app.acquisition.demo_routes import router as demo_router
app.include_router(demo_router)

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "app", "dashboard")

@app.get("/", response_class=HTMLResponse)
async def landing():
    with open(os.path.join(DASHBOARD_DIR, "landing.html"), encoding="utf-8") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    from app.api.auth import get_current_user
    user = get_current_user(request)
    if not user:
        return HTMLResponse(status_code=302, headers={"Location": "/login"})
    with open(os.path.join(DASHBOARD_DIR, "index.html"), encoding="utf-8") as f:
        return f.read()

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Connexion — RegWatch</title>
<style>body{font-family:-apple-system,sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:white;border-radius:12px;padding:40px;max-width:400px;width:100%;box-shadow:0 2px 20px rgba(0,0,0,.08)}
h1{color:#1a2744;font-size:22px;margin-bottom:8px}.logo{color:#1D9E75;font-weight:700;font-size:16px;margin-bottom:24px;display:block}
p{color:#666;font-size:14px;margin-bottom:20px}input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:14px;margin-bottom:12px}
button{width:100%;background:#1a2744;color:white;border:none;padding:12px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#243869}.msg{text-align:center;font-size:13px;color:#1D9E75;margin-top:12px;display:none}</style>
</head><body><div class="card">
<span class="logo">REGWATCH</span>
<h1>Connexion</h1>
<p>Entrez votre email pour recevoir un lien de connexion.</p>
<input type="email" id="email" placeholder="votre@email.com" />
<button onclick="login()">Envoyer le lien de connexion</button>
<div class="msg" id="msg">Lien envoyé ! Vérifiez votre boîte mail.</div>
</div>
<script>
async function login() {
  const email = document.getElementById('email').value;
  if (!email) return;
  const resp = await fetch('/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
  if (resp.ok) document.getElementById('msg').style.display='block';
}
</script></body></html>""")

@app.get("/admin/access")
async def admin_access(email: str, key: str):
    from fastapi.responses import RedirectResponse
    from fastapi import HTTPException
    from app.api.auth import create_token
    if key != "ZKNrkgCq":
        raise HTTPException(403, "Forbidden")
    token = create_token(email)
    resp = RedirectResponse(url="/dashboard")
    resp.set_cookie("regwatch_session", token, httponly=True, secure=True, samesite="lax", max_age=604800)
    return resp

@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/billing", response_class=HTMLResponse)
async def billing():
    return HTMLResponse("<html><body><h2>Gestion de l'abonnement</h2><p>Contactez contact@regwatch.app pour modifier votre abonnement.</p></body></html>")

@app.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe():
    return HTMLResponse("<html><body><h2>Désinscription</h2><p>Connectez-vous à votre dashboard pour annuler votre abonnement.</p></body></html>")
