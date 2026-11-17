select
    p.product_id,
    p.product_category_name                          as category_name_pt,
    t.product_category_name_english                  as category_name,
    p.product_name_lenght                            as name_length,
    p.product_description_lenght                     as description_length,
    p.product_photos_qty                             as photos_qty,
    p.product_weight_g                               as weight_g,
    p.product_length_cm                              as length_cm,
    p.product_height_cm                              as height_cm,
    p.product_width_cm                               as width_cm
from {{ source('raw', 'products') }} as p
left join {{ source('raw', 'product_category_name_translation') }} as t
    on p.product_category_name = t.product_category_name