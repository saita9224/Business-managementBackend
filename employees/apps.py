# employees/apps.py
from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'employees'

    def ready(self):
        from .permissions_loader import load_permissions
        try:
            load_permissions()
        except Exception:
            pass
