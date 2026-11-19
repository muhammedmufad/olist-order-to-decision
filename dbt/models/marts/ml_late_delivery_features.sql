-- Features for the late-delivery model.
-- Rule: only information available at the moment of purchase.

select
    f.order_id,
    f.purchased_at,                                   -- for the time-based split, not a feature
    extract(month from f.purchased_at)                as purchase_month,
    extract(dow from f.purchased_at)                  as purchase_dow,
    extract(hour from f.purchased_at)                 as purchase_hour,
    f.promised_days,
    f.item_count,
    f.seller_count,
    f.items_value,
    f.freight_value,
    f.freight_value / nullif(f.items_value, 0)        as freight_ratio,
    f.main_item_weight_g,
    coalesce(f.main_category, 'unknown')              as main_category,
    f.customer_state,
    s.seller_state,
    f.customer_state = s.seller_state                 as same_state,
    f.is_late                                         -- the target
from {{ ref('fct_orders') }} as f
left join {{ ref('stg_sellers') }} as s
    on f.main_seller_id = s.seller_id
where f.is_late is not null