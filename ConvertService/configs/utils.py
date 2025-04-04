import csv
import os
from functools import lru_cache
from django.conf import settings

def remove_bom(header_name):
    try:
        header = header_name.lstrip('\ufeff')
        header = header.replace("\ufeff", "")
    except Exception as e:
        return header_name
    return header


@lru_cache(maxsize=None)
def get_edit_options():
    """
    Read options from the edit_option.csv file and return them as a list of tuples.
    The cache ensures we don't read the file repeatedly.
    """
    list_value = []
    try:
        file_path = os.path.join(settings.STATIC_ROOT, 'web', 'edit_option.csv')
        if os.path.exists(file_path):
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    list_value.append((row['label'], row['value']))
        else:
            list_value = [
                ('150', '150：直接管理'),
                ('151', '151：人間ドック'),
                ('152', '152：協会けんぽ'),
                ('153', '153：東振協'),
                ('154', '154：急ぎ'),
                ('155', '155：巡回もれ'),
                ('156', '156：ストレスチェック'),
                ('157', '157：その他')
            ]
    except Exception as e:
        list_value = [
            ('150', '150：直接管理'),
            ('151', '151：人間ドック'),
            ('152', '152：協会けんぽ'),
            ('153', '153：東振協'),
            ('154', '154：急ぎ'),
            ('155', '155：巡回もれ'),
            ('156', '156：ストレスチェック'),
            ('157', '157：その他')
        ]
    return list_value
