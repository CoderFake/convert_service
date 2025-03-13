INSERT INTO file_format (file_format_id, file_format_name, created_at, updated_at)
VALUES ('CSV_C_SJIS', 'CSVファイル（カンマ区切り）SJIS', NOW(), NOW()),
       ('CSV_C_UTF-8', 'CSVファイル（カンマ区切り）UTF-8', NOW(), NOW()),
       ('CSV_T_SJIS', 'CSVファイル（タブ区切り）SJIS', NOW(), NOW()),
       ('CSV_T_UTF-8', 'CSVファイル（タブ区切り）UTF-8', NOW(), NOW()),
       ('XML', 'XMLファイル', NOW(), NOW()),
       ('JSON', 'JSONファイル', NOW(), NOW()),
       ('EXCEL', 'EXCELファイル', NOW(), NOW());


INSERT INTO data_format (tenant_id, data_format_id, data_format_name, file_format_id, created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'), 'DF_001', '健診システム取込用データ',
        (SELECT id FROM file_format WHERE file_format_id = 'CSV_C_SJIS'), NOW(), NOW()),
       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'), 'DF_002', '予約代行業者Aの予約データ',
        (SELECT id FROM file_format WHERE file_format_id = 'JSON'), NOW(), NOW()),
       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'), 'DF_003', '予約代行業者Bの予約データ',
        (SELECT id FROM file_format WHERE file_format_id = 'CSV_C_UTF-8'), NOW(), NOW()),
       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'), 'DF_004', '予約代行業者Cの予約データ',
        (SELECT id FROM file_format WHERE file_format_id = 'EXCEL'), NOW(), NOW());