\timing

-- Find packages/pallets of products in multiple locations
\echo ''
\echo 'Finding packages in multiple locations:'
SELECT
    p.package_id,
    p.package_name,
    COUNT(location_id) AS location_count,
    string_agg(CAST(location_id AS VARCHAR(10)), ', ') AS location_ids,
    string_agg(CAST(location_name AS VARCHAR(100)), ', ') AS location_names
FROM (
    SELECT
        q.package_id,
        q.location_id,
        loc.name AS location_name,
        pack.name AS package_name
    FROM
        stock_quant q
    INNER JOIN 
    	stock_quant_package pack ON pack.id = q.package_id 
    INNER JOIN 
    	stock_location loc ON loc.id = q.location_id
    WHERE
        q.package_id IS NOT NULL
    GROUP BY
        q.package_id,
        q.location_id,
        pack.name,
        loc.name
) AS p
GROUP BY
    p.package_id,
    p.package_name
HAVING
    COUNT(location_id) > 1
;

-- Find pallets of packages in mutliple locations
\echo ''
\echo 'Finding pallets in multiple locations:'
SELECT
    p.pallet_id,
    p.pallet_name,
    COUNT(location_id) AS location_count,
    string_agg(CAST(location_id AS VARCHAR(10)), ', ') AS location_ids,
    string_agg(CAST(location_name AS VARCHAR(100)), ', ') AS location_names
FROM (
    SELECT
        pallet.id AS pallet_id,
        pallet.name AS pallet_name,
        q.location_id,
        loc.name AS location_name
    FROM stock_quant q
    INNER JOIN
        stock_quant_package pack ON pack.id = q.package_id
    INNER JOIN
        stock_quant_package pallet ON pallet.id = pack.package_id
    INNER JOIN
    	stock_location loc ON loc.id = q.location_id
    GROUP BY
        pallet.id,
        pallet.name,
        q.location_id,
        loc.name
) AS p
GROUP BY
    p.pallet_id,
    p.pallet_name
HAVING
    COUNT(location_id) > 1
;
