import frappe

@frappe.whitelist()
def create_timesheet_entry(data):
    timesheet = frappe.new_doc("Timesheet")
    timesheet.update(data)
    timesheet.save(ignore_permigitssions=True)
    return timesheet

@frappe.whitelist()
def create_time_log(timesheet, task_name, time_spent, from_time, to_time, project, activity_type):
    timesheet = frappe.get_doc("Timesheet", timesheet)
   
    # Convert time_spent to hours
    hours_spent = time_spent / 3600

    row = timesheet.append('time_logs', {})
    row.activity_type =  activity_type
    row.project =  project
    row.hours_category =  "CPH" if project else "NCPH"
    row.description =  task_name
    row.hours =  hours_spent
    row.from_time =  from_time
    row.to_time = to_time

    timesheet.save(ignore_permissions=True)

    return timesheet

@frappe.whitelist(allow_guest=True)  # Remove allow_guest=True if authentication is required
def save_timesheet_heartbeat(timesheet, description, screenshot=None):
    """
    API method to save Timesheet Heatbeat data.

    Args:
    timesheet (str): The linked Timesheet ID.
    description (str): Description text.
    screenshot (str, optional): Base64 encoded image data.

    Returns:
    dict: Success or error response.
    """

    try:
        # Create a new Timesheet Heatbeat record
        heatbeat = frappe.get_doc({
            "doctype": "Timesheet Heatbeat",
            "timesheet": timesheet,
            "description": description
        })

        # Handle image upload if provided
        if screenshot:
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": f"screenshot_{timesheet}.png",
                "content": base64.b64decode(screenshot),
                "is_private": 1,
                "attached_to_doctype": "Timesheet Heatbeat",
                "attached_to_name": heatbeat.name
            })
            file_doc.insert()
            heatbeat.screenshot = file_doc.file_url  # Save file URL in the Timesheet Heatbeat record

        # Insert the Timesheet Heatbeat record
        heatbeat.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "message": "Timesheet Heatbeat saved successfully!", "data": heatbeat.as_dict()}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Timesheet Heatbeat API Error")
        return {"success": False, "error": str(e)}