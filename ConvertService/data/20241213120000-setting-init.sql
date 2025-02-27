-- Insert data into convert_rule_category
INSERT INTO convert_rule_category (convert_rule_category_id, convert_rule_category_name, created_at, updated_at)
VALUES
('CRC_NON', 'カテゴリなし', NOW(), NOW()),
('CRC_DATE', '日付変更', NOW(), NOW()),
('CRC_GENDER', '性別変更', NOW(), NOW()),
('CRC_KANA', 'カナ変更', NOW(), NOW()),
('CRC_FIXED', '固定ルール', NOW(), NOW()),
('CRC_OPTION', '固定ルール', NOW(), NOW()),
('CRC_POSTAL', '郵便番号変更', NOW(), NOW()),
('CRC_TIME', '時刻を文字列に変換する', NOW(), NOW());

-- Insert data into convert_rule
INSERT INTO convert_rule (convert_rule_id, convert_rule_name, convert_rule_category_id, created_at, updated_at)
VALUES
('CR_NOT_CHANGE', '変換なし', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_NON'), NOW(), NOW()),
('CR_DATE1', '日付変更（-yyyy/MM/dd）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_DATE'), NOW(), NOW()),
('CR_DATE2', '日付変更（-yyyy-MM-dd）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_DATE'), NOW(), NOW()),
('CR_G_12', '性別変更（男=1、女=2）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_GENDER'), NOW(), NOW()),
('CR_G_MF', '性別変更（男=M、女=F）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_GENDER'), NOW(), NOW()),
('CR_KANA_F-H', 'カナ変更（全角カナ→半角ｶﾅ）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_KANA'), NOW(), NOW()),
('CR_KANA_H-F', 'カナ変更（半角ｶﾅ→全角カナ）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_KANA'), NOW(), NOW()),
('CR_GROUP_NO', 'ふくおか公衆衛生用変換（顧客名→団体番号１）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW()),
('CR_POSTAL_FORMAT', '郵便番号形式変更（XXX-XXXX）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_POSTAL'), NOW(), NOW()),
('CR_TIME_CODE1', 'ふくおか公衆衛生用変換（予約時間→（必須）時間帯コード）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW()),
('CR_CAUSE_CODE1', 'ふくおか公衆衛生用変換（顧客コース名→予約コース１）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW()),
('CR_TIME_START', 'ふくおか公衆衛生用変換（予約時間→受付時間開始）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW()),
('CR_TIME_END', 'ふくおか公衆衛生用変換（予約時間→受付時間終了）', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW()),
('CR_TIME','時刻を文字列に変換する', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_TIME'), NOW(), NOW()),
('CR_FIXED_VALUE', '固定データ用の規則', (SELECT id FROM convert_rule_category WHERE convert_rule_category_id = 'CRC_FIXED'), NOW(), NOW());

