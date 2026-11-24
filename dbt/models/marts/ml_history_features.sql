-- History features, computed "as of" the purchase moment.
-- Rule: only orders already DELIVERED before this order was PURCHASED may count.

with history as (
    -- every delivered order: who sold it, when it arrived, was it late
    select
        main_seller_id     as seller_id,
        delivered_at,
        is_late
    from {{ ref('fct_orders') }}
    where is_late is not null
),

orders as (
    select order_id, main_seller_id, purchased_at
    from {{ ref('fct_orders') }}
    where is_late is not null
),

-- 1. Seller reliability: this seller's earlier, already-delivered orders
seller_history as (
    select
        o.order_id,
        count(h.delivered_at)            as seller_past_orders,
        avg(h.is_late::integer)          as seller_past_late_rate
    from orders as o
    left join history as h
        on  h.seller_id = o.main_seller_id
        and h.delivered_at < o.purchased_at
    group by o.order_id
),

-- 2. Recent conditions: all orders delivered in the 14 days before the purchase day
daily as (
    select
        cast(delivered_at as date)       as day,
        count(*)                         as delivered,
        sum(is_late::integer)            as late
    from history
    group by 1
),

purchase_days as (
    select distinct cast(purchased_at as date) as day
    from orders
),

recent_by_day as (
    select
        p.day,
        coalesce(sum(d.delivered), 0)                    as recent_delivered_14d,
        sum(d.late) * 1.0 / nullif(sum(d.delivered), 0)  as recent_late_rate_14d
    from purchase_days as p
    left join daily as d
        on  d.day <  p.day
        and d.day >= p.day - interval 14 day
    group by p.day
)

select
    o.order_id,
    s.seller_past_orders,
    s.seller_past_late_rate,
    r.recent_delivered_14d,
    r.recent_late_rate_14d
from orders as o
left join seller_history as s
    on o.order_id = s.order_id
left join recent_by_day as r
    on cast(o.purchased_at as date) = r.day