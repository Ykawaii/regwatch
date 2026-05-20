import logging
from datetime import datetime
from abc import ABC, abstractmethod
from app.database import get_db

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    source_name: str = ""

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Retourne une liste de textes réglementaires."""
        pass

    def save_to_db(self, textes: list[dict]) -> int:
        db = get_db()
        saved = 0
        for t in textes:
            try:
                existing = db.table("textes_reglementaires").select("id").eq("url", t["url"]).execute()
                if existing.data:
                    continue
                db.table("textes_reglementaires").insert({
                    "source": self.source_name,
                    "titre": t["titre"][:500],
                    "url": t["url"],
                    "date_publication": t.get("date_publication"),
                    "contenu_brut": t.get("contenu", "")[:50000],
                    "secteurs_concernes": t.get("secteurs", []),
                }).execute()
                saved += 1
            except Exception as e:
                logger.error(f"Erreur save texte {t.get('url')}: {e}")
        self._log_scraping(len(textes), saved)
        return saved

    def _log_scraping(self, found: int, saved: int, error: str = None):
        try:
            db = get_db()
            db.table("scraping_log").upsert({
                "source": self.source_name,
                "derniere_execution": datetime.utcnow().isoformat(),
                "nb_textes_trouves": found,
                "erreur": error,
            }, on_conflict="source").execute()
        except Exception as e:
            logger.error(f"Erreur log scraping: {e}")

    def get_last_scraping(self) -> datetime | None:
        try:
            db = get_db()
            res = db.table("scraping_log").select("derniere_execution").eq("source", self.source_name).execute()
            if res.data:
                return datetime.fromisoformat(res.data[0]["derniere_execution"])
        except:
            pass
        return None
