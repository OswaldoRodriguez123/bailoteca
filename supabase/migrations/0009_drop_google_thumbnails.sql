update academies
set google = google - 'thumbnail' - 'thumbnail_source' - 'thumbnail_fetched_at'
where google is not null;
