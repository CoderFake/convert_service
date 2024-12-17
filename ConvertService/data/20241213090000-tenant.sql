INSERT INTO tenant (tenant_id, tenant_name, created_at, updated_at)
VALUES ('T_001', 'サービス利用健診施設A', NOW(), NOW()),
       ('T_002', 'サービス利用健診施設B', NOW(), NOW()),
       ('T_003', 'サービス利用健診施設C', NOW(), NOW());


INSERT INTO data_item (tenant_id, data_format_id, data_item_id, data_item_name, data_item_index, created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_001', '健診システム取込データ項目００１', 0,
        NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_002', '健診システム取込データ項目００２', 1,
        NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_001', '変換前データ項目００１', 0, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_002', '変換前データ項目００２', 1, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_006', '変換前データ項目００６', 5, NOW(), NOW());


INSERT INTO data_conversion_info (tenant_id, data_convert_id, data_convert_name, data_format_before_id,
                                  data_format_after_id, created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        'C_001', '予約代行業者B用データ変換',
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'),
        NOW(), NOW());


INSERT INTO detailed_info (tenant_id, data_convert_id, data_item_id_before_id, data_item_id_after_id, convert_rule_id,
                           created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_001'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_NOT_CHANGE'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_002'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_002'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_G_12'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_006'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_001'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_KANA_F-H'), NOW(), NOW());
