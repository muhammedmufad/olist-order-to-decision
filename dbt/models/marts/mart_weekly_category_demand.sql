-- Weekly units ordered per product category: the input for demand forecasting.
-- Demand is counted at purchase time; canceled and unavailable orders are excluded.
-- Weeks with no sales appear as 0 (zero-filled), so the forecast sees real gaps.

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

weekly_totals as (
    select week_start, count(*) as units
    from items
    group by 1
),

valid_range as (
    -- the span of weeks with meaningful volume; trims the sparse start and end
    select min(week_start) as first_week, max(week_start) as last_week
    from weekly_totals
    where units >= 200
),

weeks as (
    select w.week_start
    from weekly_totals as w
    cross join valid_range as r
    where w.week_start between r.first_week and r.last_week
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