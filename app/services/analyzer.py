import time
import json
import logging
from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY
from app.database import get_db

logger = logging.getLogger(__name__)
client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Tu es un expert en droit et réglementation française et européenne.
Tu analyses des textes réglementaires pour des professionnels (avocats, experts-comptables, médecins, etc.).
Tes réponses sont toujours précises, concises, et actionnables. Tu ne dis jamais "il faudrait consulter un professionnel" — TU ES le professionnel qui aide."""

def score_pertinence(texte: dict, secteur_client: str) -> dict:
    """Score de 1-10 + raison courte. Retourne {"score": int, "raison": str}"""
    try:
        time.sleep(0.5)
        prompt = f"""Secteur du professionnel : {secteur_client}

Texte réglementaire :
Titre : {texte.get('titre', '')}
Résumé : {texte.get('contenu_brut', '')[:2000]}

Évalue la pertinence de ce texte pour ce professionnel sur une échelle de 1 à 10.
10 = modification critique qu'il DOIT connaître immédiatement
7-9 = important, à lire cette semaine
4-6 = utile, à garder en veille
1-3 = peu pertinent pour son activité

Réponds UNIQUEMENT avec ce JSON valide (rien d'autre) :
{{"score": 7, "raison": "Ce décret modifie les obligations déclaratives TVA pour les micro-entreprises"}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Nettoie si Claude ajoute des backticks
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        return {"score": int(result.get("score", 5)), "raison": result.get("raison", "")}
    except Exception as e:
        logger.error(f"Erreur score_pertinence: {e}")
        return {"score": 5, "raison": "Analyse non disponible"}

def generer_resume(texte: dict, secteur_client: str) -> str:
    """Génère un résumé HTML structuré du texte pour le secteur donné."""
    try:
        time.sleep(0.5)
        prompt = f"""Secteur du professionnel : {secteur_client}

Texte réglementaire à analyser :
Titre : {texte.get('titre', '')}
Source : {texte.get('source', '')}
Date : {texte.get('date_publication', '')}
Contenu : {texte.get('contenu_brut', '')[:4000]}

Génère un résumé en 3 sections (format HTML avec balises p, ul, li, strong uniquement) :

1. <strong>Ce qui change</strong> : 2-3 phrases maximum, en langage clair, sans jargon
2. <strong>Ce que vous devez faire</strong> : liste d'actions concrètes (maximum 4 items)
3. <strong>Date limite</strong> : date d'entrée en vigueur ou deadline si applicable (sinon "Immédiat" ou "Pas de deadline")

Maximum 250 mots. Langage professionnel mais accessible."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erreur generer_resume: {e}")
        return f"<p>Résumé non disponible pour ce texte.</p>"

def generer_rapport_hebdo(client_data: dict, textes: list[dict]) -> str:
    """Génère l'email HTML complet du rapport hebdomadaire."""
    try:
        if not textes:
            return _rapport_vide(client_data)

        textes_str = "\n\n".join([
            f"[Score: {t.get('score', '?')}/10] {t.get('titre', '')}\n{t.get('resume_ia', '')[:500]}"
            for t in textes[:10]
        ])

        time.sleep(0.5)
        prompt = f"""Client : {client_data.get('nom', 'Cabinet')} ({client_data.get('secteurs', [])})

Textes réglementaires de la semaine (par ordre de pertinence) :
{textes_str}

Génère :
1. Une synthèse de 2-3 phrases "Cette semaine en bref" qui résume les grands enjeux
2. Une liste "Actions prioritaires" (max 3 items) : ce que le professionnel doit absolument faire cette semaine

Format : JSON avec clés "synthese" (string HTML) et "actions" (liste de strings)
Réponds UNIQUEMENT avec le JSON valide."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        ia_data = json.loads(text)

        return _build_email_html(client_data, textes, ia_data)
    except Exception as e:
        logger.error(f"Erreur generer_rapport_hebdo: {e}")
        return _build_email_html(client_data, textes, {"synthese": "Rapport de veille de la semaine.", "actions": []})

def _build_email_html(client_data: dict, textes: list[dict], ia_data: dict) -> str:
    from datetime import datetime
    nom = client_data.get("nom", "Cabinet")
    semaine = datetime.utcnow().strftime("%d/%m/%Y")
    app_url = __import__('app.config', fromlist=['APP_URL']).APP_URL

    textes_html = ""
    for t in textes[:8]:
        score = t.get("score", 5)
        badge_color = "#E24B4A" if score >= 9 else "#1D9E75" if score >= 7 else "#888780"
        badge_text = "URGENT" if score >= 9 else "IMPORTANT" if score >= 7 else "À NOTER"
        textes_html += f"""
        <tr>
          <td style="padding:16px 0;border-bottom:1px solid #f0f0f0;">
            <span style="background:{badge_color};color:white;font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px;margin-bottom:8px;display:inline-block">{badge_text} {score}/10</span>
            <p style="margin:6px 0;font-size:15px;font-weight:600;color:#1a2744">{t.get('titre','')[:100]}</p>
            <div style="font-size:13px;color:#555;line-height:1.6">{t.get('resume_ia','') or 'Résumé en cours de génération.'}</div>
            <a href="{t.get('url','#')}" style="color:#1D9E75;font-size:12px;text-decoration:none">Lire le texte officiel →</a>
          </td>
        </tr>"""

    actions_html = ""
    for action in ia_data.get("actions", []):
        actions_html += f'<li style="margin:6px 0;color:#333">{action}</li>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden">
  <tr><td style="background:#1a2744;padding:24px 32px">
    <p style="margin:0;color:#1D9E75;font-size:12px;font-weight:600;letter-spacing:0.1em">REGWATCH</p>
    <p style="margin:4px 0 0;color:white;font-size:20px;font-weight:600">Rapport de veille — semaine du {semaine}</p>
    <p style="margin:4px 0 0;color:#aab4c8;font-size:13px">{nom}</p>
  </td></tr>
  <tr><td style="padding:24px 32px">
    <div style="background:#f0f9f4;border-left:3px solid #1D9E75;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:24px">
      <p style="margin:0;font-size:13px;font-weight:600;color:#0F6E56;margin-bottom:4px">Cette semaine en bref</p>
      <div style="font-size:14px;color:#333;line-height:1.6">{ia_data.get('synthese','')}</div>
    </div>
    {'<div style="background:#fff9f0;border-left:3px solid #EF9F27;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:24px"><p style="margin:0;font-size:13px;font-weight:600;color:#854F0B;margin-bottom:8px">Actions prioritaires cette semaine</p><ul style="margin:0;padding-left:20px">' + actions_html + '</ul></div>' if actions_html else ''}
    <p style="font-size:14px;font-weight:600;color:#1a2744;margin:0 0 8px">{len(textes)} textes analysés cette semaine</p>
    <table width="100%">{textes_html}</table>
  </td></tr>
  <tr><td style="background:#f5f5f5;padding:16px 32px;text-align:center">
    <a href="{app_url}/dashboard" style="display:inline-block;background:#1a2744;color:white;text-decoration:none;padding:10px 24px;border-radius:6px;font-size:13px;margin-bottom:12px">Voir mon tableau de bord</a>
    <p style="margin:0;font-size:11px;color:#999">RegWatch · Veille réglementaire automatisée<br>
    <a href="{app_url}/unsubscribe" style="color:#999">Se désabonner</a></p>
  </td></tr>
</table></td></tr></table></body></html>"""

def _rapport_vide(client_data: dict) -> str:
    nom = client_data.get("nom", "Cabinet")
    return f"""<html><body style="font-family:sans-serif;padding:32px">
    <h2 style="color:#1a2744">Bonjour {nom},</h2>
    <p>Aucun texte réglementaire pertinent n'a été publié cette semaine pour votre secteur.</p>
    <p style="color:#555">RegWatch continue de surveiller le Journal Officiel et EUR-Lex chaque jour.<br>
    Nous vous alerterons immédiatement si un texte important est publié.</p>
    </body></html>"""
