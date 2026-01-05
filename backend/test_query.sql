-- Test 1: Check if invoice exists with date
SELECT 
    i.id,
    i.invoice_date->>'value' as date_string,
    TO_DATE(i.invoice_date->>'value', 'MM/DD/YYYY') as parsed_date
FROM icap_invoice i
WHERE i.invoice_date->>'value' = '02/03/2025'
LIMIT 5;

-- Test 2: Check invoice_detail with product mapping
SELECT 
    ivd.id,
    ivd.product_id->>'value' as product_id_str,
    pm.name as product_name,
    pm.id as product_uuid
FROM icap_invoice_detail ivd
LEFT JOIN icap_invoice i ON ivd.document_id = i.document_id
LEFT JOIN icap_product_master pm ON (ivd.product_id->>'value') != '' AND (ivd.product_id->>'value')::uuid = pm.id
WHERE i.invoice_date->>'value' = '02/03/2025'
LIMIT 5;

-- Test 3: Check product-category mapping
SELECT 
    pm.name as product_name,
    pcm.product_id,
    pcm.gl_category_id,
    tcm.name as category_name
FROM icap_product_master pm
LEFT JOIN icap_product_category_mapping pcm ON pm.id = pcm.product_id
LEFT JOIN icap_tenant_category_master tcm ON pcm.gl_category_id = tcm.id
WHERE pcm.product_id IS NOT NULL
LIMIT 5;
