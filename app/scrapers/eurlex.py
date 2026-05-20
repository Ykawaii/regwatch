import httpx
import logging
from datetime import datetime, timedelta
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class EurLexScraper(BaseScraper):
    source_name = "eur_lex"
    api_url = "https://eur-lex.europa.eu/api/search"

    def scrape(self) -> list[dict]:
        textes = []
        try:
            last = self.get_last_scraping()
            depuis = last if last else datetime.utcnow() - timedelta(days=7)
            logger.info(f"[EURLEX] Scraping depuis {depuis.date()}")

            # EUR-Lex SPARQL endpoint (accès public)
            sparql_url = "https://publications.europa.eu/webapi/rdf/sparql"
            query = f"""
            SELECT ?uri ?title ?date ?type WHERE {{
              ?uri a <http://publications.europa.eu/ontology/cdm#legislation_secondary> ;
                   <http://publications.europa.eu/ontology/cdm#work_date_document> ?date ;
                   <http://publications.europa.eu/ontology/cdm#work_has_expression> ?expr .
              ?expr <http://publications.europa.eu/ontology/cdm#expression_title> ?title ;
                    <http://publications.europa.eu/ontology/cdm#expression_uses_language> <http://publications.europa.eu/resource/authority/language/FRA> .
              FILTER(?date >= "{depuis.strftime('%Y-%m-%d')}"^^xsd:date)
            }}
            ORDER BY DESC(?date)
            LIMIT 30
            """

            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(sparql_url, params={"query": query, "format": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json()
                        for binding in data.get("results", {}).get("bindings", []):
                            t = self._parse_sparql_binding(binding)
                            if t:
                                textes.append(t)
            except Exception as e:
                logger.warning(f"[EURLEX] SPARQL indisponible, fallback RSS: {e}")
                textes = self._scrape_rss(depuis)

            logger.info(f"[EURLEX] {len(textes)} textes trouvés")
            return textes

        except Exception as e:
            logger.error(f"[EURLEX] Erreur: {e}")
            self._log_scraping(0, 0, str(e))
            return []

    def _parse_sparql_binding(self, binding: dict) -> dict | None:
        try:
            uri = binding.get("uri", {}).get("value", "")
            titre = binding.get("title", {}).get("value", "")
            date_str = binding.get("date", {}).get("value", "")
            date_pub = date_str[:10] if date_str else None
            if not uri or not titre:
                return None
            return {
                "titre": titre[:500],
                "url": uri,
                "date_publication": date_pub,
                "contenu": titre,
                "secteurs": [],
            }
        except:
            return None

    def _scrape_rss(self, depuis: datetime) -> list[dict]:
        """Fallback: flux RSS EUR-Lex JO série L (actes législatifs)."""
        textes = []
        try:
            rss_url = "https://eur-lex.europa.eu/oj/direct-access.html"
            feed_url = f"https://eur-lex.europa.eu/oj/ojs-rss.xml"
            with httpx.Client(timeout=20) as client:
                resp = client.get(feed_url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "xml")
                for item in soup.find_all("item")[:20]:
                    titre = item.find("title")
                    link = item.find("link")
                    pub_date = item.find("pubDate")
                    if titre and link:
                        textes.append({
                            "titre": titre.get_text(strip=True)[:500],
                            "url": link.get_text(strip=True),
                            "date_publication": str(depuis.date()),
                            "contenu": titre.get_text(strip=True),
                            "secteurs": [],
                        })
        except Exception as e:
            logger.error(f"[EURLEX] RSS fallback échoué: {e}")
        return textes
