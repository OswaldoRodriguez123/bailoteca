-- Consolidar los datos de Google Maps en una única columna JSONB.
-- Migra los valores de las columnas individuales (si existen) y las elimina.

alter table academies
  add column if not exists google jsonb;

update academies
set google = jsonb_strip_nulls(
  jsonb_build_object(
    'place_id', google_place_id,
    'name', google_name,
    'address', google_address,
    'rating', google_rating,
    'reviews', google_reviews,
    'price', google_price,
    'hours', google_hours,
    'open_state', google_open_state,
    'maps_url', google_maps_url,
    'fetched_at', google_fetched_at
  )
)
where google is null
  and (
    google_place_id is not null or google_name is not null or
    google_address is not null or google_rating is not null or
    google_reviews is not null or google_price is not null or
    google_hours is not null or google_open_state is not null or
    google_maps_url is not null or google_fetched_at is not null
  );

alter table academies
  drop column if exists google_place_id,
  drop column if exists google_name,
  drop column if exists google_address,
  drop column if exists google_rating,
  drop column if exists google_reviews,
  drop column if exists google_price,
  drop column if exists google_hours,
  drop column if exists google_open_state,
  drop column if exists google_maps_url,
  drop column if exists google_fetched_at;