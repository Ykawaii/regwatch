import resend
import logging
from app.config import RESEND_API_KEY, APP_URL

resend.api_key = RESEND_API_KEY
logger = logging.getLogger(__name__)

FROM_EMAIL = "RegWatch <onboarding@resend.dev>"

def send_welcome(email: str, nom: str, plan: str):
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "Bienvenue sur RegWatch — votre veille démarre maintenant",
            "html": f"""
            <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px">
              <h1 style="color:#1a2744;font-size:22px">Bienvenue, {nom or 'cher client'} !</h1>
              <p style="color:#333;line-height:1.7">Votre veille réglementaire est maintenant active.<br>
              Plan souscrit : <strong>{plan.upper()}</strong></p>
              <p style="color:#333;line-height:1.7">Dès ce soir, RegWatch va scraper le Journal Officiel et EUR-Lex pour votre secteur.
              Vous recevrez votre premier rapport lundi prochain à 8h00.</p>
              <a href="{APP_URL}/dashboard" style="display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:12px 28px;border-radius:6px;margin:16px 0;font-size:14px">
                Accéder à mon tableau de bord →
              </a>
              <p style="color:#888;font-size:12px;margin-top:32px">Une question ? Répondez directement à cet email.</p>
            </div>"""
        })
        logger.info(f"Email bienvenue envoyé à {email}")
    except Exception as e:
        logger.error(f"Erreur email bienvenue {email}: {e}")

def send_alert(email: str, nom: str, texte: dict):
    score = texte.get("score", 7)
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": f"⚠️ Alerte réglementaire urgente — {texte.get('titre','')[:60]}",
            "html": f"""
            <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px">
              <div style="background:#fff3cd;border-left:4px solid #E24B4A;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:20px">
                <p style="margin:0;font-weight:600;color:#E24B4A">Alerte prioritaire — score {score}/10</p>
              </div>
              <h2 style="color:#1a2744;font-size:18px">{texte.get('titre','')}</h2>
              <div style="color:#333;line-height:1.7">{texte.get('resume_ia','') or 'Voir le texte officiel pour le détail.'}</div>
              <a href="{texte.get('url','#')}" style="display:inline-block;background:#E24B4A;color:white;text-decoration:none;padding:10px 24px;border-radius:6px;margin:16px 0;font-size:13px">
                Lire le texte officiel →
              </a>
              <a href="{APP_URL}/dashboard" style="display:block;color:#1D9E75;font-size:12px;text-decoration:none;margin-top:8px">
                Voir tous mes textes →
              </a>
            </div>"""
        })
        logger.info(f"Alerte urgente envoyée à {email} pour {texte.get('titre','')[:50]}")
    except Exception as e:
        logger.error(f"Erreur alerte {email}: {e}")

def send_rapport(email: str, nom: str, rapport_html: str, pdf_url: str = None):
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "Votre rapport de veille réglementaire — Cette semaine",
            "html": rapport_html,
        })
        logger.info(f"Rapport hebdo envoyé à {email}")
    except Exception as e:
        logger.error(f"Erreur rapport {email}: {e}")

def send_magic_link(email: str, token: str):
    login_url = f"{APP_URL}/auth/verify?token={token}"
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "Votre lien de connexion RegWatch",
            "html": f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
              <h2 style="color:#1a2744">Connexion à RegWatch</h2>
              <p style="color:#333">Cliquez sur ce lien pour accéder à votre tableau de bord :</p>
              <a href="{login_url}" style="display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:12px 28px;border-radius:6px;margin:16px 0;font-size:14px">
                Me connecter →
              </a>
              <p style="color:#888;font-size:12px">Ce lien expire dans 7 jours. Si vous n'avez pas demandé cette connexion, ignorez cet email.</p>
            </div>"""
        })
    except Exception as e:
        logger.error(f"Erreur magic link {email}: {e}")

def send_payment_failed(email: str, nom: str):
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "Action requise — Problème de paiement RegWatch",
            "html": f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
              <h2 style="color:#E24B4A">Problème de paiement</h2>
              <p style="color:#333">Bonjour {nom or ''},<br>
              Nous n'avons pas pu traiter votre paiement mensuel RegWatch.</p>
              <p style="color:#333">Votre accès reste actif pendant 7 jours. Merci de mettre à jour votre moyen de paiement :</p>
              <a href="{APP_URL}/billing" style="display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:12px 24px;border-radius:6px;margin:16px 0">
                Mettre à jour ma carte →
              </a>
            </div>"""
        })
    except Exception as e:
        logger.error(f"Erreur email paiement échoué {email}: {e}")
