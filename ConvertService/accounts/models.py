from django.contrib.auth.models import AbstractUser
from django.db import models
from home.models import Tenant

class Account(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = "account"

    def __str__(self):
        return self.username
