import httpx
import logging
import pdfplumber
import io
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SECTEUR_KEYWORDS = {
    "comptabilite": ["TVA", "comptable", "fiscal", "impôt", "bilan", "déclaration", "cotisation", "URSSAF", "liasse"],
    "droit": ["avocat", "barreau", "juridiction", "procédure", "tribunal", "contrat", "responsabilité"],
    "immobilier": ["bail", "loyer", "propriétaire", "locataire", "DPE", "diagnostic", "copropriété", "PLU"],
    "sante": ["médecin", "patient", "médicament", "ANSM", "HAS", "ordonnance", "pharmacie", "clinique"],
    "finance": ["AMF", "ACPR", "bancaire", "assurance", "crédit", "investissement", "MIFID"],
    "rh": ["salarié", "contrat de travail", "licenciement", "convention collective", "SMIC", "congé"],
}

class JournalOfficielScraper(BaseScraper):
    source_name = "journal_officiel_fr"
    base_url = "https://www.legifrance.gouv.fr"

    def scrape(self) -> list[dict]:
        textes = []
        try:
            last = self.get_last_scraping()
            depuis = last if last else datetime.utcnow() - timedelta(days=7)
            logger.info(f"[JO] Scraping depuis {depuis.date()}")

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; RegWatch/1.0; veille réglementaire)",
                "Accept": "text/html,application/xhtml+xml",
            }

            # Utilise l'API Légifrance (accès public sans authentification pour les textes récents)
            api_url = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/search"
            payload = {
                "rechercheFinalite": "TOUS_TEXTES",
                "fond": "JORF",
                "sort": "PUBLICATION_DATE_DESC",
                "pageNumber": 1,
                "pageSize": 50,
                "datePublicationDebut": depuis.strftime("%Y-%m-%d"),
                "datePublicationFin": datetime.utcnow().strftime("%Y-%m-%d"),
            }

            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(api_url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            t = self._parse_api_item(item)
                            if t:
                                textes.append(t)
            except Exception as e:
                logger.warning(f"[JO] API PISTE indisponible, fallback scraping: {e}")
                textes = self._scrape_fallback(depuis, headers)

            logger.info(f"[JO] {len(textes)} textes trouvés")
            return textes

        except Exception as e:
            logger.error(f"[JO] Erreur scraping: {e}")
            self._log_scraping(0, 0, str(e))
            return []

    def _parse_api_item(self, item: dict) -> dict | None:
        try:
            titre = item.get("title", "")
            url = f"{self.base_url}/jorf/id/{item.get('id', '')}"
            date_str = item.get("publicationDate", "")
            date_pub = datetime.strptime(date_str[:10], "%Y-%m-%d").date() if date_str else None
            contenu = item.get("extract", "") + " " + item.get("nature", "")
            secteurs = self._detect_secteurs(titre + " " + contenu)
            return {
                "titre": titre,
                "url": url,
                "date_publication": str(date_pub) if date_pub else None,
                "contenu": contenu[:10000],
                "secteurs": secteurs,
            }
        except:
            return None

    def _scrape_fallback(self, depuis: datetime, headers: dict) -> list[dict]:
        """Fallback: scrape la page HTML du JO si l'API est indisponible."""
        textes = []
        try:
            url = f"{self.base_url}/jorf/jo"
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=headers)
                soup = BeautifulSoup(resp.text, "lxml")
                for link in soup.select("a[href*='/jorf/id/']")[:30]:
                    href = link.get("href", "")
                    titre = link.get_text(strip=True)
                    if not titre or len(titre) < 10:
                        continue
                    full_url = self.base_url + href if href.startswith("/") else href
                    secteurs = self._detect_secteurs(titre)
                    textes.append({
                        "titre": titre,
                        "url": full_url,
                        "date_publication": str(depuis.date()),
                        "contenu": titre,
                        "secteurs": secteurs,
                    })
        except Exception as e:
            logger.error(f"[JO] Fallback scraping échoué: {e}")
        return textes

    def _detect_secteurs(self, text: str) -> list[str]:
        text_lower = text.lower()
        detected = []
        for secteur, keywords in SECTEUR_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                detected.append(secteur)
        return detected
