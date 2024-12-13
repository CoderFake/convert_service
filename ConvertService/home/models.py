from django.db import models
from configs.models import ConvertRule

class Tenant(models.Model):
    id = models.AutoField(primary_key=True)
    tenant_id = models.CharField(unique=True, max_length=50)
    tenant_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant"

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
    data_item_index = models.IntegerField(null=True, blank=True, help_text="Index of the data item")
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