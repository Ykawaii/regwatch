-- RegWatch — Schéma Supabase
-- Exécute ce fichier dans l'éditeur SQL de Supabase

create table if not exists clients (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  nom text,
  secteurs text[] default '{}',
  plan text default 'starter',
  lemonsqueezy_subscription_id text,
  actif boolean default true,
  created_at timestamptz default now()
);

create table if not exists textes_reglementaires (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  titre text not null,
  url text unique not null,
  date_publication date,
  contenu_brut text,
  resume_ia text,
  score_pertinence_global integer default 0,
  secteurs_concernes text[] default '{}',
  created_at timestamptz default now()
);

create table if not exists alertes (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) on delete cascade,
  texte_id uuid references textes_reglementaires(id) on delete cascade,
  score integer,
  envoyee boolean default false,
  date_envoi timestamptz,
  created_at timestamptz default now()
);

create table if not exists rapports_hebdo (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) on delete cascade,
  semaine_debut date,
  contenu_html text,
  pdf_url text,
  envoyee boolean default false,
  created_at timestamptz default now()
);

create table if not exists scraping_log (
  id uuid primary key default gen_random_uuid(),
  source text,
  derniere_execution timestamptz,
  nb_textes_trouves integer default 0,
  erreur text,
  created_at timestamptz default now()
);

create table if not exists prospects (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  nom text,
  telephone text,
  ville text,
  secteur text,
  site text,
  source text default 'pages_jaunes',
  statut text default 'nouveau',   -- nouveau | email_envoye | relance_envoyee | demo_vue | converti | desabonne
  ref text,
  date_premier_email timestamptz,
  date_relance timestamptz,
  resend_email_id text,
  created_at timestamptz default now()
);

-- Index utiles
create index if not exists idx_textes_date on textes_reglementaires(date_publication desc);
create index if not exists idx_alertes_client on alertes(client_id);
create index if not exists idx_alertes_non_envoyees on alertes(envoyee) where envoyee = false;
