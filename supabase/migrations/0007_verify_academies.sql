-- Marcar como verificadas las academias que aún no tienen fecha de verificación.
-- `verified_at` es la fuente de verdad de la verificación; `status` sigue siendo
-- el estado operativo (active/closed/unknown) y no se toca aquí.

update academies
set verified_at = now()
where verified_at is null;
