/**
 * Google Apps Script for TNMC Timetable — 155-Student Multi-User Engine
 * ----------------------------------------------------------------------
 * Supports all 155 MBBS Batch 2024 students concurrently without collisions.
 * 
 * 1. Open your Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Replace all code with this file.
 * 4. Deploy > Manage deployments > Edit > New version:
 *    - Execute as: 'Me'
 *    - Who has access: 'Anyone'  <-- CRITICAL: Must be 'Anyone' to prevent 403 Forbidden!
 * 5. Click 'Deploy'.
 */

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : 'health';
  var roll = (e && e.parameter && e.parameter.roll) ? String(e.parameter.roll) : null;
  
  if (action === 'get') {
    if (!roll) {
      return respondJson({ status: 'error', message: 'Roll number required' });
    }
    
    var raw = PropertiesService.getScriptProperties().getProperty('tnmc_absences_roll_' + roll);
    var updatedAt = PropertiesService.getScriptProperties().getProperty('tnmc_updated_roll_' + roll);
    
    return respondJson({
      status: 'success',
      roll: parseInt(roll, 10),
      updatedAt: updatedAt || null,
      absences: raw ? JSON.parse(raw) : {}
    });
  }
  
  return respondJson({
    status: 'ok',
    message: 'TNMC Batch 2024 Multi-User Attendance API is active. Ready for 155 students.'
  });
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return respondJson({ status: 'error', message: 'No POST data' });
    }
    
    var data = JSON.parse(e.postData.contents);
    var roll = data.roll ? parseInt(data.roll, 10) : null;
    
    if (!roll || roll < 1 || roll > 155) {
      return respondJson({ status: 'error', message: 'Valid roll number (1-155) required' });
    }
    
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var now = new Date();
    var timeStr = Utilities.formatDate(now, "Asia/Kolkata", "dd-MMM-yyyy, hh:mm:ss a 'IST'");
    var rollKey = String(roll);
    
    // 1. Save student-specific absence state in ScriptProperties
    if (data.absences) {
      PropertiesService.getScriptProperties().setProperty('tnmc_absences_roll_' + rollKey, JSON.stringify(data.absences));
      PropertiesService.getScriptProperties().setProperty('tnmc_updated_roll_' + rollKey, timeStr);
    }
    
    // 2. Determine Batch (A: 1-37, B: 38-75, C: 76-111, D: 112-155)
    var batch = "A";
    if (roll >= 38 && roll <= 75) batch = "B";
    else if (roll >= 76 && roll <= 111) batch = "C";
    else if (roll >= 112 && roll <= 155) batch = "D";
    
    // 3. Update Master Sheet: "Batch Roster (1-155)"
    var rosterSheet = ss.getSheetByName("Batch Roster (1-155)");
    if (!rosterSheet) {
      rosterSheet = ss.insertSheet("Batch Roster (1-155)");
      var headers = ["Roll No", "Batch", "Theory Attended", "Theory Conducted", "Theory %", "Posting Attended", "Posting Conducted", "Posting %", "Theory Cushion", "Posting Cushion", "Last Synced (IST)"];
      rosterSheet.getRange(1, 1, 1, headers.length).setValues([headers])
        .setFontWeight("bold").setBackground("#1d4ed8").setFontColor("#ffffff");
      rosterSheet.setFrozenRows(1);
      
      // Pre-seed 155 rows
      var initRows = [];
      for (var r = 1; r <= 155; r++) {
        var b = (r <= 37) ? "A" : (r <= 75 ? "B" : (r <= 111 ? "C" : "D"));
        initRows.push([r, b, "--", "--", "--", "--", "--", "--", "--", "--", "Never"]);
      }
      rosterSheet.getRange(2, 1, 155, headers.length).setValues(initRows);
      rosterSheet.autoResizeColumns(1, headers.length);
    }
    
    var stats = data.stats || {};
    var rowIndex = roll + 1; // row 1 is header, row 2 is Roll 1
    
    var thPctStr = stats.thPct !== undefined ? stats.thPct.toFixed(1) + "%" : "--";
    var prPctStr = stats.prPct !== undefined ? stats.prPct.toFixed(1) + "%" : "--";
    
    var studentRow = [
      roll,
      batch,
      stats.thAtt !== undefined ? stats.thAtt : "--",
      stats.thTot !== undefined ? stats.thTot : "--",
      thPctStr,
      stats.prAtt !== undefined ? stats.prAtt : "--",
      stats.prTot !== undefined ? stats.prTot : "--",
      prPctStr,
      stats.thCushion || "--",
      stats.prCushion || "--",
      timeStr
    ];
    
    rosterSheet.getRange(rowIndex, 1, 1, studentRow.length).setValues([studentRow]);
    
    // 4. Append to "Live Absence Feed"
    var feedSheet = ss.getSheetByName("Live Absence Feed");
    if (!feedSheet) {
      feedSheet = ss.insertSheet("Live Absence Feed");
      var feedHeaders = ["Logged At (IST)", "Roll No", "Batch", "Class Date", "Class Slot", "Subject / Posting", "Type"];
      feedSheet.getRange(1, 1, 1, feedHeaders.length).setValues([feedHeaders])
        .setFontWeight("bold").setBackground("#c2410c").setFontColor("#ffffff");
      feedSheet.setFrozenRows(1);
    }
    
    var absencesList = data.absenceDetails || [];
    if (absencesList.length > 0) {
      var feedRows = absencesList.map(function(item) {
        return [timeStr, roll, batch, item.date, item.time, item.subject, item.type];
      });
      feedSheet.getRange(feedSheet.getLastRow() + 1, 1, feedRows.length, feedHeaders.length).setValues(feedRows);
    }
    
    return respondJson({
      status: 'success',
      roll: roll,
      message: 'Synced successfully for Roll #' + roll,
      updatedAt: timeStr
    });
    
  } catch (err) {
    return respondJson({
      status: 'error',
      message: err.toString()
    });
  }
}

function respondJson(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
