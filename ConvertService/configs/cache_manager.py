import json
import os
import redis
import logging
from configs.models import ConvertDataValue
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


class ConvertDataValueCache:
    """
    A class to manage caching of ConvertDataValue for tenants using Redis.
    """

    def __init__(self):
        self.client = self.get_redis_client()

    @staticmethod
    def get_redis_client():

        try:
            client = redis.StrictRedis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                decode_responses=True
            )
            return client
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}")
            raise

    def load_cache(self, tenant_id):

        try:
            cache_key = f"convert_data_value:{tenant_id}"
            if not self.client.exists(cache_key):  # Check if cache exists
                data = list(ConvertDataValue.objects.filter(tenant_id=tenant_id).values(
                    'data_value_before', 'data_value_after'
                ))
                self.client.set(cache_key, json.dumps(data))  # Cache data
            return json.loads(self.client.get(cache_key))
        except Exception as e:
            logger.error(f"Error loading cache for tenant {tenant_id}: {e}")
            return []

    def refresh_cache(self, tenant_id):

        try:
            cache_key = f"convert_data_value:{tenant_id}"
            data = list(ConvertDataValue.objects.filter(tenant_id=tenant_id).values(
                'data_value_before', 'data_value_after'
            ))
            self.client.set(cache_key, json.dumps(data))
        except Exception as e:
            logger.error(f"Error refreshing cache for tenant {tenant_id}: {e}")

    def delete_cache(self, tenant_id):

        try:
            cache_key = f"convert_data_value:{tenant_id}"
            self.client.delete(cache_key)
        except Exception as e:
            logger.error(f"Error deleting cache for tenant {tenant_id}: {e}")

    def get_cache(self, tenant_id):

        try:
            cache_key = f"convert_data_value:{tenant_id}"
            if self.client.exists(cache_key):
                return json.loads(self.client.get(cache_key))
            else:
                return self.load_cache(tenant_id)
        except Exception as e:
            logger.error(f"Error retrieving cache for tenant {tenant_id}: {e}")
            return []


cache_manager = ConvertDataValueCache()

@receiver(post_save, sender=ConvertDataValue)
@receiver(post_delete, sender=ConvertDataValue)
def handle_convert_data_value_change(sender, instance, **kwargs):

    try:
        tenant_id = instance.tenant.id
        if tenant_id:
            cache_manager.refresh_cache(tenant_id)
            logger.info(f"Cache refreshed for tenant {tenant_id} due to changes in ConvertDataValue.")
    except Exception as e:
        logger.error(f"Error handling ConvertDataValue signal: {e}")
