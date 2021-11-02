\timing

-- Find packages/pallets of products in multiple locations
SELECT
    p.package_id,
    COUNT(location_id)
FROM (
    SELECT
        package_id,
        location_id
    FROM
        stock_quant
    WHERE
        package_id IS NOT NULL
    GROUP BY
        package_id,
        location_id
) AS p
GROUP BY
    p.package_id
HAVING
    COUNT(location_id) > 1
;

-- Find pallets of packages in mutliple locations
SELECT
    p.pallet_id,
    COUNT(location_id)
FROM (
    SELECT
        pallet.id AS pallet_id,
        q.location_id
    FROM stock_quant q
    INNER JOIN
        stock_quant_package pack ON pack.id = q.package_id
    INNER JOIN
        stock_quant_package pallet ON pallet.id = pack.package_id
    GROUP BY
        pallet.id,
        q.location_id
) AS p
GROUP BY
    p.pallet_id
HAVING
    COUNT(location_id) > 1
;
