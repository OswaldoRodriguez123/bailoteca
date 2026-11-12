alter table academies
    add column if not exists social_followers integer,
    add column if not exists social_network text;
