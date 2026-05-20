# RegWatch — Veille réglementaire automatisée

SaaS de veille réglementaire B2B avec acquisition client 100% automatisée.

## Ce que fait le système automatiquement

| Heure | Action |
|-------|--------|
| 6h00 tous les jours | Scraping Journal Officiel + EUR-Lex |
| 6h05 tous les jours | Analyse IA (scoring + résumés) pour chaque client |
| 6h10 tous les jours | Alertes immédiates si texte critique (score ≥ 9) |
| 9h00 mar + jeu | Scraping prospects Pages Jaunes + envoi cold emails |
| 8h00 chaque lundi | Rapport hebdomadaire PDF envoyé à chaque client |
| 3h00 le 1er du mois | Nettoyage BDD |

## Déploiement Railway en 10 étapes

### 1. Comptes requis (tous gratuits au démarrage)
- [Railway.app](https://railway.app) — hébergement
- [Supabase.com](https://supabase.com) — base de données
- [Resend.com](https://resend.com) — envoi emails
- [LemonSqueezy.com](https://lemonsqueezy.com) — paiements (compte gratuit)

### 2. Supabase — Base de données
1. Créer un projet sur supabase.com
2. Aller dans SQL Editor → New Query
3. Coller et exécuter le contenu de `schema.sql`
4. Récupérer dans Settings → API : `Project URL` et `anon public key`

### 3. Resend — Emails
1. Créer un compte sur resend.com
2. Ajouter et vérifier ton domaine (ex: regwatch.app)
3. Créer une API Key → noter la clé `re_...`
4. Configurer le domaine d'envoi : `demo@regwatch.app` et `alertes@regwatch.app`

### 4. Lemon Squeezy — Paiements (5 minutes)
1. Créer un compte sur [lemonsqueezy.com](https://lemonsqueezy.com)
2. Créer un **Store** (ton magasin) → noter le **Store ID** (visible dans l'URL)
3. Créer 3 **Products** de type Subscription :
   - Starter : 99$/mois — cocher "Free trial" → 30 jours
   - Pro : 299$/mois — cocher "Free trial" → 30 jours
   - Expert : 599$/mois — cocher "Free trial" → 30 jours
   - Pour chaque product, noter le **Variant ID** (visible dans l'URL de l'édition)
4. Settings → API → **Generate API Key** → noter la clé
5. Settings → Webhooks → Add webhook :
   - URL : `https://TON-APP.railway.app/webhook/lemonsqueezy`
   - Events : `subscription_created`, `subscription_updated`, `subscription_cancelled`, `subscription_expired`, `subscription_payment_failed`
   - Signing secret → noter la valeur

### 5. Railway — Déploiement
1. Fork ce repo sur GitHub
2. Aller sur railway.app → New Project → Deploy from GitHub
3. Sélectionner le repo
4. Dans Variables → Add toutes les variables de `.env.example` avec tes vraies valeurs
5. Railway détecte automatiquement Python via nixpacks

### 6. Variables d'environnement Railway
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...
PAYPAL_CLIENT_ID=AXxx...
PAYPAL_CLIENT_SECRET=EXxx...
PAYPAL_MODE=live
PAYPAL_PLAN_STARTER=P-XXXXXXXXXXXXXXXXXXXXXXXX
PAYPAL_PLAN_PRO=P-XXXXXXXXXXXXXXXXXXXXXXXX
PAYPAL_PLAN_EXPERT=P-XXXXXXXXXXXXXXXXXXXXXXXX
PAYPAL_WEBHOOK_ID=WHxx...
JWT_SECRET=un_secret_aleatoire_de_32_caracteres_minimum
APP_URL=https://ton-app.railway.app
```

### 7. Installation Playwright sur Railway
Ajouter ces variables supplémentaires :
```
PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright
```
Et dans le build command Railway : `pip install playwright && playwright install chromium`

### 8. Vérification
- Ouvrir `https://ton-app.railway.app` → landing page visible
- Ouvrir `https://ton-app.railway.app/health` → `{"status": "ok"}`
- Vérifier les logs Railway : le scheduler doit démarrer sans erreur

### 9. Premier lancement manuel
Pour lancer immédiatement sans attendre le cron :
```
# Dans Railway → Terminal
python -c "import asyncio; from app.services.scheduler import run_daily_scraping; asyncio.run(run_daily_scraping())"
```

### 10. Surveiller
- Logs Railway : tout est loggé avec timestamps
- Supabase → Table Editor : voir les données en temps réel
- Resend → Logs : historique de tous les emails envoyés

## Stack technique
- **Backend** : Python 3.11 + FastAPI
- **Scraping** : httpx + BeautifulSoup + Playwright
- **IA** : Claude API (claude-sonnet-4-20250514)
- **BDD** : Supabase (PostgreSQL)
- **Emails** : Resend
- **Paiements** : PayPal Subscriptions API (via httpx)
- **Scheduler** : APScheduler
- **Déploiement** : Railway

## Coûts mensuels estimés (10 clients)
| Service | Coût |
|---------|------|
| Railway | ~5$/mois |
| Supabase | Gratuit (free tier) |
| Resend | Gratuit jusqu'à 3000 emails/mois |
| Claude API | ~10-20$/mois (selon volume) |
| PayPal | 3.49% + frais fixe par transaction |
| **Total** | **~20-30$/mois** |

Rentable dès le 1er client à 99$/mois.
