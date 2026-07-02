import frappe
from frappe.model.workflow import get_workflow_name, get_transitions, apply_workflow
from frappe.utils import add_days, nowdate, formatdate
from task_tracker.task_tracker.apis.timesheet import send_screenshot_to_sowaan_ai
from datetime import datetime, timedelta

BATCH_SIZE = 1000

def delete_old_timesheet_heartbeats():
    delete_after_days = (
        frappe.db.get_single_value("Task Tracker Settings", "delete_heartbeat_data_after_days")
        or 30
    )

    cutoff_date = add_days(nowdate(), -delete_after_days)

    frappe.logger().info(f"Heartbeat cleanup started. Cutoff: {cutoff_date}")

    while True:

        # STEP 1: Get batch of heartbeat names (small chunk only)
        heartbeats = frappe.get_all(
            "Timesheet Heartbeat",
            filters={
                "modified": ["<=", cutoff_date],
                "docstatus": ["!=", 2],  # optional safety
            },
            fields=["name"],
            limit=BATCH_SIZE
        )

        if not heartbeats:
            break

        heartbeat_names = [h.name for h in heartbeats]

        # STEP 2: Fetch all attached files in one query
        files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Timesheet Heartbeat",
                "attached_to_name": ["in", heartbeat_names]
            },
            fields=["name"]
        )

        file_names = [f.name for f in files]

        # STEP 3: Delete files first (important for cleanup integrity)
        for fname in file_names:
            try:
                frappe.delete_doc("File", fname, ignore_permissions=True, force=True)
            except Exception as e:
                frappe.log_error(
                    title="Heartbeat File Deletion Error",
                    message=f"File: {fname}\nError: {str(e)}"
                )

        # STEP 4: Bulk delete heartbeats (FAST SQL DELETE)
        try:
            frappe.db.sql("""
                DELETE FROM `tabTimesheet Heartbeat`
                WHERE name IN %(names)s
            """, {"names": heartbeat_names})

        except Exception as e:
            frappe.log_error(
                title="Heartbeat Bulk Delete Error",
                message=str(e)
            )

        frappe.db.commit()

        frappe.logger().info(f"Deleted batch of {len(heartbeat_names)} heartbeats")

    frappe.logger().info("Heartbeat cleanup completed.")


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
        if after_days >= 0:
            from_workflow_state = tt_settings.from_workflow_state
            workflow_action = tt_settings.workflow_action
            from_date = tt_settings.from_date
            # from_date = formatdate(from_date, "dd-mm-yyyy")

            cutoff_date = add_days(nowdate(), -after_days if after_days > 0 else 0)
            # cutoff_date = formatdate(cutoff_date, "dd-mm-yyyy")
            timesheets = frappe.get_all("Timesheet",
                filters=[
                    ["Timesheet","creation","Between",[from_date,cutoff_date]],
                    ["Timesheet","workflow_state","=",from_workflow_state]
                ],
                fields=["name", "owner"]
            )

            # Log the number of timesheets found for submission
            frappe.log(f"Applying workflow on Timesheets: Found {len(timesheets)} timesheets created on or before {cutoff_date} and on or after {from_date} in state '{from_workflow_state}'")

            # Store the currently logged-in user
            previous_user = frappe.session.user  
            for ts in timesheets:
                try:
                    timesheet = frappe.get_doc("Timesheet", ts.name)

                    # Clean up Timesheet Logs
                    cleaned_logs = []
                    for log in timesheet.time_logs:
                        from_time = log.from_time
                        to_time = log.to_time

                        # Case 1: Both missing → skip (delete)
                        if not from_time and not to_time:
                            continue

                        # Case 2: from_time present but to_time missing
                        if from_time and not to_time:
                            log.to_time = from_time

                        # Case 3: to_time present but from_time missing
                        elif to_time and not from_time:
                            log.from_time = to_time

                        cleaned_logs.append(log)

                    # Replace logs with cleaned list
                    timesheet.time_logs = cleaned_logs

                    # Save the cleaned Timesheet
                    timesheet.save(ignore_permissions=True)

                    # Apply workflow transition as the creator of the timesheet
                    frappe.set_user(ts["owner"])
                    
                    apply_workflow(timesheet, workflow_action)
                    
                    # Add a comment to the Timesheet
                    timesheet.add_comment(
                        comment_type="Info",
                        text=f"{workflow_action} auto-applied by System."
                    )
                    
                    # frappe.log_error(f"Timesheet {ts['name']} auto-submitted by '{ts['owner']}' using transition '{workflow_action}'", "Auto Submit Timesheet")
                    
                    # Reset user back to previous_user
                    frappe.set_user(previous_user)
                except Exception as e:
                    frappe.log_error(title="Error Submitting Timesheet", message=f"Error submitting Timesheet {ts.name}: {e}")

            #commit the db
            frappe.db.commit()
        
          
