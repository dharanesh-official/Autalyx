import pandas as pd
from datetime import date
from calendar import monthrange
def calculate_payslip(employee, year, month, db, Holiday, LeaveRequest):
    """
    Calculates the payslip for a given employee for a specific month and year.
    """
    start_of_month = date(year, month, 1)
    days_in_month = monthrange(year, month)[1]
    end_of_month = date(year, month, days_in_month)
    month_dates = pd.date_range(start_of_month, end_of_month)

    
    holidays_query = Holiday.query.filter(
        db.extract('year', Holiday.date) == year,
        db.extract('month', Holiday.date) == month
    ).all()
    public_holidays = [h.date for h in holidays_query]
    payable_days_count = 0
    for day in month_dates:
        if day.weekday() != 6 and day.date() not in public_holidays:
            payable_days_count += 1
        
    if payable_days_count == 0:
        return {
            "employee_name": employee.name,
            "month_year": start_of_month.strftime("%B %Y"),
            "gross_salary": employee.salary,
            "total_payable_days": 0,
            "per_day_salary": 0,
            "deductible_leave_days": 0,
            "deductions": 0,
            "net_salary": 0,
            "error": "No payable days in this month."
        }

    per_day_salary = employee.salary / payable_days_count
    approved_leaves_query = LeaveRequest.query.filter(
        LeaveRequest.user_id == employee.id,
        LeaveRequest.status == 'Approved'
    ).all()
    
    deductible_leave_days = 0
    leave_dates_list = []
    for leave in approved_leaves_query:
        leave_dates = pd.date_range(leave.start_date, leave.end_date)
        for leave_day in leave_dates:
            if leave_day.month == month and leave_day.year == year:
                if leave_day.weekday() != 6 and leave_day.date() not in public_holidays:
                    deductible_leave_days += 1
                    leave_dates_list.append(leave_day.strftime('%d-%b'))

    deductions = deductible_leave_days * per_day_salary
    net_salary = employee.salary - deductions

    payslip_data = {
        "employee_name": employee.name,
        "month_year": start_of_month.strftime("%B %Y"),
        "gross_salary": employee.salary,
        "total_payable_days": payable_days_count,
        "per_day_salary": per_day_salary,
        "deductible_leave_days": deductible_leave_days,
        "leave_dates": leave_dates_list,
        "deductions": deductions,
        "net_salary": net_salary
    }
    
    return payslip_data