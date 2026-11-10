-- Datos enriquecidos de Google Maps por academia (rating, reseñas, precio, horarios).
-- Se obtienen vía SerpApi (engine=google_maps), atribuidos y con fecha de captura.

alter table academies
  add column if not exists google_place_id text,
  add column if not exists google_name text,
  add column if not exists google_address text,
  add column if not exists google_rating numeric(3,2),
  add column if not exists google_reviews integer,
  add column if not exists google_price text,
  add column if not exists google_hours jsonb,
  add column if not exists google_open_state text,
  add column if not exists google_maps_url text,
  add column if not exists google_fetched_at timestamptz;
