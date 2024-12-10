from django.db import models
from configs.models import ConvertRule

class Tenant(models.Model):
    tenant_id = models.AutoField(primary_key=True)
    tenant_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FileFormat(models.Model):
    file_format_id = models.AutoField(primary_key=True)


class DataFormat(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_format_id = models.AutoField(primary_key=True)
    file_format = models.ForeignKey(FileFormat, on_delete=models.CASCADE)


class DataItem(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_format = models.ForeignKey(DataFormat, on_delete=models.CASCADE)
    data_item_id = models.AutoField(primary_key=True)


class DetailedInfo(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_convert_id = models.IntegerField()
    data_item_id_before = models.ForeignKey(DataItem, related_name='before', on_delete=models.CASCADE)
    data_item_id_after = models.ForeignKey(DataItem, related_name='after', on_delete=models.CASCADE)
    convert_rule = models.ForeignKey(ConvertRule, on_delete=models.CASCADE)


class DataConversionInfo(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    data_convert_id = models.AutoField(primary_key=True)
    data_format_after = models.ForeignKey(DataFormat, on_delete=models.CASCADE)