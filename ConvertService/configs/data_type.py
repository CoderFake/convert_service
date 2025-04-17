import enum


class Mess(enum.Enum):
    CREATE = '追加に成功しました。'
    UPDATE = '更新に成功しました。'
    DELETE = '削除に成功しました。'
    ERROR = 'エラーが発生しました。'
    NOTFOUND = 'データが見つかりません。'