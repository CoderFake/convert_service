from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from home.models import Tenant

class Account(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("テナント名"))
    modified_at = models.DateTimeField(auto_now=True, verbose_name=_("変更日"))
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    groups = None
    user_permissions = None

    is_superuser = models.BooleanField(default=False)

    class Meta:
        db_table = "account"
        verbose_name = _("アカウント")
        verbose_name_plural= _("アカウント")

    def __str__(self):
        return self.email
