import logging
import os

import django

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ConvertService.settings")
django.setup()

from accounts.models import Account as User
from home.models import Tenant

username = os.getenv("SUPERUSER_USERNAME", "")
email = os.getenv("SUPERUSER_EMAIL", "")
password = os.getenv("SUPERUSER_PASSWORD", "")

try:
    user = User.objects.get(username=username or None)
    user.tenant = Tenant.objects.get(id=1)
    user.is_superuser = True
    user.is_staff = True
    user.save()
    logger.info(
        f"Administrator account '{username}' already exists. Skipping account creation."
    )
except User.DoesNotExist:
    try:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                tenant=Tenant.objects.get(id=1),
            )
            logger.info(
                f"Administrator account '{username}' has been successfully created!"
            )
        else:
            logger.info(
                f"Username '{username}' already exists. Skipping account creation."
            )
    except Exception as e:
        logger.error(f"An error occurred while creating the administrator account: {e}")
