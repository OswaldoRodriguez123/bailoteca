-- Agrega bachata a la taxonomía de estilos.
-- Idempotente: se puede reaplicar desde el SQL Editor sin error.

insert into styles (slug, name, discipline, sort) values
  ('bachata', 'Bachata', 'bachata', 40)
on conflict (slug) do nothing;
