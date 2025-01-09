from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ConfigsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'configs'

    def ready(self):
        try:
            from django.contrib.auth.signals import user_logged_in, user_logged_out
            from configs.cache_manager import ConvertDataValueCache
            from django.dispatch import receiver

            @receiver(user_logged_in)
            def handle_user_logged_in(sender, request, user, **kwargs):
                try:
                    if hasattr(user, 'tenant') and user.tenant:
                        tenant_id = user.tenant.id
                        cache_manager = ConvertDataValueCache()
                        cache_manager.load_cache(tenant_id)
                        logger.info(f"Cache loaded for tenant {tenant_id} after user {user.email} logged in.")
                except Exception as e:
                    logger.error(f"Error loading cache during user login: {e}")

            @receiver(user_logged_out)
            def handle_user_logged_out(sender, request, user, **kwargs):
                try:
                    if hasattr(user, 'tenant') and user.tenant:
                        tenant_id = user.tenant.id
                        cache_manager = ConvertDataValueCache()
                        cache_manager.delete_cache(tenant_id)
                        logger.info(f"Cache deleted for tenant {tenant_id} after user {user.email} logged out.")
                except Exception as e:
                    logger.error(f"Error deleting cache during user logout: {e}")

            logger.info("Configs app is ready, signals initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing signals in ConfigsConfig: {e}")
