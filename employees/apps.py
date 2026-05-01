# employees/apps.py  
from django.apps import AppConfig

class EmployeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'employees'

    def ready(self):
        # Do NOT call load_permissions() here.
        # Run: python manage.py sync_permissions --all-tenants
        pass