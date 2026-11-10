SELECT
    Store,
    COUNT(*) AS total_registros,
    COUNT(*) FILTER (WHERE CPI = 'NA') AS cpi_na,
    COUNT(*) FILTER (WHERE Unemployment = 'NA') AS unemployment_na
FROM bruto.features
WHERE CPI = 'NA' OR Unemployment = 'NA'
GROUP BY Store
ORDER BY Store;