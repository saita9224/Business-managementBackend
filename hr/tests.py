from datetime import date, time

from django.test import SimpleTestCase

from hr.models import AttendanceRecord, EmployeeContract, LeaveRequest
from hr.permissions import PERMISSION_META, PERMISSIONS
from hr.services import _is_late, _working_days_in_month


class HRPermissionTests(SimpleTestCase):
    def test_all_permissions_have_metadata(self):
        self.assertEqual(PERMISSIONS, set(PERMISSION_META))


class HRAttendanceCalculationTests(SimpleTestCase):
    def test_is_late_respects_grace_period(self):
        contract = EmployeeContract(
            check_in_time=time(9, 0),
            late_threshold_mins=15,
        )

        self.assertFalse(_is_late(time(9, 15), contract))
        self.assertTrue(_is_late(time(9, 16), contract))

    def test_attendance_weight_maps_statuses(self):
        self.assertEqual(
            AttendanceRecord(status=AttendanceRecord.PRESENT).attendance_weight,
            1.0,
        )
        self.assertEqual(
            AttendanceRecord(status=AttendanceRecord.HALF_DAY).attendance_weight,
            0.5,
        )
        self.assertEqual(
            AttendanceRecord(status=AttendanceRecord.ABSENT).attendance_weight,
            0.0,
        )

    def test_working_days_in_month_counts_weekdays(self):
        self.assertEqual(_working_days_in_month(2026, 5, 5), 21)


class HRLeaveTests(SimpleTestCase):
    def test_leave_total_days_is_inclusive(self):
        leave = LeaveRequest(
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 12),
        )

        self.assertEqual(leave.total_days, 3)
