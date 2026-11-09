-- Directorio de baile — esquema v1
-- Ocho tablas: taxonomía, publicadas, borradores y rechazos.

create table styles (
  id smallint generated always as identity primary key,
  slug text unique not null,
  name text not null,
  discipline text not null default 'salsa',
  sort int not null default 0
);

create table academies (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  description text,
  status text not null default 'unknown'
    check (status in ('active', 'closed', 'unknown')),
  source_urls text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  verified_at timestamptz
);

create table academy_locations (
  id uuid primary key default gen_random_uuid(),
  academy_id uuid not null references academies(id) on delete cascade,
  label text,
  address text,
  comuna text,
  lat double precision,
  lng double precision,
  source_url text
);

create table academy_links (
  id uuid primary key default gen_random_uuid(),
  academy_id uuid not null references academies(id) on delete cascade,
  kind text not null
    check (kind in ('web', 'instagram', 'facebook', 'tiktok', 'whatsapp', 'phone', 'email')),
  url text not null,
  unique (academy_id, kind, url)
);

create table academy_styles (
  academy_id uuid not null references academies(id) on delete cascade,
  style_id smallint not null references styles(id),
  confidence numeric(3,2),
  evidence text,
  primary key (academy_id, style_id)
);

create table candidates (
  id uuid primary key default gen_random_uuid(),
  key text unique not null,
  name text not null,
  url text,
  handle text,
  source text not null,
  comuna text,
  raw jsonb not null default '{}',
  status text not null default 'new'
    check (status in ('new', 'proposed', 'rejected', 'published')),
  discovered_at timestamptz not null default now()
);

create table proposals (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid references candidates(id) on delete cascade,
  academy_id uuid references academies(id),
  kind text not null check (kind in ('create', 'update')),
  dedupe_key text unique not null,
  payload jsonb not null,
  evidence jsonb not null default '{}',
  confidence numeric(3,2),
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create table field_rejections (
  academy_id uuid not null references academies(id) on delete cascade,
  field text not null,
  value_hash text not null,
  rejected_at timestamptz not null default now(),
  primary key (academy_id, field, value_hash)
);

create index academies_slug_idx on academies (slug);
create index academy_locations_comuna_idx on academy_locations (comuna);
create index academy_styles_style_idx on academy_styles (style_id);
create index candidates_status_idx on candidates (status);
create index proposals_status_idx on proposals (status);

insert into styles (slug, name, discipline, sort) values
  ('salsa-cubana', 'Salsa cubana', 'salsa', 10),
  ('salsa-linea', 'Salsa en línea', 'salsa', 20),
  ('mambo', 'Mambo', 'salsa', 30)
on conflict (slug) do nothing;
