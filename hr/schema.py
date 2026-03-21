# hr/schema.py

from .queries import HRQuery
from .mutations import HRMutation
from .dataloaders import create_hr_dataloaders

__all__ = ["HRQuery", "HRMutation", "create_hr_dataloaders"]