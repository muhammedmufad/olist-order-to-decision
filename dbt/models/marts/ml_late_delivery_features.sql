-- Features for the late-delivery model.
-- Rule: only information available at the moment of purchase.

with geo as (
    select * from {{ ref('stg_geolocation') }}
)

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
    -- straight-line distance between seller and customer (haversine formula)
    2 * 6371 * asin(sqrt(
        power(sin(radians(sg.lat - cg.lat) / 2), 2)
        + cos(radians(cg.lat)) * cos(radians(sg.lat))
          * power(sin(radians(sg.lng - cg.lng) / 2), 2)
    ))                                                as distance_km,
    f.is_late                                         -- the target
from {{ ref('fct_orders') }} as f
left join {{ ref('stg_sellers') }} as s
    on f.main_seller_id = s.seller_id
left join geo as cg
    on f.customer_zip_code_prefix = cg.zip_code_prefix
left join geo as sg
    on s.seller_zip_code_prefix = sg.zip_code_prefix
where f.is_late is not null