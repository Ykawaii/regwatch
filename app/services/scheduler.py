import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Paris")

def start_scheduler():
    # Scraping quotidien à 6h00
    scheduler.add_job(run_daily_scraping, CronTrigger(hour=6, minute=0), id="scraping_quotidien", replace_existing=True)
    # Rapport hebdomadaire lundi 8h00
    scheduler.add_job(run_weekly_reports, CronTrigger(day_of_week="mon", hour=8, minute=0), id="rapports_hebdo", replace_existing=True)
    # Nettoyage mensuel 1er du mois 3h00
    scheduler.add_job(run_monthly_cleanup, CronTrigger(day=1, hour=3, minute=0), id="nettoyage_mensuel", replace_existing=True)
    # Scraping prospects + envoi cold emails — mardi et jeudi 9h
    scheduler.add_job(run_acquisition_campaign, CronTrigger(day_of_week="tue,thu", hour=9, minute=0), id="acquisition", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler démarré — scraping 6h, rapports lundi 8h, acquisition mar+jeu 9h, cleanup 1er du mois 3h")

async def run_daily_scraping():
    from app.scrapers.journal_officiel import JournalOfficielScraper
    from app.scrapers.eurlex import EurLexScraper
    from app.services.analyzer import score_pertinence, generer_resume
    from app.services.emailer import send_alert
    from app.database import get_db

    start = datetime.utcnow()
    logger.info("[SCHEDULER] Début scraping quotidien")
    total_textes = 0
    total_alertes = 0

    try:
        db = get_db()

        # Scraping des sources
        for ScraperClass in [JournalOfficielScraper, EurLexScraper]:
            scraper = ScraperClass()
            textes = scraper.scrape()
            saved = scraper.save_to_db(textes)
            total_textes += saved
            logger.info(f"[SCHEDULER] {scraper.source_name}: {len(textes)} trouvés, {saved} sauvegardés")

        # Récupère les textes non encore analysés
        textes_res = db.table("textes_reglementaires")\
            .select("*")\
            .is_("resume_ia", "null")\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()

        nouveaux_textes = textes_res.data or []

        # Récupère tous les clients actifs
        clients_res = db.table("clients").select("*").eq("actif", True).execute()
        clients = clients_res.data or []

        for texte in nouveaux_textes:
            # Génère le résumé IA une fois (pas par client)
            all_secteurs = " ".join(texte.get("secteurs_concernes", []) or ["general"])
            resume = generer_resume(texte, all_secteurs)
            db.table("textes_reglementaires").update({"resume_ia": resume}).eq("id", texte["id"]).execute()

            # Score pour chaque client
            for client_data in clients:
                secteurs_client = client_data.get("secteurs") or ["general"]
                for secteur in secteurs_client:
                    result = score_pertinence(texte, secteur)
                    score = result["score"]

                    if score >= 6:
                        # Crée une alerte
                        db.table("alertes").insert({
                            "client_id": client_data["id"],
                            "texte_id": texte["id"],
                            "score": score,
                            "envoyee": False,
                        }).execute()
                        total_alertes += 1

                        # Alerte immédiate si score critique et plan pro/expert
                        from app.config import PLAN_LIMITS
                        plan = client_data.get("plan", "starter")
                        if score >= 9 and PLAN_LIMITS.get(plan, {}).get("alertes_immediates"):
                            texte_with_score = {**texte, "score": score, "resume_ia": resume}
                            send_alert(client_data["email"], client_data.get("nom", ""), texte_with_score)
                            db.table("alertes")\
                                .update({"envoyee": True, "date_envoi": datetime.utcnow().isoformat()})\
                                .eq("client_id", client_data["id"])\
                                .eq("texte_id", texte["id"])\
                                .execute()
                        break  # Un score par client suffit

        duree = (datetime.utcnow() - start).seconds
        logger.info(f"[SCHEDULER] Scraping terminé en {duree}s — {total_textes} textes, {total_alertes} alertes")

    except Exception as e:
        logger.error(f"[SCHEDULER] Erreur scraping quotidien: {e}")

async def run_weekly_reports():
    from app.services.analyzer import generer_rapport_hebdo
    from app.services.emailer import send_rapport
    from app.database import get_db

    logger.info("[SCHEDULER] Génération rapports hebdomadaires")
    db = get_db()

    try:
        clients_res = db.table("clients").select("*").eq("actif", True).execute()
        clients = clients_res.data or []
        semaine_debut = (datetime.utcnow() - timedelta(days=7)).date()

        for client_data in clients:
            try:
                # Récupère les alertes de la semaine pour ce client
                alertes_res = db.table("alertes")\
                    .select("*, textes_reglementaires(*)")\
                    .eq("client_id", client_data["id"])\
                    .gte("created_at", semaine_debut.isoformat())\
                    .order("score", desc=True)\
                    .limit(10)\
                    .execute()

                textes_semaine = []
                for alerte in (alertes_res.data or []):
                    texte = alerte.get("textes_reglementaires", {})
                    if texte:
                        texte["score"] = alerte.get("score", 5)
                        textes_semaine.append(texte)

                rapport_html = generer_rapport_hebdo(client_data, textes_semaine)
                send_rapport(client_data["email"], client_data.get("nom", ""), rapport_html)

                # Sauvegarde le rapport
                db.table("rapports_hebdo").insert({
                    "client_id": client_data["id"],
                    "semaine_debut": str(semaine_debut),
                    "contenu_html": rapport_html[:100000],
                    "envoyee": True,
                }).execute()

                logger.info(f"[SCHEDULER] Rapport envoyé à {client_data['email']} ({len(textes_semaine)} textes)")

            except Exception as e:
                logger.error(f"[SCHEDULER] Erreur rapport pour {client_data.get('email')}: {e}")

    except Exception as e:
        logger.error(f"[SCHEDULER] Erreur run_weekly_reports: {e}")

async def run_monthly_cleanup():
    from app.database import get_db
    db = get_db()
    six_mois = (datetime.utcnow() - timedelta(days=180)).isoformat()
    try:
        res = db.table("textes_reglementaires").delete().lt("created_at", six_mois).execute()
        logger.info(f"[SCHEDULER] Nettoyage mensuel — textes anciens supprimés")
    except Exception as e:
        logger.error(f"[SCHEDULER] Erreur nettoyage: {e}")

async def run_acquisition_campaign():
    """Lance automatiquement le scraping prospects + campagne cold email."""
    from app.acquisition.prospect_scraper import scrape_all_prospects
    from app.acquisition.cold_email import run_cold_email_campaign

    logger.info("[ACQUISITION] Démarrage campagne automatique")
    try:
        # 1. Scrape de nouveaux prospects
        nb_nouveaux = scrape_all_prospects(max_par_combo=5)
        logger.info(f"[ACQUISITION] {nb_nouveaux} nouveaux prospects trouvés")

        # 2. Lance les emails
        stats = run_cold_email_campaign(batch_size=20)
        logger.info(f"[ACQUISITION] Campagne terminée: {stats}")
    except Exception as e:
        logger.error(f"[ACQUISITION] Erreur: {e}")
