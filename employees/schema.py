# employees/schema.py
import strawberry
from typing import List, Optional
from employees.models import Employee

@strawberry.type
class EmployeeType:
    id: int
    name: str
    email: str
    phone: Optional[str]
    role: str
    is_active: bool
    created_at: str  # ISO string for simplicity

@strawberry.type
class EmployeeQuery:
    @strawberry.field
    def employees(self) -> List[EmployeeType]:
        qs = Employee.objects.all()
        return [
            EmployeeType(
                id=e.id,
                name=e.name,
                email=e.email,
                phone=e.phone,
                role=e.role,
                is_active=e.is_active,
                created_at=e.created_at.isoformat() if e.created_at else ""
            )
            for e in qs
        ]

@strawberry.type
class EmployeeMutation:
    # placeholder, we'll implement create/update/delete later
    pass
