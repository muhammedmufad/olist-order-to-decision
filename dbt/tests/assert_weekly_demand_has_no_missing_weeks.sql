-- Fails (returns a row) if any week is missing between the first and last week.
select
    count(distinct week_start)                                     as weeks_present,
    date_diff('week', min(week_start), max(week_start)) + 1        as weeks_expected
from {{ ref('mart_weekly_category_demand') }}
having count(distinct week_start)
    != date_diff('week', min(week_start), max(week_start)) + 1