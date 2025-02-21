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
                    let showHeartbeatMap = r.message.show_heartbeat_map_on_timesheet;
                    let showSpareBlock = r.message.show_sparetime_between_activities_on_timesheet;
                    let showSummaryBlock = r.message.show_summary_on_timesheet;
                    
                    let heatmapData = r.message.heatmap_data;
                    let totalWorkingHours = r.message.total_working_hours || 0;
                    let totalNotWorkingHours = r.message.total_not_working_hours || 0;
                    let totalProductiveHours = r.message.total_productive_hours || 0;
                    let totalNonProductiveHours = r.message.total_non_productive_hours || 0;
        
                    let lastActivityEndTime = null;

                    if(showSummaryBlock){
                        // Calculate productivity percentage
                        let productivityPercentage = totalWorkingHours > 0 
                            ? ((totalProductiveHours / totalWorkingHours) * 100).toFixed(2) 
                            : 0;

                        let nonProductivityPercentage = totalWorkingHours > 0 
                            ? ((totalNonProductiveHours / totalWorkingHours) * 100).toFixed(2) 
                            : 0;
                        
                        let notWorkingPercentage = totalWorkingHours > 0 
                            ? ((totalNotWorkingHours / totalWorkingHours) * 100).toFixed(2)  
                            : 0;
                        
                        // Heatmap color scale
                        let productivityColor = "#4caf50";  // Green
                        let notWorkingColor = "#f44336";   // Red
                        let nonProductivityColor = "#ffc107";    // Yellow
                        
                        // Summary Block
                        let summaryBlock = $(`
                            <div class="summary-block">
                                <h3>Timesheet Summary</h3>
                            
                                <!-- Custom Productivity Heatmap -->
                                <div class="productivity-heatmap">
                                    <div class="progress-bar-1">
                                        <div class="progress-1 productive" style="width: ${productivityPercentage}%; background-color: ${productivityColor};"></div>
                                        <div class="progress-1 non-productive" style="width: ${nonProductivityPercentage}%; background-color: ${nonProductivityColor};"></div>
                                        <div class="progress-1 not-working" style="width: ${notWorkingPercentage}%; background-color: ${notWorkingColor};"></div>
                                    </div>
                                    <div class="legend">
                                        <span><span class="legend-box" style="background-color: ${productivityColor};"></span> Productive ${productivityPercentage}%</span>
                                        <span><span class="legend-box" style="background-color: ${nonProductivityColor};"></span> Non-Productive ${nonProductivityPercentage}%</span>
                                        <span><span class="legend-box" style="background-color: ${notWorkingColor};"></span> Non-Working ${notWorkingPercentage}%</span>
                                    </div>
                                </div>
                            </div>
                        `);
                        
                        container.append(summaryBlock);
                    }
                    

                    // Function to format time in HH:mm format
                    function formatTime(durationInMinutes) {
                        let hours = Math.floor(durationInMinutes / 60);
                        let minutes = durationInMinutes % 60;
                        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
                    }
        
                    // Generate HTML for each activity
                    heatmapData.forEach((activity, index) => {

                        // Check for spare time between activities
                        if (lastActivityEndTime && activity.from_time) {
                            let gapStart = lastActivityEndTime;
                            let gapEnd = activity.from_time;

                            if (gapStart < gapEnd) {
                                let spareTimeDuration = moment(gapEnd, "HH:mm").diff(moment(gapStart, "HH:mm"), 'minutes');
                                let spareTimeFormatted = formatTime(spareTimeDuration);

                                if (showSpareBlock && spareTimeDuration > 5) {
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
                                    ${showHeartbeatMap && activity.minutes && activity.minutes.length > 0 ? 
                                        activity.minutes.map(min => `
                                            <div 
                                                class="minute ${min.status}" 
                                                title="${min.time}: ${min.status === 'working' ? 'Working' : min.status === 'non-productive' ? 'Non-Productive' : 'Not Working'}"
                                                style="background-color: ${min.color};"
                                            ></div>
                                        `).join('') : ``}
                                </div>
                            </div>
                        `);

                        container.append(activityBlock);
                        lastActivityEndTime = activity.to_time;
                    });

                } else {
                    container.append(`<p>No time logs available for this Timesheet.</p>`);
                }
            }
        });              
        
    }
});
