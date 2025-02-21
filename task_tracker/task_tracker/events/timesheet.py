import frappe
from frappe import _
from frappe.utils import now
import json
from task_tracker.task_tracker.utils import get_heatmap_data

def before_submit(doc, method):
    heatmap_data = get_heatmap_data(doc.name)
    data = {
        "heatmap_data": heatmap_data.get("heatmap_data"),
        "total_working_hours": heatmap_data.get("total_working_hours"),
        "total_not_working_hours": heatmap_data.get("total_not_working_hours"),
        "total_productive_hours": heatmap_data.get("total_productive_hours"),
        "total_non_productive_hours": heatmap_data.get("total_non_productive_hours")
    }
    doc.custom_heatmap_data = json.dumps(data)