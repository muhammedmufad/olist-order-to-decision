-- One coordinate per zip-code prefix.
-- The raw table has many rows per prefix and some points outside Brazil, so we filter and average.
select
    geolocation_zip_code_prefix       as zip_code_prefix,
    avg(geolocation_lat)              as lat,
    avg(geolocation_lng)              as lng
from {{ source('raw', 'geolocation') }}
where geolocation_lat between -34 and 6
  and geolocation_lng between -74 and -34
group by 1