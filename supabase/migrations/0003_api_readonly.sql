-- Usuario de solo lectura para la API.
-- La contraseña se define a mano en el SQL Editor; nunca va en la migración.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'bailoteca_api') then
    create role bailoteca_api login;
  end if;
end
$$;

alter role bailoteca_api login;

grant usage on schema public to bailoteca_api;
grant select on styles, academies, academy_locations, academy_links, academy_styles
  to bailoteca_api;

drop policy if exists "lectura api de estilos" on styles;
create policy "lectura api de estilos"
  on styles for select to bailoteca_api using (true);

drop policy if exists "lectura api de academias" on academies;
create policy "lectura api de academias"
  on academies for select to bailoteca_api using (true);

drop policy if exists "lectura api de sedes" on academy_locations;
create policy "lectura api de sedes"
  on academy_locations for select to bailoteca_api using (true);

drop policy if exists "lectura api de enlaces" on academy_links;
create policy "lectura api de enlaces"
  on academy_links for select to bailoteca_api using (true);

drop policy if exists "lectura api de estilos por academia" on academy_styles;
create policy "lectura api de estilos por academia"
  on academy_styles for select to bailoteca_api using (true);
