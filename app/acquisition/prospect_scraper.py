"""
Scraper de prospects B2B
Trouve automatiquement les experts-comptables, avocats, notaires
via Google Maps + Pages Jaunes
"""
import httpx
import logging
import time
import re
from bs4 import BeautifulSoup
from app.database import get_db

logger = logging.getLogger(__name__)

METIERS = {
    "comptabilite": ["expert comptable", "cabinet comptable", "expertise comptable"],
    "droit":        ["avocat", "cabinet avocat", "cabinet juridique"],
    "immobilier":   ["notaire", "cabinet notarial", "agence immobilière"],
    "sante":        ["médecin", "cabinet médical", "clinique privée"],
}

VILLES_FR = [
    "Paris", "Lyon", "Marseille", "Bordeaux", "Lille", "Toulouse",
    "Nantes", "Strasbourg", "Montpellier", "Rennes", "Nice", "Grenoble",
    "Fort-de-France", "Pointe-à-Pitre", "Saint-Denis",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

def scrape_pages_jaunes(metier: str, ville: str, max_results: int = 10) -> list[dict]:
    """Scrape Pages Jaunes pour un métier et une ville donnés."""
    prospects = []
    try:
        query = metier.replace(" ", "+")
        url = f"https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui={query}&ou={ville}&univers=pagesjaunes"
        with httpx.Client(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning(f"Pages Jaunes {resp.status_code} pour {metier}/{ville}")
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.bi-content")[:max_results]
            for card in cards:
                nom = card.select_one(".bi-denomination")
                tel = card.select_one("[class*='phones']")
                adresse = card.select_one(".bi-address")
                email_tag = card.select_one("a[href^='mailto:']")
                site_tag = card.select_one("a.bi-website")
                nom_text = nom.get_text(strip=True) if nom else ""
                if not nom_text:
                    continue
                email = email_tag["href"].replace("mailto:", "") if email_tag else None
                site = site_tag["href"] if site_tag else None
                # Si pas d'email direct, on tente de l'extraire du site
                if not email and site:
                    email = _extract_email_from_site(site, client)
                if not email:
                    continue  # On ne garde que les prospects avec email
                prospects.append({
                    "nom": nom_text,
                    "email": email.lower().strip(),
                    "telephone": tel.get_text(strip=True) if tel else "",
                    "adresse": adresse.get_text(strip=True) if adresse else ville,
                    "ville": ville,
                    "secteur": _metier_to_secteur(metier),
                    "source": "pages_jaunes",
                    "site": site or "",
                })
        logger.info(f"Pages Jaunes {metier}/{ville}: {len(prospects)} prospects avec email")
    except Exception as e:
        logger.error(f"Erreur Pages Jaunes {metier}/{ville}: {e}")
    return prospects

def _extract_email_from_site(url: str, client: httpx.Client) -> str | None:
    """Tente d'extraire un email depuis la page d'accueil d'un site."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = client.get(url, timeout=8, follow_redirects=True)
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', resp.text)
        # Filtre les emails génériques/spam
        blacklist = ["noreply", "no-reply", "contact@pagesjaunes", "info@pagesjaunes", "webmaster", "admin@"]
        for email in emails:
            if not any(b in email.lower() for b in blacklist) and len(email) < 60:
                return email
    except:
        pass
    return None

def _metier_to_secteur(metier: str) -> str:
    for secteur, metiers in METIERS.items():
        if any(m in metier.lower() for m in metiers):
            return secteur
    return "general"

def scrape_all_prospects(secteurs: list[str] = None, villes: list[str] = None, max_par_combo: int = 5) -> int:
    """
    Lance le scraping complet pour tous les secteurs et villes.
    Sauvegarde en BDD. Retourne le nombre de prospects trouvés.
    """
    secteurs = secteurs or list(METIERS.keys())
    villes = villes or VILLES_FR[:5]  # Commence par 5 villes
    db = get_db()
    total = 0

    for secteur in secteurs:
        metiers = METIERS.get(secteur, [secteur])
        for metier in metiers[:1]:  # 1 requête par secteur pour éviter le ban
            for ville in villes:
                prospects = scrape_pages_jaunes(metier, ville, max_par_combo)
                for p in prospects:
                    try:
                        # Vérifie si déjà en base
                        existing = db.table("prospects").select("id").eq("email", p["email"]).execute()
                        if existing.data:
                            continue
                        db.table("prospects").insert({
                            "email": p["email"],
                            "nom": p["nom"],
                            "telephone": p["telephone"],
                            "ville": p["ville"],
                            "secteur": p["secteur"],
                            "site": p["site"],
                            "source": p["source"],
                            "statut": "nouveau",
                        }).execute()
                        total += 1
                    except Exception as e:
                        logger.error(f"Erreur save prospect {p.get('email')}: {e}")
                time.sleep(2)  # Pause entre chaque requête pour éviter le ban

    logger.info(f"Scraping prospects terminé: {total} nouveaux prospects")
    return total
