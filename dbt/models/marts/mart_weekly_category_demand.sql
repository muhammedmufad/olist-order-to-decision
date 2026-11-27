{% set first_week = '2017-01-02' %}  {# data is sparse before 2017; November 2016 has no orders at all #}
{% set end_week = '2018-08-20' %}    {# exclusive: the week starting 2018-08-20 is cut off mid-week #}

-- Weekly units ordered per product category: the input for demand forecasting.
-- Demand is counted at purchase time; canceled and unavailable orders are excluded.
-- Every week in the range appears for every category; weeks without sales are 0.

with items as (
    select
        date_trunc('week', o.purchased_at)        as week_start,
        coalesce(p.category_name, 'unknown')      as category,
        i.order_id
    from {{ ref('stg_order_items') }} as i
    join {{ ref('stg_orders') }} as o
        on i.order_id = o.order_id
    left join {{ ref('stg_products') }} as p
        on i.product_id = p.product_id
    where o.order_status not in ('canceled', 'unavailable')
),

weeks as (
    -- one row for EVERY week in the range, generated as a calendar, not taken from the data
    select range as week_start
    from range(timestamp '{{ first_week }}', timestamp '{{ end_week }}', interval 7 day)
),

categories as (
    select distinct category from items
),

counts as (
    select
        week_start,
        category,
        count(*)                   as units,
        count(distinct order_id)   as orders
    from items
    group by 1, 2
)

select
    strftime(w.week_start, '%Y-%m-%d') || '|' || c.category   as demand_key,
    w.week_start,
    c.category,
    coalesce(n.units, 0)                                       as units,
    coalesce(n.orders, 0)                                      as orders
from weeks as w
cross join categories as c
left join counts as n
    on  n.week_start = w.week_start
    and n.category   = c.category