# hr/permissions.py

"""
Permissions for the HR app.
permissions_loader.py loads these into the DB on startup.
"""

PERMISSIONS = {
    "hr.view_contracts",
    "hr.manage_contracts",
    "hr.view_attendance",
    "hr.manage_attendance",
    "hr.self_checkin",
    "hr.view_salary",
    "hr.manage_salary",
    "hr.view_leave",
    "hr.manage_leave",
    "hr.request_leave",
}

PERMISSION_META = {
    "hr.view_contracts":    ("View Contracts",       "Can view employee contracts and terms"),
    "hr.manage_contracts":  ("Manage Contracts",     "Can create and update employee contracts"),
    "hr.view_attendance":   ("View Attendance",      "Can view attendance records for all employees"),
    "hr.manage_attendance": ("Record Attendance",    "Can record and edit attendance for any employee"),
    "hr.self_checkin":      ("Self Check-in",        "Can check themselves in and out for the day"),
    "hr.view_salary":       ("View Payroll",         "Can view salary records and payslips"),
    "hr.manage_salary":     ("Manage Payroll",       "Can generate, approve, and record salary payments"),
    "hr.view_leave":        ("View Leave Requests",  "Can view all employee leave requests"),
    "hr.manage_leave":      ("Approve Leave",        "Can approve or reject employee leave requests"),
    "hr.request_leave":     ("Request Leave",        "Can submit own leave requests"),
}