class TelegramRouter:
    """
    Router for Telegram account models to use PostgreSQL database.
    """
    telegram_app = 'accounts'
    telegram_models = {'TelegramAccount', 'AccountAuditLog', 'GlobalAppSettings'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.telegram_app and model.__name__ in self.telegram_models:
            return 'telegram_db'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.telegram_app and model.__name__ in self.telegram_models:
            return 'telegram_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label == self.telegram_app and obj1.__class__.__name__ in self.telegram_models and
            obj2._meta.app_label == self.telegram_app and obj2.__class__.__name__ in self.telegram_models
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.telegram_app and model_name in [m.lower() for m in self.telegram_models]:
            return db == 'telegram_db'
        return None