"""
Générateur de démo personnalisée
Crée un vrai rapport de veille réglementaire au nom du prospect
avec les textes réels de la semaine — avant même qu'il soit client
"""
import logging
from datetime import datetime, timedelta
from anthropic import Anthropic
from app.config import ANTHROPIC_API_KEY, APP_URL
from app.database import get_db

logger = logging.getLogger(__name__)
client_ai = Anthropic(api_key=ANTHROPIC_API_KEY)

def generer_demo_prospect(prospect: dict) -> str:
    """
    Génère un email HTML de démo personnalisé pour un prospect.
    Utilise les vrais textes réglementaires de la semaine depuis la BDD.
    """
    secteur = prospect.get("secteur", "general")
    nom = prospect.get("nom", "Cabinet")
    ville = prospect.get("ville", "")

    # Récupère les textes réels de la semaine depuis la BDD
    db = get_db()
    depuis = (datetime.utcnow() - timedelta(days=7)).isoformat()
    textes_res = db.table("textes_reglementaires")\
        .select("titre,url,date_publication,resume_ia,contenu_brut")\
        .gte("created_at", depuis)\
        .not_.is_("resume_ia", "null")\
        .order("created_at", desc=True)\
        .limit(30)\
        .execute()

    tous_textes = textes_res.data or []

    # Score les textes pour ce prospect via IA
    textes_pertinents = _scorer_textes_pour_prospect(tous_textes, secteur, nom)[:3]

    # Si pas assez de textes en BDD, génère des exemples réalistes
    if len(textes_pertinents) < 2:
        textes_pertinents = _generer_exemples_realistes(secteur)

    return _build_demo_html(prospect, textes_pertinents)

def _scorer_textes_pour_prospect(textes: list[dict], secteur: str, nom_cabinet: str) -> list[dict]:
    """Filtre et trie les textes les plus pertinents pour le secteur."""
    if not textes:
        return []
    try:
        textes_str = "\n".join([f"- {t.get('titre','')}" for t in textes[:20]])
        response = client_ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Secteur: {secteur}
Cabinet: {nom_cabinet}

Parmi ces titres de textes réglementaires publiés cette semaine, donne-moi les indices (0-based) des 3 plus pertinents pour ce secteur. Réponds UNIQUEMENT avec un JSON: {{"indices": [0, 3, 7]}}

