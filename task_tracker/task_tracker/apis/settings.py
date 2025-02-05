import frappe

@frappe.whitelist()
def get_task_tracker_settings():
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    return task_tracker_settings