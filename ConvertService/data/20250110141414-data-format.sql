INSERT INTO data_conversion_info (tenant_id, data_convert_id, data_convert_name, data_format_before_id,
                                  data_format_system_after, data_format_agency_after, created_at, updated_at)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        'C_001', '予約代行業者B用データ変換',
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'),
        (SELECT id FROM data_format WHERE data_format_id = 'DF_003'),
        NOW(), NOW());
