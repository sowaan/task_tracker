import frappe
import json

@frappe.whitelist()
def create_timesheet_entry():
    try:
        task_tracker_settings = frappe.get_doc("Task Tracker Settings")

        # Parse the incoming request JSON
        data = frappe.request.get_json()

        if not data:
            frappe.throw("Missing request data")

        if not isinstance(data, dict):
            frappe.throw("Invalid request format. Expected a JSON object.")

        # Ensure "doctype" is set
        data["doctype"] = "Timesheet"

        # Ensure "time_logs" exists and is a **list**
        if "time_logs" not in data or not isinstance(data["time_logs"], list):
            frappe.throw("'time_logs' must be a list of dictionaries")

        # Loop through time_logs and assign defaults if missing
        for log in data["time_logs"]:
            if not isinstance(log, dict):
                frappe.throw("Each 'time_logs' entry must be a dictionary")

            if "project" not in log:
                log["project"] = task_tracker_settings.default_project

            if "activity_type" not in log:
                log["activity_type"] = task_tracker_settings.default_activity_type

        # Create and save the Timesheet
        timesheet = frappe.get_doc(data)
        timesheet.insert(ignore_permissions=True)

        return timesheet

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Timesheet Creation Error")
        return {"error": str(e)}

@frappe.whitelist()
def create_time_log(timesheet, task_name, time_spent, from_time, to_time, project, activity_type):
    timesheet = frappe.get_doc("Timesheet", timesheet)
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    
    # Remove time_logs with description "Initial entry to create a timesheet"
    timesheet.time_logs = [log for log in timesheet.time_logs if log.description != "Initial entry to create a timesheet"]

    # Convert time_spent to hours
    hours_spent = time_spent / 3600

    if not project:
        project = task_tracker_settings.default_project
    if not activity_type:
        activity_type = task_tracker_settings.default_activity_type

    row = timesheet.append('time_logs', {})
    row.activity_type = activity_type
    row.project = project
    row.hours_category = "CPH" if project else "NCPH"
    row.description = task_name
    row.hours = hours_spent
    row.from_time = from_time
    row.to_time = to_time

    timesheet.save(ignore_permissions=True)

    return timesheet