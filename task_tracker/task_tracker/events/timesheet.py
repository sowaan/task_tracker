import frappe
from frappe import _
from frappe.utils import now
import json
from task_tracker.task_tracker.utils import get_heatmap_data

def validate(doc, method):
    heatmap_data = get_heatmap_data(doc.name).get("heatmap_data")
    doc.custom_heatmap_data = json.dumps(heatmap_data)