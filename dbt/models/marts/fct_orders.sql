with items as (
    select
        i.order_id,
        count(*)                              as item_count,
        count(distinct i.seller_id)           as seller_count,
        sum(i.price)                          as items_value,
        sum(i.freight_value)                  as freight_value,
        arg_max(p.category_name, i.price)     as main_category,
        arg_max(i.seller_id, i.price)         as main_seller_id,
        arg_max(p.weight_g, i.price)          as main_item_weight_g
    from {{ ref('stg_order_items') }} as i
    left join {{ ref('stg_products') }} as p
        on i.product_id = p.product_id
    group by i.order_id
)

select
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    c.customer_zip_code_prefix,
    o.order_status,
    o.purchased_at,
    o.delivered_at,
    o.estimated_delivery_at,
    i.item_count,
    i.seller_count,
    i.items_value,
    i.freight_value,
    i.main_category,
    i.main_seller_id,
    i.main_item_weight_g,
    date_diff('day', o.purchased_at, o.delivered_at)           as delivery_days,
    date_diff('day', o.purchased_at, o.estimated_delivery_at)  as promised_days,
    case
        when o.order_status = 'delivered' and o.delivered_at is not null
            then o.delivered_at > o.estimated_delivery_at
    end                                                        as is_late
from {{ ref('stg_orders') }} as o
left join {{ ref('stg_customers') }} as c
    on o.customer_id = c.customer_id
left join items as i
    on o.order_id = i.order_id