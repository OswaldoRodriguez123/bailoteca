-- Registro de origen de los pins de sede (auditoría para revisión posterior).
-- Vocabulario: 'google' (gps_coordinates de la academia), 'nominatim' (OpenStreetMap),
-- 'google_embed' (endpoint no oficial maps?output=embed), 'manual' (puesto a mano).
alter table academy_locations add column if not exists coords_source text;

-- Backfill: todos los pins existentes fueron puestos a mano (2026-11) antes de este
-- registro; 'manual' es el bucket honesto.
update academy_locations set coords_source = 'manual' where lat is not null and coords_source is null;

create index if not exists academy_locations_coords_source_idx on academy_locations (coords_source);
