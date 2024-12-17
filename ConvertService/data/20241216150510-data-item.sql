INSERT INTO data_item (tenant_id, data_format_id, data_item_id, data_item_name, data_item_index, created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_001', '代行業者名', 0, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_002', '性別', 1, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_003', '受診コース名', 2, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_004', '郵便番号', 3, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_005', '予約希望日', 4, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_006', '受診者カナ', 5, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_007', 'コースコード', 6, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'), 'D3_008', '生年月日', 7, NOW(), NOW()),


       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_001', '代行業者名', 2, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_002', '性別', 3, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_003', '受診コース名', 5, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_004', '郵便番号', 1, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_005', '予約希望日', 4, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_006', '受診者カナ', 6, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_007', 'コースコード', 7, NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_001'), 'D1_008', '生年月日', 0, NOW(), NOW());

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
        (SELECT id FROM data_item WHERE data_item_id = 'D3_003'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_003'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_NOT_CHANGE'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_004'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_004'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_POSTAL_FORMAT'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_005'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_005'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_DATE1'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_006'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_006'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_KANA_F-H'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_007'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_007'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_NOT_CHANGE'), NOW(), NOW()),

       ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        (SELECT id FROM data_conversion_info WHERE data_convert_id = 'C_001'),
        (SELECT id FROM data_item WHERE data_item_id = 'D3_008'),
        (SELECT id FROM data_item WHERE data_item_id = 'D1_008'),
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_DATE1'), NOW(), NOW());
