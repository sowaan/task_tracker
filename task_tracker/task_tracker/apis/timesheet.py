import frappe
import base64
import json
from frappe import _
import requests
from task_tracker.task_tracker.utils import analyze_image


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
        timesheet.custom_heartbeat_interval = task_tracker_settings.heartbeat_timeout_minutes
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

@frappe.whitelist()
def update_time_log(timesheet, task_name, time_spent, from_time, to_time, project, activity_type):
    timesheet = frappe.get_doc("Timesheet", timesheet)
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    
    # Convert time_spent to hours
    hours_spent = time_spent / 3600

    if not project:
        project = task_tracker_settings.default_project
    if not activity_type:
        activity_type = task_tracker_settings.default_activity_type

    for log in timesheet.time_logs:
        if not log.to_time:
            log.activity_type = activity_type
            log.project = project
            log.hours_category = "CPH" if project else "NCPH"
            log.hours = hours_spent
            log.to_time = to_time

    timesheet.save(ignore_permissions=True)

    return timesheet

@frappe.whitelist()
def delete_time_logs(timesheet_id, task_ids):
    try:
        timesheet = frappe.get_doc("Timesheet", timesheet_id)
        task_ids = frappe.parse_json(task_ids) if isinstance(task_ids, str) else task_ids
        
        if not timesheet:
            return {"status": "error", "message": _(f"Timesheet {timesheet_id} not found.")}

        updated_time_logs = [log for log in timesheet.time_logs if log.name not in task_ids]
        timesheet.time_logs = updated_time_logs
        timesheet.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"status": "success", "message": _(f"Time logs for tasks {', '.join(task_ids)} deleted successfully.")}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "delete_time_logs Error")
        return {"status": "error", "message": _(f"Error deleting time logs: {str(e)}")}
    
    

@frappe.whitelist()  # Remove allow_guest=True if authentication is required
def save_timesheet_heartbeat(timesheet, description, screenshot=None):
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    try:
        heartbeat = frappe.get_doc({
            "doctype": "Timesheet Heartbeat",
            "timesheet": timesheet,
            "description": description
        })
        heartbeat.insert(ignore_permissions=True)
        frappe.db.commit() 

        file_url = None
        if screenshot:
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": f"screenshot_{heartbeat.name}.png",
                "content": base64.b64decode(screenshot),
                "is_private": 1,
                "attached_to_doctype": "Timesheet Heartbeat",
                "attached_to_name": heartbeat.name  # Now the name exists
            })
            file_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            # Save file URL to the Timesheet Heartbeat record
            file_url = file_doc.file_url
            heartbeat.screenshot = file_url
            heartbeat.save(ignore_permissions=True)  # Update the record with the screenshot URL

            if (task_tracker_settings.measure_productivity_using_ai 
                and not task_tracker_settings.use_sowaan_ai
                and task_tracker_settings.hugging_face_api_token
                and task_tracker_settings.hugging_face_model):
                if file_url.startswith('/'):
                    file_url = file_url[1:]

                frappe.enqueue(process_screenshot, docname=heartbeat.name, ss_path=file_url)
            elif (task_tracker_settings.measure_productivity_using_ai 
                and task_tracker_settings.use_sowaan_ai
                and task_tracker_settings.sowaan_ai_instance_url
                and task_tracker_settings.sowaan_ai_api_key
                and task_tracker_settings.sowaan_ai_api_secret):
                frappe.enqueue(send_screenshot_to_sowaan_ai, 
                               docname=heartbeat.name, 
                               ss_path=file_url, 
                               instance_url=task_tracker_settings.sowaan_ai_instance_url, 
                               api_key=task_tracker_settings.sowaan_ai_api_key, 
                               api_secret=task_tracker_settings.sowaan_ai_api_secret
                               )


        return {"success": True, "message": "Timesheet Heatbeat saved successfully!"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Timesheet Heatbeat API Error")
        return {"success": False, "error": str(e)}



@frappe.whitelist
def update_heartbeat(ref_name, productivity_flag, productivity_reason, ai_response, error_message):
    frappe.db.set_value('Timesheet Heartbeat', ref_name, {
        'productivity_flag': productivity_flag,
        'productivity_reason': productivity_reason,
        'error_message': error_message,
        'ai_response': ai_response
    })


def process_screenshot(docname, ss_path):
    response = analyze_image(ss_path)
    try:
        productivity = json.loads(response)

        frappe.db.set_value('Timesheet Heartbeat', docname, {
            'productivity_flag': productivity.get("status", ""),
            'productivity_reason': productivity.get("message", ""),
            'error_message': "",
            'ai_response': response
        })

    except Exception as e:
        frappe.db.set_value('Timesheet Heartbeat', docname, {
            'productivity_flag': "non-productive",
            'productivity_reason': "",
            'error_message': str(e),
            'ai_response': response
        })

def send_screenshot_to_sowaan_ai(docname, ss_path, instance_url, api_key, api_secret):
    try:
        # Read and encode the image file to base64
        file_path = frappe.get_site_path(ss_path.lstrip("/"))
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        
        # Prepare the API endpoint
        api_endpoint = f"{instance_url}/api/method/sowaan_ai.sowaan_ai.apis.image.save_image"
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {api_key}:{api_secret}"
        }
        
        # Prepare payload
        payload = {
            "instance_name": instance_url,
            "ref_name": docname,
            "image": encoded_string
        }
        
        # Make the request
        response = requests.post(api_endpoint, json=payload, headers=headers)
        
        # Handle response
        if response.status_code != 200:
            frappe.log_error(f"Failed to send screenshot: {response.text}", "send_screenshot_to_sowaan_ai")
    except Exception as e:
        frappe.log_error(f"Exception: {str(e)}\n\nTraceback:\n{frappe.get_traceback()}", "send_screenshot_to_sowaan_ai")


