INSERT INTO convert_data_value (tenant_id, data_value_before, data_value_after, convert_rule_id)
VALUES ((SELECT id FROM tenant WHERE tenant_id = 'T_001'),
        '【B.変更】　　　健康診断　予約のお願い', '予約　さんぷる１',
        (SELECT id FROM convert_rule WHERE convert_rule_id = 'CR_FIXED_VALUE'));
