from django.db import models

class ConvertRuleCategory(models.Model):
    id = models.AutoField(primary_key=True)
    convert_rule_category_id = models.CharField(unique=True, max_length=50)
    convert_rule_category_name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "convert_rule_category"

    def __str__(self):
        return self.convert_rule_category_name


class ConvertRule(models.Model):
    id = models.AutoField(primary_key=True)
    convert_rule_id = models.CharField(unique=True, max_length=50, default='default_rule_id')
    convert_rule_name = models.CharField(max_length=255, null=True, blank=True)
    convert_rule_category = models.ForeignKey(ConvertRuleCategory, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "convert_rule"

    def __str__(self):
        return self.convert_rule_name


class Migrations(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    hash = models.CharField(unique=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)