import frappe

def execute():
    frappe.logger().info("Starting patch: fill custom_project_name in Task")

    # Fetch all tasks where custom_project_name is empty or null
    tasks = frappe.get_all(
        "Task",
        filters={"custom_project_name": ["in", [None, ""]]},
        fields=["name", "project"]
    )

    frappe.logger().info(f"Found {len(tasks)} tasks to update")

    for task in tasks:
        if task.project:
            # Fetch project name
            project_name = frappe.db.get_value("Project", task.project, "project_name")
            if project_name:
                frappe.db.set_value("Task", task.name, "custom_project_name", project_name)
    
    frappe.db.commit()
    frappe.logger().info("Completed patch: fill custom_project_name in Task")
