alter table academy_locations add column if not exists region text;
create index if not exists academy_locations_region_idx on academy_locations (region);
