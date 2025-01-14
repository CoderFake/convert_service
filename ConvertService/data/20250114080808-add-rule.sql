-- Insert data into convert_rule_category
INSERT INTO convert_rule_category (convert_rule_category_id, convert_rule_category_name, created_at, updated_at)
VALUES
('CRC_TIME', '時刻を文字列に変換する', NOW(), NOW());

-- Insert data into convert_rule
INSERT INTO convert_rule (convert_rule_id, convert_rule_name, convert_rule_category_id, created_at, updated_at)
VALUES
('CR_TIME','時刻を文字列に変換する', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_TIME'), NOW(), NOW());