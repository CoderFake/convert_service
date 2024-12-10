from django.db import models

class ConvertRuleCategory(models.Model):
    convert_rule_category_id = models.AutoField(primary_key=True)
    convert_rule_category_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ConvertRule(models.Model):
    convert_rule_id = models.AutoField(primary_key=True)
    convert_rule_category = models.ForeignKey(ConvertRuleCategory, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
