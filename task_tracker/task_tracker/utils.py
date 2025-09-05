import frappe
from io import BytesIO
from PIL import Image
import pytesseract
import numpy as np
import cv2
import json
from transformers import pipeline
from huggingface_hub import InferenceClient
import datetime
from frappe.utils import get_datetime, now_datetime


@frappe.whitelist()
def get_heatmap_data(timesheet):
    """
    Fetch time logs and heartbeats for a Timesheet to create a custom heatmap.
    """
    try:
        doc = frappe.get_doc("Timesheet", timesheet)
    except Exception as e:
        frappe.throw(f"Error fetching Timesheet: {e}")

    heatmap_data = []
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")
    
    total_working_hours = 0
    total_not_working_hours = 0
    total_productive_hours = 0
    total_non_productive_hours = 0
    
    if (doc.custom_heatmap_data and doc.docstatus != 0):
        json_data = json.loads(doc.custom_heatmap_data)
        heatmap_data = json_data.get("heatmap_data")
        total_working_hours = json_data.get("total_working_hours")
        total_not_working_hours = json_data.get("total_not_working_hours")
        total_productive_hours = json_data.get("total_productive_hours")
        total_non_productive_hours = json_data.get("total_non_productive_hours")
    else:
        # Set default heartbeat interval to 1 minute if missing or 0
        heartbeat_interval = doc.custom_heartbeat_interval if getattr(doc, "custom_heartbeat_interval", 0) else 1  

        # Fetch time logs
        time_logs = [log for log in doc.get("time_logs", []) if log.get("from_time") and log.get("to_time")]
        if not time_logs:
            return {
                "heatmap_data": [],
                "total_working_hours": total_working_hours,
                "total_not_working_hours": total_not_working_hours,
                "total_productive_hours": total_productive_hours,
                "total_non_productive_hours": total_non_productive_hours,
                "show_heartbeat_map_on_timesheet": task_tracker_settings.show_heartbeat_map_on_timesheet,
                "show_sparetime_between_activities_on_timesheet": task_tracker_settings.show_sparetime_between_activities_on_timesheet,
                "show_summary_on_timesheet": task_tracker_settings.show_summary_on_timesheet
            }

        allowed_users = [u.strip() for u in task_tracker_settings.show_screenshots_on_heartbeat_map.split(",")]
        is_allowed_role = frappe.session.user in allowed_users
        
        allowed_users_reason = [u.strip() for u in task_tracker_settings.show_reason_on_heartbeat_map.split(",")]
        is_allowed_role_reason = frappe.session.user in allowed_users_reason


        # Fetch heartbeats with productivity_flag
        heartbeats = frappe.get_all(
            "Timesheet Heartbeat",
            filters={"timesheet": timesheet},
            fields=["name", "creation", "productivity_flag", "productivity_reason"]
        )

        # Get all attachments for these heartbeats
        heartbeat_names = [hb.name for hb in heartbeats]
        attachments = frappe.get_all(
            "File",
            filters={"attached_to_doctype": "Timesheet Heartbeat", "attached_to_name": ["in", heartbeat_names]},
            fields=["attached_to_name", "file_url"]
        )

        # Map attachments by heartbeat name
        attachments_map = {}
        for att in attachments:
            if att.attached_to_name not in attachments_map:
                attachments_map[att.attached_to_name] = []
            attachments_map[att.attached_to_name].append(att.file_url)

        # Store heartbeats with their status
        heartbeat_data = {
            get_datetime(hb.creation).strftime("%Y-%m-%d %H:%M"): {
                "flag": hb.productivity_flag,
                "reason": hb.productivity_reason,
                "screenshots": attachments_map.get(hb.name, [])
            }
            for hb in heartbeats
        }

        # Process data for each time log
        for log in time_logs:
            from_time = get_datetime(log.from_time)
            to_time = get_datetime(log.to_time)
            duration_minutes = (to_time - from_time).total_seconds() / 60

            activity_data = {
                "activity": log.activity_type,
                "project": log.project_name,
                "description": log.description,
                "from_time": from_time.strftime("%H:%M"),
                "to_time": to_time.strftime("%H:%M"),
                "hours": round(log.hours, 2),
                "hours_category": log.hours_category,
                "minutes": []
            }

            current_time = from_time
            working_minutes = 0
            not_working_minutes = 0
            productive_minutes = 0
            non_productive_minutes = 0
            
            isEnd = False
            while current_time <= to_time and not isEnd:
                time_str = current_time.strftime("%Y-%m-%d %H:%M")
                heartbeat_entry = heartbeat_data.get(time_str, None)

                if heartbeat_entry:
                    productivity_flag = heartbeat_entry["flag"]
                    productivity_reason = heartbeat_entry.get("reason", "") if is_allowed_role_reason else ""
                    # Show screenshots only if System Manager
                    screenshot_links = heartbeat_entry.get("screenshots", []) if is_allowed_role else []

                    if productivity_flag == "non-productive":
                        color = "#FFA500"  # Yellowish Orange (Non-Productive)
                        status = "non-productive"
                        non_productive_minutes += heartbeat_interval
                    else:
                        color = "#008000"  # Green (Productive)
                        status = "working"
                        productive_minutes += heartbeat_interval
                else:
                    color = "#FF0000"  # Red (No heartbeat recorded)
                    status = "not_working"
                    screenshot_links = []
                    productivity_reason = ""
                    not_working_minutes += heartbeat_interval

                minute_data = {
                    "time": current_time.strftime("%H:%M"),
                    "status": status,
                    "color": color,
                }
                if screenshot_links:
                    minute_data["screenshots"] = screenshot_links
                if productivity_reason:
                    minute_data["reason"] = productivity_reason

                activity_data["minutes"].append(minute_data)

                if(current_time == to_time):
                    isEnd = True
                
                if (
                    (current_time + datetime.timedelta(minutes=heartbeat_interval) > to_time)
                    and current_time.strftime("%H:%M") != to_time.strftime("%H:%M")
                    ):
                    current_time = to_time
                else:
                    current_time += datetime.timedelta(minutes=heartbeat_interval)  # Use custom heartbeat interval

            total_working_hours += (productive_minutes + non_productive_minutes + not_working_minutes)
            total_not_working_hours += not_working_minutes
            total_productive_hours += productive_minutes
            total_non_productive_hours += non_productive_minutes

            heatmap_data.append(activity_data)

        total_working_hours = round(total_working_hours/60, 2)
        total_not_working_hours = round(total_not_working_hours/60, 2)
        total_productive_hours = round(total_productive_hours/60, 2)
        total_non_productive_hours = round(total_non_productive_hours/60, 2)

    return {
        "heatmap_data": heatmap_data,
        "total_working_hours": total_working_hours,
        "total_not_working_hours": total_not_working_hours,
        "total_productive_hours": total_productive_hours,
        "total_non_productive_hours": total_non_productive_hours,
        "show_heartbeat_map_on_timesheet": task_tracker_settings.show_heartbeat_map_on_timesheet,
        "show_sparetime_between_activities_on_timesheet": task_tracker_settings.show_sparetime_between_activities_on_timesheet,
        "show_summary_on_timesheet": task_tracker_settings.show_summary_on_timesheet
    }



def analyze_image(image_path, job_description=None):
    return classify_productivity(extract_text_from_screenshot(image_path), job_description)


def extract_text_from_screenshot(image_path):
    file_path = frappe.get_site_path(image_path)
    img = cv2.imread(file_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Perform OCR
    text = pytesseract.image_to_string(gray)
    return text.strip()

def classify_productivity(text, job_description):
    if not text:
        return "Uncertain (No Text Detected)"
    JD = ""
    if job_description:
        JD = f" with this Job Description: {job_description}"
    
    task_tracker_settings = frappe.get_doc("Task Tracker Settings")

    hf_api_token = task_tracker_settings.hugging_face_api_token 
    client = InferenceClient(api_key=hf_api_token)

    # Define the prompt for the classification task
    messages = [
        {"role": "user", "content": f"analyze this as productive or non-productive (productive means office working and non-productive means using social media, watching videos and playing games) in office work environment{JD}, response should contain a json object with 2 objects status and message:\n\n{text}"}
    ]

    completion = client.chat.completions.create(
        model=task_tracker_settings.hugging_face_model, 
        messages=messages,
        max_tokens=500
    )
    
    return completion.choices[0].message.content




