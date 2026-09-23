from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from employees.models import RolePermission
from tenants.models import Business


ALLOWED_LOGO_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def employee_can_manage_tenant_profile(employee) -> bool:
    if not employee or not getattr(employee, "is_active", False):
        return False

    if employee.roles.filter(name__iexact="Admin").exists():
        return True

    roles = employee.roles.all()
    if not roles.exists():
        return False

    return RolePermission.objects.filter(
        role__in=roles,
        permission__code="tenant.manage_profile",
    ).exists()


def validate_business_logo(logo_file: UploadedFile) -> None:
    if not logo_file:
        raise ValueError("No image file provided under key 'logo'.")

    max_size = getattr(settings, "MAX_BUSINESS_LOGO_BYTES", 2 * 1024 * 1024)
    if logo_file.size and logo_file.size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValueError(f"Logo file is too large. Maximum size is {max_mb:.1f} MB.")

    content_type = getattr(logo_file, "content_type", "")
    if content_type and content_type not in ALLOWED_LOGO_CONTENT_TYPES:
        raise ValueError("Logo must be a JPEG, PNG, or WebP image.")

    original_position = None
    try:
        if hasattr(logo_file, "tell"):
            original_position = logo_file.tell()
        data = logo_file.read()
        Image.open(BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Uploaded logo is not a valid image.")
    finally:
        if hasattr(logo_file, "seek"):
            logo_file.seek(original_position or 0)


@transaction.atomic
def update_business_logo(business_id: int, logo_file: UploadedFile) -> Business:
    validate_business_logo(logo_file)

    business = Business.objects.select_for_update().get(id=business_id)
    old_logo_name = business.logo.name if business.logo else None

    business.logo = logo_file
    business.save(update_fields=["logo"])

    if old_logo_name and old_logo_name != business.logo.name:
        business.logo.storage.delete(old_logo_name)

    return business


def update_business_name(business_id: int, name: str) -> Business:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Business name is required.")

    business = Business.objects.get(id=business_id)
    business.name = clean_name
    business.save(update_fields=["name"])
    return business
