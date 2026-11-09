-- Seguridad: RLS activado en todas las tablas.
-- La llave anónima solo lee las tablas publicadas; no hay políticas de escritura.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
end
$$;

alter table styles enable row level security;
alter table academies enable row level security;
alter table academy_locations enable row level security;
alter table academy_links enable row level security;
alter table academy_styles enable row level security;
alter table candidates enable row level security;
alter table proposals enable row level security;
alter table field_rejections enable row level security;

create policy "lectura pública de estilos"
  on styles for select to anon using (true);

create policy "lectura pública de academias"
  on academies for select to anon using (true);

create policy "lectura pública de sedes"
  on academy_locations for select to anon using (true);

create policy "lectura pública de enlaces"
  on academy_links for select to anon using (true);

create policy "lectura pública de estilos por academia"
  on academy_styles for select to anon using (true);
