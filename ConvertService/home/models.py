from django.db import models
from configs.models import ConvertRule

class Tenant(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(unique=True, max_length=50, verbose_name="テナントID")
    tenant_name = models.CharField(max_length=255, verbose_name="テナント名")
    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        db_table = "tenant"
        verbose_name = "テナント名"
        verbose_name_plural = "テナント名"

    def __str__(self):
        return self.tenant_name


class FileFormat(models.Model):
    id = models.AutoField(primary_key=True)
    file_format_id = models.CharField(unique=True, max_length=50)
    file_format_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "file_format"

    def __str__(self):
        return self.file_format_name


class DataFormat(models.Model):
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_format_id = models.CharField(unique=True, max_length=50)
    data_format_name = models.CharField(max_length=255)
    file_format = models.ForeignKey(FileFormat, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_format"

    def __str__(self):
        return self.data_format_name


class DataItem(models.Model):
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_format = models.ForeignKey(DataFormat, on_delete=models.CASCADE)
    data_item_id = models.CharField(unique=True, max_length=50)
    data_item_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_item"

    def __str__(self):
        return self.data_item_name


class DataConversionInfo(models.Model):
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_convert_id = models.CharField(unique=True, max_length=50)
    data_convert_name = models.CharField(max_length=255)
    data_format_before = models.ForeignKey(DataFormat, related_name="before_conversion", on_delete=models.CASCADE)
    data_format_after = models.ForeignKey(DataFormat, related_name="after_conversion", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_conversion_info"

    def __str__(self):
        return self.data_convert_name


class DetailedInfo(models.Model):
    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_convert = models.ForeignKey(DataConversionInfo, on_delete=models.CASCADE)
    data_item_id_before = models.ForeignKey(DataItem, related_name='before', on_delete=models.CASCADE)
    data_item_id_after = models.ForeignKey(DataItem, related_name='after', on_delete=models.CASCADE)
    convert_rule = models.ForeignKey(ConvertRule, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "detailed_info"

    def __str__(self):
        return f"Detail for {self.data_convert}"


class DataItemType(models.Model):

    class TypeName(models.TextChoices):
        BEFORE = 'input', '変換前の列'
        FORMAT = 'format', '変換中の列'
        AFTER = 'output', '変換後の列'

    class FormatValue(models.TextChoices):
        STRING = 'string', '文字列'
        NUMBER = 'number', '数値'
        DATE = 'date', '日付'
        TIME = 'time', '時間'
        DATETIME = 'datetime', '日時'
        BOOLEAN = 'boolean', '真偽値'
        PERIOD = 'period', '時間帯'

    id = models.AutoField(primary_key=True)
    data_item = models.ForeignKey('DataItem', on_delete=models.CASCADE)
    type_name = models.CharField(max_length=50, choices=TypeName.choices)
    index_value = models.IntegerField(null=True, blank=True)
    display = models.BooleanField(default=True)
    edit_value = models.BooleanField(default=False)
    format_value = models.CharField(max_length=50, choices=FormatValue.choices, default=FormatValue.STRING)


    class Meta:
        db_table = "data_item_type"

    def check_constraints(self):
        existing_types = DataItemType.objects.filter(data_item=self.data_item).values_list('type_name', flat=True)

        if self.type_name in existing_types:
            return f"種類 '{self.type_name}' は既にこのデータアイテムに存在します。"
        if len(existing_types) >= 3:
            return "データアイテムは最大3種類のみ登録できます。"
        return None

    def save(self, *args, **kwargs):
        message = self.check_constraints()
        if message:
            return message
        super().save(*args, **kwargs)

    @staticmethod
    def get_all_type_names():
        return [{"value": choice[0], "display": choice[1]} for choice in DataItemType.TypeName.choices]

    @staticmethod
    def get_all_format_values():
        return [{"value": choice[0], "display": choice[1]} for choice in DataItemType.FormatValue.choices]

