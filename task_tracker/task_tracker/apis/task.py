import frappe
from frappe import _

@frappe.whitelist()
def get_user_tasks(search_text=None):
    
    try:
        task_tracker_settings = frappe.get_doc("Task Tracker Settings")

        filters=[
            ["Task","_assign","like",f"%{frappe.session.user}%"],
            ["Task","workflow_state","=",f"{task_tracker_settings.task_workflow_state}"]
            
        ]
        or_filter = []
        if search_text:
            or_filter = [
                ["Task", "subject", "like", f"%{search_text}%"],
                ["Task", "project", "like", f"%{search_text}%"],
                ["Task", "custom_project_name", "like", f"%{search_text}%"],
                ["Task", "priority", "like", f"%{search_text}%"],
            ]

        tasks = frappe.get_list('Task', 
                                filters=filters,
                                or_filters=or_filter, 
                                fields=['name', 'subject', 'project', 'custom_project_name', 'priority', 'description', 'expected_time', 'custom_activity_type'],
                                order_by='modified desc'
        )

        for task in tasks:
            if task.project and not task.custom_project_name:
                project_name = frappe.db.get_value("Project", task.project, "project_name")
                if project_name:
                    task.custom_project_name = project_name
            if not task.custom_activity_type:
                task.custom_activity_type = frappe.db.get_single_value("Task Tracker Settings", "default_activity_type")

        
        return tasks
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error fetching tasks"))
        return {"error": str(e)}