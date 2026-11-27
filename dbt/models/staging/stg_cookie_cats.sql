-- One row per player in the Cookie Cats experiment.
-- version: gate_30 = control (original), gate_40 = treatment (gate moved to level 40).
select
    userid                                   as player_id,
    version                                  as variant,
    sum_gamerounds                           as game_rounds_14d,
    cast(retention_1 as boolean)             as retained_day1,
    cast(retention_7 as boolean)             as retained_day7
from {{ source('raw', 'cookie_cats') }}