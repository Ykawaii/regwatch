import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import jwt, JWTError
from app.config import JWT_SECRET, APP_URL
from app.database import get_db
from app.services.emailer import send_magic_link

router = APIRouter()

def create_token(email: str) -> str:
    payload = {"sub": email, "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None

def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("regwatch_session")
    if not token:
        return None
    email = verify_token(token)
    if not email:
        return None
    db = get_db()
    res = db.table("clients").select("*").eq("email", email).eq("actif", True).execute()
    return res.data[0] if res.data else None

@router.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")
    db = get_db()
    client = db.table("clients").select("id").eq("email", email).eq("actif", True).execute()
    if not client.data:
        raise HTTPException(404, "Aucun compte actif trouvé pour cet email")
    token = create_token(email)
    send_magic_link(email, token)
    return {"message": "Lien de connexion envoyé à votre adresse email"}

@router.get("/auth/verify")
async def verify(token: str, response: Response):
    email = verify_token(token)
    if not email:
        raise HTTPException(401, "Lien invalide ou expiré")
    new_token = create_token(email)
    resp = RedirectResponse(url="/dashboard")
    resp.set_cookie("regwatch_session", new_token, httponly=True, secure=True, samesite="lax", max_age=604800)
    return resp

@router.get("/auth/logout")
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("regwatch_session")
    return resp
