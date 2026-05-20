import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import APP_URL, LS_API_KEY, LS_STORE_ID, LS_VARIANTS, LS_WEBHOOK_SECRET, PLAN_LIMITS
from app.database import get_db
from app.api.auth import get_current_user
from app.services.emailer import send_welcome, send_payment_failed

router = APIRouter()
logger = logging.getLogger(__name__)

LS_API_BASE = "https://api.lemonsqueezy.com"

# ── LEMON SQUEEZY HELPERS ────────────────────────────────────────────────────

def _ls_headers() -> dict:
    return {
        "Authorization": f"Bearer {LS_API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def _verify_ls_webhook(body: bytes, signature: str) -> bool:
    """Vérifie la signature HMAC-SHA256 du webhook Lemon Squeezy."""
    expected = hmac.new(LS_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── ABONNEMENT LEMON SQUEEZY ─────────────────────────────────────────────────

@router.post("/create-subscription")
async def create_subscription(request: Request):
    """Crée un checkout Lemon Squeezy et retourne l'URL de paiement."""
    body = await request.json()
    plan = body.get("plan", "starter")
    email = body.get("email", "").strip().lower()
    secteurs = body.get("secteurs", [])

    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")

    variant_id = LS_VARIANTS.get(plan)
    if not variant_id:
        raise HTTPException(400, f"Plan inconnu ou non configuré : {plan}")

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                f"{LS_API_BASE}/v1/checkouts",
                headers=_ls_headers(),
                json={
                    "data": {
                        "type": "checkouts",
                        "attributes": {
                            "checkout_data": {
                                "email": email,
                                "custom": {
                                    "plan": plan,
                                    "email": email,
                                    "secteurs": ",".join(secteurs),
                                },
                            },
                            "product_options": {
                                "redirect_url": f"{APP_URL}/onboarding",
                                "receipt_button_text": "Accéder à mon tableau de bord",
                                "receipt_link_url": f"{APP_URL}/dashboard",
                            },
                            "checkout_options": {
                                "button_color": "#1D9E75",
                            },
                        },
                        "relationships": {
                            "store": {
                                "data": {"type": "stores", "id": str(LS_STORE_ID)}
                            },
                            "variant": {
                                "data": {"type": "variants", "id": str(variant_id)}
                            },
                        },
                    }
                },
            )
            resp.raise_for_status()
            checkout_url = resp.json()["data"]["attributes"]["url"]
            return {"url": checkout_url}

    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur Lemon Squeezy create-subscription: {e.response.text}")
        raise HTTPException(500, "Erreur lors de la création du checkout")
    except Exception as e:
        logger.error(f"Erreur create-subscription: {e}")
        raise HTTPException(500, "Erreur interne")


@router.post("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    """Reçoit et traite les webhooks Lemon Squeezy."""
    raw_body = await request.body()
    signature = request.headers.get("x-signature", "")

    if not _verify_ls_webhook(raw_body, signature):
        raise HTTPException(400, "Signature webhook invalide")

    event = json.loads(raw_body)
    event_name = event.get("meta", {}).get("event_name", "")
    custom_data = event.get("meta", {}).get("custom_data", {})
    data = event.get("data", {})
    attributes = data.get("attributes", {})

    logger.info(f"[WEBHOOK LS] {event_name}")
    db = get_db()

    # ── Abonnement créé / activé ───────────────────────────────────────────
    if event_name in ("subscription_created", "subscription_updated"):
        status = attributes.get("status", "")
        if event_name == "subscription_updated" and status not in ("active", "on_trial"):
            # géré par les events cancelled/expired ci-dessous
            return {"ok": True}

        subscription_id = str(data.get("id", ""))
        email = (
            custom_data.get("email")
            or attributes.get("user_email", "")
        )
        plan = custom_data.get("plan", "starter")
        secteurs_str = custom_data.get("secteurs", "")
        secteurs = [s for s in secteurs_str.split(",") if s] or ["general"]

        if not email:
            logger.warning("[WEBHOOK LS] subscription sans email")
            return {"ok": True}

        existing = db.table("clients").select("id").eq("email", email).execute()
        if existing.data:
            db.table("clients").update({
                "plan": plan,
                "actif": True,
                "lemonsqueezy_subscription_id": subscription_id,
                "secteurs": secteurs,
            }).eq("email", email).execute()
        else:
            db.table("clients").insert({
                "email": email,
                "plan": plan,
                "actif": True,
                "lemonsqueezy_subscription_id": subscription_id,
                "secteurs": secteurs,
            }).execute()

        if event_name == "subscription_created":
            send_welcome(email, "", plan)
        logger.info(f"[WEBHOOK LS] Client activé: {email} plan={plan}")

    # ── Abonnement annulé / expiré ─────────────────────────────────────────
    elif event_name in ("subscription_cancelled", "subscription_expired"):
        subscription_id = str(data.get("id", ""))
        if subscription_id:
            db.table("clients").update({"actif": False}).eq(
                "lemonsqueezy_subscription_id", subscription_id
            ).execute()
            logger.info(f"[WEBHOOK LS] Abonnement désactivé: {subscription_id}")

    # ── Paiement échoué ────────────────────────────────────────────────────
    elif event_name == "subscription_payment_failed":
        subscription_id = str(data.get("id", ""))
        if subscription_id:
            res = (
                db.table("clients")
                .select("email,nom")
                .eq("lemonsqueezy_subscription_id", subscription_id)
                .execute()
            )
            if res.data:
                c = res.data[0]
                send_payment_failed(c["email"], c.get("nom", ""))
                logger.info(f"[WEBHOOK LS] Paiement échoué notifié: {c['email']}")

    return {"ok": True}


@router.get("/onboarding")
async def onboarding(
    subscription_id: str = "",
    order_id: str = "",
):
    """Page de confirmation après paiement Lemon Squeezy."""
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Bienvenue sur RegWatch</title>
<style>body{font-family:-apple-system,sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:white;border-radius:12px;padding:40px;max-width:480px;text-align:center;box-shadow:0 2px 20px rgba(0,0,0,.08)}
h1{color:#1a2744;font-size:24px}.check{font-size:48px;margin-bottom:16px}
p{color:#555;line-height:1.7}.badge{background:#E1F5EE;color:#0F6E56;padding:4px 12px;border-radius:999px;font-size:13px;font-weight:600}
a{display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:12px 32px;border-radius:8px;margin-top:24px;font-size:15px}</style>
</head><body><div class="card">
<div class="check">✓</div>
<h1>Bienvenue sur RegWatch !</h1>
<p>Votre compte est activé.<br>
Un email de bienvenue vous a été envoyé.</p>
<p>Votre première veille démarre ce soir à 6h00.</p>
<a href="/dashboard">Accéder à mon tableau de bord →</a>
</div></body></html>""")


# ── DASHBOARD API ────────────────────────────────────────────────────────────

@router.get("/api/textes")
async def get_textes(request: Request, semaine: str = "current"):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Non connecté")
    db = get_db()
    depuis = (datetime.utcnow() - timedelta(days=7)).isoformat()
    res = (
        db.table("alertes")
        .select("score, textes_reglementaires(id,titre,url,date_publication,resume_ia,source)")
        .eq("client_id", user["id"])
        .gte("created_at", depuis)
        .order("score", desc=True)
        .limit(20)
        .execute()
    )
    textes = []
    for a in res.data or []:
        t = a.get("textes_reglementaires", {})
        if t:
            textes.append({**t, "score": a.get("score", 5)})
    return textes


@router.get("/api/rapports")
async def get_rapports(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Non connecté")
    db = get_db()
    res = (
        db.table("rapports_hebdo")
        .select("id,semaine_debut,envoyee,created_at")
        .eq("client_id", user["id"])
        .order("created_at", desc=True)
        .limit(12)
        .execute()
    )
    return res.data or []


@router.put("/api/client/secteurs")
async def update_secteurs(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Non connecté")
    body = await request.json()
    secteurs = body.get("secteurs", [])
    limit = PLAN_LIMITS.get(user.get("plan", "starter"), {}).get("secteurs", 1)
    if len(secteurs) > limit:
        raise HTTPException(400, f"Votre plan permet {limit} secteur(s) maximum")
    db = get_db()
    db.table("clients").update({"secteurs": secteurs}).eq("id", user["id"]).execute()
    return {"ok": True, "secteurs": secteurs}


@router.get("/api/stats")
async def get_stats(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Non connecté")
    db = get_db()
    total = (
        db.table("alertes").select("id", count="exact")
        .eq("client_id", user["id"]).execute()
    )
    urgentes = (
        db.table("alertes").select("id", count="exact")
        .eq("client_id", user["id"]).gte("score", 9).execute()
    )
    rapports = (
        db.table("rapports_hebdo").select("id", count="exact")
        .eq("client_id", user["id"]).execute()
    )
    return {
        "total_alertes": total.count or 0,
        "alertes_urgentes": urgentes.count or 0,
        "rapports_envoyes": rapports.count or 0,
        "plan": user.get("plan"),
        "secteurs": user.get("secteurs", []),
    }
