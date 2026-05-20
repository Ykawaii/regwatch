"""
Route /demo/{prospect_id}
Page personnalisée que le prospect voit en cliquant dans l'email
Montre son rapport en temps réel + bouton Stripe pour s'abonner
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.database import get_db
from app.config import APP_URL
from app.acquisition.demo_generator import generer_demo_prospect

router = APIRouter()

@router.get("/demo/{prospect_id}", response_class=HTMLResponse)
async def demo_page(prospect_id: str, ref: str = "direct"):
    db = get_db()

    # Récupère le prospect
    res = db.table("prospects").select("*").eq("id", prospect_id).execute()
    if not res.data:
        return HTMLResponse("<html><body><h2>Lien expiré</h2><p>Contactez contact@regwatch.app</p></body></html>")

    prospect = res.data[0]

    # Marque comme "démo vue"
    db.table("prospects").update({"statut": "demo_vue", "ref": ref}).eq("id", prospect_id).execute()

    nom = prospect.get("nom", "Cabinet")
    secteur = prospect.get("secteur", "votre secteur")
    email = prospect.get("email", "")

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Votre rapport RegWatch — {nom}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;color:#333}}
nav{{background:#1a2744;padding:0 24px;height:56px;display:flex;align-items:center;gap:12px}}
.logo{{color:#1D9E75;font-weight:700;font-size:16px}}
.nav-tag{{color:#aab4c8;font-size:12px}}
.container{{max-width:680px;margin:0 auto;padding:24px 16px}}
.banner{{background:#1D9E75;color:white;border-radius:8px;padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:12px}}
.banner-text{{font-size:14px;line-height:1.5}}
.cta-box{{background:white;border:2px solid #1D9E75;border-radius:12px;padding:24px;text-align:center;margin-bottom:20px}}
.cta-title{{font-size:18px;font-weight:600;color:#1a2744;margin-bottom:8px}}
.cta-sub{{font-size:13px;color:#666;margin-bottom:16px;line-height:1.6}}
.cta-btn{{display:inline-block;background:#1D9E75;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;border:none;width:100%}}
.cta-btn:hover{{background:#169670}}
.cta-note{{font-size:11px;color:#999;margin-top:10px}}
.report-frame{{background:white;border-radius:8px;border:1px solid #e8e8e8;overflow:hidden}}
.report-header{{background:#f8f9fb;padding:12px 20px;border-bottom:1px solid #e8e8e8;font-size:12px;color:#888;display:flex;justify-content:space-between}}
</style>
</head>
<body>
<nav>
  <span class="logo">REGWATCH</span>
  <span class="nav-tag">Rapport personnalisé pour {nom}</span>
</nav>
<div class="container">

  <div class="banner">
    <span style="font-size:24px">👇</span>
    <div class="banner-text">
      <strong>Voici votre rapport de cette semaine</strong><br>
      Généré automatiquement pour <strong>{nom}</strong> · Secteur {secteur}
    </div>
  </div>

  <div class="cta-box">
    <div class="cta-title">Ce rapport vous sera envoyé chaque lundi</div>
    <div class="cta-sub">Activez RegWatch maintenant et ne ratez plus jamais une obligation réglementaire.<br>
    <strong>30 jours gratuits</strong> — sans carte bancaire, sans engagement.</div>
    <button class="cta-btn" onclick="checkout()">Activer mon accès gratuit →</button>
    <div class="cta-note">Sans CB · Résiliation en 1 clic · Données 100% sécurisées</div>
  </div>

  <div class="report-frame">
    <div class="report-header">
      <span>Rapport de veille réglementaire — {secteur}</span>
      <span>Cette semaine</span>
    </div>
    <iframe id="report-iframe" style="width:100%;border:none;min-height:600px" srcdoc="Chargement..."></iframe>
  </div>

</div>

<script>
// Charge le contenu du rapport dans l'iframe
fetch('/api/demo-content/{prospect_id}')
  .then(r => r.text())
  .then(html => {{
    document.getElementById('report-iframe').srcdoc = html;
  }});

async function checkout() {{
  try {{
    const resp = await fetch('/create-checkout-session', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        plan: 'pro',
        email: '{email}',
        secteurs: ['{secteur}']
      }})
    }});
    const data = await resp.json();
    if (data.url) window.location.href = data.url;
  }} catch(e) {{
    alert('Erreur. Contactez contact@regwatch.app');
  }}
}}
</script>
</body></html>""")

@router.get("/api/demo-content/{prospect_id}")
async def demo_content(prospect_id: str):
    """Retourne le HTML du rapport pour l'iframe."""
    db = get_db()
    res = db.table("prospects").select("*").eq("id", prospect_id).execute()
    if not res.data:
        return HTMLResponse("<p>Rapport non disponible.</p>")
    prospect = res.data[0]
    html = generer_demo_prospect(prospect)
    return HTMLResponse(html)
