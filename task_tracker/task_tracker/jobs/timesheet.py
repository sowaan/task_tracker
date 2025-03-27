import frappe
from frappe.model.workflow import get_workflow_name, get_transitions, apply_workflow
from frappe.utils import add_days, nowdate
from task_tracker.task_tracker.apis.timesheet import send_screenshot_to_sowaan_ai
from datetime import datetime, timedelta

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
                attached_file = frappe.db.get_value("File",
                    {"attached_to_doctype": "Timesheet Heartbeat", "attached_to_name": hb.name},
                    "file_url"
                )
                send_screenshot_to_sowaan_ai(
                    hb.name, 
                    attached_file,
                    task_tracker_settings.sowaan_ai_instance_name,
                    task_tracker_settings.sowaan_ai_instance_url,
                    task_tracker_settings.sowaan_ai_api_key,
                    task_tracker_settings.sowaan_ai_api_secret,
                )
            except Exception as e:
                frappe.log_error(title="Error Sending Timesheet Heartbeat", message=f"Error sending Heartbeat {hb.name}: {e}") 

def auto_submit_timesheets():
    tt_settings = frappe.get_doc("Task Tracker Settings")
    if tt_settings.automatically_apply_workflow_action:
        after_days = tt_settings.after_days
        if after_days > 0:
            from_workflow_state = tt_settings.from_workflow_state
            workflow_action = tt_settings.workflow_action
            from_date = tt_settings.from_date

            cutoff_date = add_days(nowdate(), -after_days)
            timesheets = frappe.get_all("Timesheet",
                filters={
                    "creation": ["<=", cutoff_date],
                    "creation": [">=", from_date],
                    "workflow_state": from_workflow_state
                },
                fields=["name", "owner"]
            )

            # Log the number of timesheets found for submission
            frappe.log(f"Applying workflow on Timesheets: Found {len(timesheets)} timesheets created on or before {cutoff_date} and on or after {from_date} in state '{from_workflow_state}'")

            for ts in timesheets:
                try:
                    timesheet = frappe.get_doc("Timesheet", ts.name)
                    
                    # Apply workflow transition as the creator of the timesheet
                    frappe.set_user(ts["owner"])
                    
                    apply_workflow(timesheet, workflow_action)
                    
                    # Add a comment to the Timesheet
                    timesheet.add_comment(
                        comment_type="Info",
                        text=f"{workflow_action} auto-applied by System."
                    )
                    
                    frappe.log_error(f"Timesheet {ts['name']} auto-submitted by '{ts['owner']}' using transition '{workflow_action}'", "Auto Submit Timesheet")
                    
                    # Reset user back to administrator/system user
                    frappe.set_user("Administrator")
                except Exception as e:
                    frappe.log_error(title="Error Submitting Timesheet", message=f"Error submitting Timesheet {ts.name}: {e}")

            #commit the db
            frappe.db.commit()
        
          