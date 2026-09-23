from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import sync_to_async
from django_tenants.utils import schema_context

from tenants.models import Business
from authentication.services import decode_jwt_token
from tenants.services import (
    employee_can_manage_tenant_profile,
    update_business_logo,
)


def _employee_can_manage_in_schema(employee, schema_name: str) -> bool:
    with schema_context(schema_name):
        return employee_can_manage_tenant_profile(employee)


@csrf_exempt
async def upload_business_logo(request):
    """
    HTTP POST multipart/form-data view to upload business logo.
    Header: Authorization: Bearer <JWT_TOKEN>
    Body: multipart file in 'logo' field.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        return JsonResponse({"error": "Authentication token missing"}, status=401)

    # 1. Decode JWT and find employee
    employee = await decode_jwt_token(token)
    if not employee:
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    schema_name = getattr(employee, "_jwt_schema_name", None)
    if not schema_name or schema_name == "public":
        return JsonResponse({"error": "Tenant context missing"}, status=400)

    allowed = await sync_to_async(_employee_can_manage_in_schema)(
        employee,
        schema_name,
    )
    if not allowed:
        return JsonResponse({"error": "Permission denied: tenant.manage_profile"}, status=403)

    # 2. Check for uploaded file
    logo_file = request.FILES.get("logo")
    if not logo_file:
        return JsonResponse({"error": "No image file provided under key 'logo'"}, status=400)

    # 3. Get Business and save via the shared validator/service.
    try:
        business = await Business.objects.aget(schema_name=schema_name)
    except Business.DoesNotExist:
        return JsonResponse({"error": "Business not found"}, status=404)

    try:
        business = await sync_to_async(update_business_logo)(business.id, logo_file)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    
    logo_url = request.build_absolute_uri(business.logo.url) if business.logo else None

    return JsonResponse({
        "status": "success",
        "message": "Logo uploaded successfully",
        "business_id": business.id,
        "business_name": business.name,
        "logo_url": logo_url,
    })
