"""
Moteur cold email automatisé
Envoie les démos personnalisées + relances automatiques
Gère le suivi des ouvertures et clics
"""
import resend
import logging
import time
from datetime import datetime, timedelta
from app.config import RESEND_API_KEY, APP_URL
from app.database import get_db
from app.acquisition.demo_generator import generer_demo_prospect

resend.api_key = RESEND_API_KEY
logger = logging.getLogger(__name__)

FROM_EMAIL = "RegWatch <demo@regwatch.app>"
REPLY_TO = "contact@regwatch.app"

def envoyer_cold_email_initial(prospect: dict) -> bool:
    """Envoie le premier email avec la démo personnalisée."""
    try:
        nom = prospect.get("nom", "Cabinet")
        email = prospect.get("email", "")
        secteur = prospect.get("secteur", "votre secteur")
        if not email:
            return False

        # Génère la démo HTML personnalisée
        demo_html = generer_demo_prospect(prospect)

        # Objet personnalisé selon le secteur
        sujets = {
            "comptabilite": f"Votre rapport de veille fiscale cette semaine — exemple pour {nom}",
            "droit":        f"Nouveautés juridiques cette semaine filtrées pour {nom}",
            "immobilier":   f"Veille réglementaire immobilier — exemple personnalisé pour {nom}",
            "sante":        f"Textes réglementaires santé de la semaine — {nom}",
        }
        sujet = sujets.get(secteur, f"Votre veille réglementaire personnalisée — {nom}")

        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "reply_to": REPLY_TO,
            "to": email,
            "subject": sujet,
            "html": demo_html,
            "headers": {
                "X-Entity-Ref-ID": prospect.get("id", ""),
                "List-Unsubscribe": f"<{APP_URL}/unsubscribe?email={email}>",
            }
        })

        # Sauvegarde l'envoi en BDD
        db = get_db()
        db.table("prospects").update({
            "statut": "email_envoye",
            "date_premier_email": datetime.utcnow().isoformat(),
            "resend_email_id": result.get("id", ""),
        }).eq("id", prospect["id"]).execute()

        logger.info(f"Cold email envoyé à {email} ({nom})")
        return True

    except Exception as e:
        logger.error(f"Erreur cold email {prospect.get('email')}: {e}")
        return False

def envoyer_relance(prospect: dict) -> bool:
    """Envoie l'email de relance J+3 si pas de réponse."""
    try:
        nom = prospect.get("nom", "Cabinet")
        email = prospect.get("email", "")
        secteur = prospect.get("secteur", "votre secteur")
        demo_url = f"{APP_URL}/demo/{prospect.get('id', '')}?ref=relance"

        relance_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,sans-serif;max-width:520px;margin:0 auto;padding:32px;color:#333">
  <p style="color:#1D9E75;font-weight:700;font-size:13px;letter-spacing:.05em;margin:0 0 16px">REGWATCH</p>
  <p style="font-size:15px;color:#1a2744;font-weight:600;margin:0 0 12px">Avez-vous eu le temps de regarder le rapport ?</p>
  <p style="font-size:14px;line-height:1.7;margin:0 0 16px">Bonjour,<br><br>
  Je vous avais envoyé il y a quelques jours un exemple de rapport de veille réglementaire personnalisé pour votre cabinet en {secteur}.<br><br>
  Si vous n'avez pas eu le temps de le regarder, le voici à nouveau :</p>
  <a href="{demo_url}" style="display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;margin-bottom:16px">
    Voir mon rapport personnalisé →
  </a>
  <p style="font-size:13px;color:#666;line-height:1.7">Ce que vous recevez chaque semaine si vous activez RegWatch :<br>
  ✓ Textes du JO et EUR-Lex filtrés pour votre secteur<br>
  ✓ Résumés en langage clair avec actions concrètes<br>
  ✓ Alertes immédiates si un texte critique est publié<br><br>
  30 jours gratuits, sans carte bancaire.</p>
  <hr style="border:none;border-top:1px solid #f0f0f0;margin:20px 0">
  <p style="font-size:11px;color:#bbb">RegWatch · <a href="{APP_URL}/unsubscribe?email={email}" style="color:#bbb">Se désabonner</a></p>
</body></html>"""

        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "reply_to": REPLY_TO,
            "to": email,
            "subject": f"Re: Votre rapport de veille {secteur}",
            "html": relance_html,
        })

        db = get_db()
        db.table("prospects").update({
            "statut": "relance_envoyee",
            "date_relance": datetime.utcnow().isoformat(),
        }).eq("id", prospect["id"]).execute()

        logger.info(f"Relance envoyée à {email}")
        return True

    except Exception as e:
        logger.error(f"Erreur relance {prospect.get('email')}: {e}")
        return False

def run_cold_email_campaign(batch_size: int = 20) -> dict:
    """
    Lance une campagne d'acquisition automatique.
    - Envoie les emails initiaux aux nouveaux prospects
    - Envoie les relances J+3
    - Respecte les limites d'envoi Resend
    Retourne les stats de la campagne.
    """
    db = get_db()
    stats = {"envoyes": 0, "relances": 0, "erreurs": 0}

    # 1. Emails initiaux — prospects nouveaux
    nouveaux = db.table("prospects")\
        .select("*")\
        .eq("statut", "nouveau")\
        .limit(batch_size)\
        .execute()

    for prospect in (nouveaux.data or []):
        success = envoyer_cold_email_initial(prospect)
        if success:
            stats["envoyes"] += 1
        else:
            stats["erreurs"] += 1
        time.sleep(1.5)  # Max ~40 emails/min, largement sous les limites Resend

    # 2. Relances J+3 — prospects qui ont reçu l'email initial il y a 3+ jours sans réponse
    trois_jours = (datetime.utcnow() - timedelta(days=3)).isoformat()
    a_relancer = db.table("prospects")\
        .select("*")\
        .eq("statut", "email_envoye")\
        .lt("date_premier_email", trois_jours)\
        .limit(batch_size)\
        .execute()

    for prospect in (a_relancer.data or []):
        success = envoyer_relance(prospect)
        if success:
            stats["relances"] += 1
        else:
            stats["erreurs"] += 1
        time.sleep(1.5)

    logger.info(f"Campagne acquisition: {stats}")
    return stats