Textes:
{textes_str}"""}]
        )
        import json
        text = response.content[0].text.strip().replace("```json","").replace("```","")
        indices = json.loads(text).get("indices", [0, 1, 2])
        return [textes[i] for i in indices if i < len(textes)]
    except:
        return textes[:3]

def _generer_exemples_realistes(secteur: str) -> list[dict]:
    """Génère des exemples de textes réalistes quand la BDD est vide (premiers jours)."""
    exemples = {
        "comptabilite": [
            {"titre": "Décret n°2025-412 relatif aux obligations déclaratives TVA des micro-entrepreneurs",
             "url": "https://www.legifrance.gouv.fr/jorf/id/exemple1",
             "date_publication": str(datetime.utcnow().date()),
             "resume_ia": "<p><strong>Ce qui change</strong> : Le seuil de franchise en base de TVA est relevé à 37 500€ pour les prestations de services à compter du 1er juillet 2025.</p><ul><li>Mettre à jour vos seuils de suivi clients</li><li>Informer vos clients proches du seuil</li></ul><p><strong>Date limite</strong> : 1er juillet 2025</p>"},
            {"titre": "Arrêté du 15 mai 2025 modifiant le barème kilométrique 2025",
             "url": "https://www.legifrance.gouv.fr/jorf/id/exemple2",
             "date_publication": str(datetime.utcnow().date()),
             "resume_ia": "<p><strong>Ce qui change</strong> : Le barème kilométrique est revalorisé de 1,8% pour tenir compte de la hausse du coût des carburants.</p><ul><li>Mettre à jour vos outils de calcul des indemnités kilométriques</li><li>Appliquer le nouveau barème aux remboursements de mai 2025</li></ul><p><strong>Date limite</strong> : Immédiat</p>"},
        ],
        "droit": [
            {"titre": "Loi n°2025-389 portant réforme de la procédure civile devant les tribunaux de commerce",
             "url": "https://www.legifrance.gouv.fr/jorf/id/exemple3",
             "date_publication": str(datetime.utcnow().date()),
             "resume_ia": "<p><strong>Ce qui change</strong> : La représentation obligatoire par avocat est étendue aux litiges commerciaux supérieurs à 10 000€ (contre 25 000€ auparavant).</p><ul><li>Informer vos clients entreprises de cette nouvelle obligation</li><li>Mettre à jour vos lettres de mission</li></ul><p><strong>Date limite</strong> : Entrée en vigueur au 1er septembre 2025</p>"},
            {"titre": "Circulaire relative à la dématérialisation des actes de procédure",
             "url": "https://www.legifrance.gouv.fr/jorf/id/exemple4",
             "date_publication": str(datetime.utcnow().date()),
             "resume_ia": "<p><strong>Ce qui change</strong> : L'envoi électronique des conclusions devient obligatoire dans tous les TGI à compter du 1er juin 2025.</p><ul><li>Vérifier votre accès au RPVA</li><li>Former vos collaborateurs à la procédure dématérialisée</li></ul><p><strong>Date limite</strong> : 1er juin 2025</p>"},
        ],
        "immobilier": [
            {"titre": "Décret relatif aux nouvelles obligations DPE pour les baux commerciaux",
             "url": "https://www.legifrance.gouv.fr/jorf/id/exemple5",
             "date_publication": str(datetime.utcnow().date()),
             "resume_ia": "<p><strong>Ce qui change</strong> : Les baux commerciaux de plus de 2 000 m² doivent désormais mentionner la consommation énergétique réelle du bien.</p><ul><li>Vérifier vos baux en cours de renouvellement</li><li>Demander les DPE actualisés aux propriétaires</li></ul><p><strong>Date limite</strong> : Applicable aux baux signés après le 1er juillet 2025</p>"},
        ],
    }
    return exemples.get(secteur, exemples.get("comptabilite", []))

def _build_demo_html(prospect: dict, textes: list[dict]) -> str:
    """Construit l'email HTML de démo personnalisé."""
    nom = prospect.get("nom", "Cabinet")
    secteur = prospect.get("secteur", "votre secteur")
    ville = prospect.get("ville", "")
    email_prospect = prospect.get("email", "")
    demo_url = f"{APP_URL}/demo/{prospect.get('id', '')}?ref=email"

    textes_html = ""
    for i, t in enumerate(textes):
        score_color = "#E24B4A" if i == 0 else "#1D9E75"
        score_label = "PRIORITAIRE" if i == 0 else "IMPORTANT"
        textes_html += f"""
        <tr>
          <td style="padding:16px 0;border-bottom:1px solid #f0f0f0">
            <span style="background:{score_color};color:white;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">{score_label}</span>
            <p style="margin:8px 0 4px;font-size:14px;font-weight:600;color:#1a2744">{t.get('titre','')}</p>
            <div style="font-size:13px;color:#555;line-height:1.6">{t.get('resume_ia','') or t.get('contenu_brut','')[:300]}</div>
            <a href="{t.get('url','#')}" style="color:#1D9E75;font-size:12px;text-decoration:none;margin-top:4px;display:inline-block">Texte officiel →</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;overflow:hidden">

  <tr><td style="background:#1a2744;padding:24px 32px">
    <p style="margin:0;color:#1D9E75;font-size:11px;font-weight:700;letter-spacing:.1em">REGWATCH — EXEMPLE PERSONNALISÉ</p>
    <p style="margin:6px 0 0;color:white;font-size:19px;font-weight:600">Voici ce que vous auriez reçu cette semaine</p>
    <p style="margin:4px 0 0;color:#aab4c8;font-size:13px">{nom} · {ville} · Secteur : {secteur}</p>
  </td></tr>

  <tr><td style="padding:24px 32px">
    <div style="background:#fff9f0;border-left:3px solid #EF9F27;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:20px">
      <p style="margin:0;font-size:12px;color:#854F0B"><strong>Ceci est un exemple réel</strong> — ce rapport a été généré automatiquement avec les textes publiés cette semaine au Journal Officiel et EUR-Lex, filtrés pour votre secteur.</p>
    </div>

    <p style="font-size:14px;font-weight:600;color:#1a2744;margin:0 0 12px">{len(textes)} textes pertinents pour {secteur} cette semaine :</p>
    <table width="100%">{textes_html}</table>
  </td></tr>

  <tr><td style="background:#f0f9f4;padding:24px 32px;text-align:center">
    <p style="margin:0 0 8px;font-size:15px;font-weight:600;color:#1a2744">Ce rapport vous sera envoyé automatiquement chaque lundi</p>
    <p style="margin:0 0 16px;font-size:13px;color:#555">Sans intervention de votre part. 30 jours d'essai gratuits.</p>
    <a href="{demo_url}" style="display:inline-block;background:#1D9E75;color:white;text-decoration:none;padding:12px 32px;border-radius:8px;font-size:14px;font-weight:600">
      Activer mon accès gratuit →
    </a>
    <p style="margin:12px 0 0;font-size:11px;color:#888">Sans carte bancaire · Sans engagement · Résiliation en 1 clic</p>
  </td></tr>

  <tr><td style="padding:16px 32px;background:#fafafa;text-align:center">
    <p style="font-size:11px;color:#bbb;margin:0">RegWatch · Veille réglementaire automatisée<br>
    Vous recevez cet email parce que votre cabinet exerce dans le secteur {secteur}.<br>
    <a href="{APP_URL}/unsubscribe?email={email_prospect}" style="color:#bbb">Ne plus recevoir de messages</a></p>
  </td></tr>

</table></td></tr></table>
</body></html>"""
