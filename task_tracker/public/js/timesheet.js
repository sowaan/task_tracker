frappe.ui.form.on('Timesheet', {
    refresh: function (frm) {
        

        let container = $(frm.fields_dict.custom_chart.wrapper);
        container.empty();

        // Fetch the heatmap data
        frappe.call({
            method: 'task_tracker.task_tracker.utils.get_heatmap_data',
            args: { timesheet: frm.doc.name },
            callback: function(r) {
                if (r.message) {
                    // console.log("Received heatmap data:", r.message);
                    
                    let showHeartbeatMap = r.message.show_heartbeat_map_on_timesheet
                    let showSpareBlock = r.message.show_sparetime_between_activities_on_timesheet
                    // Extract heatmap data from the response
                    let heatmapData = r.message.heatmap_data;
        
                    let lastActivityEndTime = null;
        
                    // Function to format time in HH:mm format
                    function formatTime(durationInMinutes) {
                        let hours = Math.floor(durationInMinutes / 60);
                        let minutes = durationInMinutes % 60;
                        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
                    }
        
                    // Generate HTML for each activity separately
                    heatmapData.forEach((activity, index) => {
        
                        // Check for spare time between the current activity and the next activity
                        if (lastActivityEndTime && activity.from_time) {
                            // Calculate the gap (spare time) between activities
                            let gapStart = lastActivityEndTime;
                            let gapEnd = activity.from_time;
        
                            if (gapStart < gapEnd) {
                                // Calculate spare time duration in minutes
                                let spareTimeDuration = moment(gapEnd, "HH:mm").diff(moment(gapStart, "HH:mm"), 'minutes');
                                let spareTimeFormatted = formatTime(spareTimeDuration); // Format spare time
                                
                                if(showSpareBlock && spareTimeDuration > 5) //ignore up to 5 minutes
                                {
                                    let spareTimeBlock = $(`
                                        <div class="activity-block spare-time-block">
                                            <div class="activity-header">
                                                <h4>Spare Time</h4>
                                                <span class="activity-time">${gapStart} - ${gapEnd}</span>
                                            </div>
            
                                            <div class="activity-details">
                                                <p><strong>Duration:</strong> ${spareTimeFormatted}</p>
                                            </div>
                                        </div>
                                    `);
                                    container.append(spareTimeBlock);
                                }
                            }
                        }
        
                        let activityBlock = $(`
                            <div class="activity-block ${activity.hours_category}">
                                <div class="activity-header">
                                    <h4>${activity.description}</h4>
                                    <span class="activity-time">${activity.from_time} - ${activity.to_time}</span>
                                </div>
        
                                <div class="activity-details">
                                    <p><strong>Project:</strong> ${activity.project || "N/A"}</p>
                                    <p><strong>Hours Category:</strong> ${activity.hours_category || "N/A"}</p>
                                    <p><strong>Total Hours:</strong> ${activity.hours || 0} hours</p>
                                </div>
        
                                <div class="heatmap">
                                    ${showHeartbeatMap && activity.minutes && activity.minutes.length > 0 ? activity.minutes.map(min => `
                                        <div 
                                            class="minute ${min.status}" 
                                            title="${min.time}: ${min.status === 'working' ? 'Working' : min.status === 'non-productive' ? 'Non-Productive' : 'Not Working'}"
                                            style="background-color: ${min.color};"
                                        ></div>
                                    `).join('') : ``}
                                </div>
                            </div>
                        `);
        
                        // Append the activity block to the container
                        container.append(activityBlock);
        
                        // Update the last activity end time to the current activity's end time
                        lastActivityEndTime = activity.to_time;
                    });
        
                } else {
                    container.append(`<p>No time logs available for this Timesheet.</p>`);
                }
            }
        });        
        
        
    }
});
