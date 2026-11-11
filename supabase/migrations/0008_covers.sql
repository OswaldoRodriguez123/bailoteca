alter table academies
  add column if not exists cover_url text,
  add column if not exists cover_source text,
  add column if not exists cover_fetched_at timestamptz;

insert into storage.buckets (id, name, public)
values ('academy-covers', 'academy-covers', true)
on conflict (id) do nothing;
