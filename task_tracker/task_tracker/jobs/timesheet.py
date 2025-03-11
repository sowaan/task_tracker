import frappe
from frappe.utils import add_days, nowdate
from task_tracker.task_tracker.apis.timesheet import send_screenshot_to_sowaan_ai

def delete_old_timesheet_heartbeats():
    delete_heartbeat_data_after_days = frappe.db.get_single_value('Task Tracker Settings', 'delete_heartbeat_data_after_days')
    if not delete_heartbeat_data_after_days:
        delete_heartbeat_data_after_days = 30

    # Calculate the cutoff date: 30 days ago
    cutoff_date = add_days(nowdate(), -delete_heartbeat_data_after_days)
    
    # Get all Timesheets which are submitted and with a posting_date or modified date (depending on your workflow)
    timesheets = frappe.get_all("Timesheet", 
        filters={
            "docstatus": 1,  # 1 indicates submitted
            "custom_heatmap_data": ["is", "set"],
            "modified": ["<=", cutoff_date]
        },
        fields=["name"]
    )

    # Log the number of timesheets found for deletion of heartbeats
    frappe.log(f"Deleting Timesheet Heartbeats: Found {len(timesheets)} timesheets submitted on or before {cutoff_date}")

    for ts in timesheets:
        # Assuming "Timesheet Heartbeat" links to Timesheet via a field "timesheet"
        heartbeats = frappe.get_all("Timesheet Heartbeat", filters={"timesheet": ts.name}, fields=["name"])
        for hb in heartbeats:
            try:
                frappe.delete_doc("Timesheet Heartbeat", hb.name, ignore_permissions=True, force=True)
            except Exception as e:
                frappe.log_error(title="Error Deleting Timesheet Heartbeat", message=f"Error deleting Heartbeat {hb.name} for Timesheet {ts.name}: {e}")

    #commit the db
    frappe.db.commit()


def send_heartbeats_to_sowaan_ai():
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    if (task_tracker_settings.measure_productivity_using_ai 
        and task_tracker_settings.use_sowaan_ai
        and task_tracker_settings.sowaan_ai_instance_url
        and task_tracker_settings.sowaan_ai_api_key
        and task_tracker_settings.sowaan_ai_api_secret
        ):
        heartbeats = frappe.get_all("Timesheet Heartbeat",
            filters=[
                ["Timesheet Heartbeat","productivity_flag","is","not set"]
            ],
            fields=["name"]
        )
        frappe.log(f"Sending Timesheet Heartbeats: Found {len(heartbeats)} heartbeats to send to Sowaan AI")
        for hb in heartbeats:
            try:
                send_screenshot_to_sowaan_ai(
                    hb.name, 
                    task_tracker_settings.sowaan_ai_instance_name,
                    task_tracker_settings.sowaan_ai_instance_url,
                    task_tracker_settings.sowaan_ai_api_key,
                    task_tracker_settings.sowaan_ai_api_secret,
                )
            except Exception as e:
                frappe.log_error(title="Error Sending Timesheet Heartbeat", message=f"Error sending Heartbeat {hb.name}: {e}") 
        
          