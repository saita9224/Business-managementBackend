# tenants/urls.py

from django.urls import path
from .views import upload_business_logo

urlpatterns = [
    path("upload-logo/", upload_business_logo, name="upload_business_logo"),
]
