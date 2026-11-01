#!/usr/bin/env python3
"""
update_timetable.py — High-Speed Timetable Pipeline Engine
Automates:
1. Faithful WhatsApp raw text parsing (clean dates, standardized times, faithful subjects)
2. Zero Sub-Batch Contamination: Never assumes Roll 38-56 or rewrites generic postings
3. Atomic synchronization into index.html (const N={...})
4. Documentation logging into TIMETABLE.md
5. Git commit & push to GitHub Pages
"""

import sys
import os
import re
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent
INDEX_HTML = DIR / "index.html"
MD_FILE = DIR / "TIMETABLE.md"

def normalize_time(t_raw):
    """Normalize raw time strings like '8-9am', '10am-1pm', '1-2 pm' to '8–9 am', '10 am–1 pm'."""
    t = t_raw.strip().lower()
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'[-–—to]+', '–', t)
    
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?(am|pm)?–(\d{1,2})(?::(\d{2}))?(am|pm)?$', t)
    if not m:
        return t_raw.strip()
    
    start_h, start_m, start_p, end_h, end_m, end_p = m.groups()
    if not end_p and not start_p:
        start_p = 'am'
        end_p = 'pm' if int(end_h) < int(start_h) or int(end_h) in [12, 1, 2, 3, 4, 5] else 'am'
    elif not end_p and start_p:
        end_p = start_p
    elif end_p and not start_p:
        if int(start_h) in [8, 9, 10, 11] and end_p == 'pm' and int(end_h) in [12, 1, 2, 3, 4, 5]:
            start_p = 'am'
        elif int(start_h) > int(end_h):
            start_p = 'am'
        else:
            start_p = end_p

    s_str = f"{start_h}" + (f":{start_m}" if start_m else "")
    if start_p != end_p:
        s_str += f" {start_p}"
    
    e_str = f"{end_h}" + (f":{end_m}" if end_m else "") + f" {end_p}"
    return f"{s_str}–{e_str}"

def parse_raw_message(raw_text):
    """Parse raw announcements faithfully without injecting sub-batch assumptions."""
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    full_text = "\n".join(lines)
    
    # Strip WhatsApp author prefix
    cleaned_lines = []
    for l in lines:
        l_clean = re.sub(r'^\[\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?,\s*[^\]]+\]\s*[^:]*:\s*', '', l)
        if l_clean:
            cleaned_lines.append(l_clean)
            
    # 1. Date Detection
    date_str = None
    dm = re.search(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b', full_text)
    if dm:
        d, m, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        if y < 100: y += 2000
        date_str = f"{y:04d}-{m:02d}-{d:02d}"
    elif "tomorrow" in full_text.lower():
        now = datetime.now()
        date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in full_text.lower():
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        
    if not date_str:
        now = datetime.now()
        date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        
    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt_obj.strftime("%A")

    # 2. Extract Time Slots and Subjects
    time_regex = re.compile(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b', re.IGNORECASE)
    
    slots = []
    i = 0
    while i < len(cleaned_lines):
        line = cleaned_lines[i]
        if re.search(r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b', line) and len(line) < 30:
            i += 1
            continue
            
        tm = time_regex.search(line)
        if tm:
            raw_time = tm.group(1)
            norm_time = normalize_time(raw_time)
            subj_parts = [line[:tm.start()].strip(), line[tm.end():].strip()]
            subj = " ".join([p for p in subj_parts if p]).strip(" :.-")
            
            j = i + 1
            extra_lines = []
            while j < len(cleaned_lines):
                if time_regex.search(cleaned_lines[j]):
                    break
                extra_lines.append(cleaned_lines[j])
                j += 1
                
            if extra_lines:
                extra_desc = " ".join(extra_lines).strip()
                if subj:
                    subj += " — " + extra_desc
                else:
                    subj = extra_desc
            
            slots.append((norm_time, subj))
            i = j
        else:
            i += 1

    # 3. Build Structured Entries (Faithful to Announcement)
    entries = []
    for norm_time, subj in slots:
        subj_clean = subj.strip()
        
        # If line is just "posting" or "10-1pm posting" without special instructions:
        # We check if index.html already handles dynamic posting.
        # But if we must include it in N, default to Roll 1-155 so we don't lock it to roll 38-56!
        min_roll = 1
        max_roll = 155
        
        # ONLY restrict roll numbers if explicitly specified in the message!
        rm = re.search(r'roll\s*(?:no\.?|nos\.?)?:?\s*(\d+)\s*[-–to]+\s*(\d+)', subj_clean, re.I)
        if rm:
            min_roll = int(rm.group(1))
            max_roll = int(rm.group(2))
        elif 'batch a' in subj_clean.lower():
            min_roll = 1
            max_roll = 37
        elif 'batch b' in subj_clean.lower():
            min_roll = 38
            max_roll = 75
        elif 'batch c' in subj_clean.lower():
            min_roll = 76
            max_roll = 111
        elif 'batch d' in subj_clean.lower():
            min_roll = 112
            max_roll = 155

        # Format generic posting cleanly without hallucinating department or OPD/OT
        if subj_clean.lower() in ['posting', 'postings', 'clinical posting', 'clinical postings', '']:
            # If the user's batch has specific dynamic posting built-in, 
            # we keep it as a clean entry for all roll numbers, OR let index.html resolve it.
            # In N, if specified, keep title clean:
            subj_clean = 'Clinical Posting'
            
        rs_flag = 0
        warn_words = ['rescheduled', 'postponed', 'online', 'google meet', 'gmeet', 'bring journal', 'strictly', 'read before', 'cancelled', 'hod sir']
        if any(w in subj_clean.lower() for w in warn_words):
            rs_flag = 1
            
        entries.append([min_roll, max_roll, norm_time, subj_clean, rs_flag])
        
    return date_str, day_name, entries

def update_html(date_str, entries):
    """Surgically update const N = {...} in index.html."""
    if not INDEX_HTML.exists():
        raise FileNotFoundError(f"{INDEX_HTML} not found.")
        
    content = INDEX_HTML.read_text(encoding="utf-8")
    
    entry_lines = []
    for e in entries:
        escaped_sub = e[3].replace("'", "\\'")
        entry_lines.append(f"  [{e[0]},{e[1]},'{e[2]}','{escaped_sub}',{e[4]}]")
    formatted_entry = f" '{date_str}':[\n" + ",\n".join(entry_lines) + "\n ]"
    
    date_pattern = re.compile(rf"('{date_str}':\s*\[[\s\S]*?\n \])(,?)")
    if date_pattern.search(content):
        content = date_pattern.sub(formatted_entry + r"\2", content)
    else:
        n_close = content.find("};\nfunction tt(")
        if n_close == -1: n_close = content.find("}; function tt(")
        if n_close == -1: n_close = content.find("};\n\nfunction tt(")
        
        last_bracket = content.rfind("]", 0, n_close)
        if last_bracket != -1:
            content = content[:last_bracket+1] + ",\n" + formatted_entry + content[last_bracket+1:]
        else:
            raise ValueError("Could not find insertion point inside const N={...} in index.html")
            
    INDEX_HTML.write_text(content, encoding="utf-8")
    print(f"✓ Updated {INDEX_HTML.name} for {date_str}")

def update_markdown(date_str, day_name, entries):
    """Log timetable entries into TIMETABLE.md."""
    if not MD_FILE.exists():
        return
        
    content = MD_FILE.read_text(encoding="utf-8")
    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_formatted = dt_obj.strftime("%d-%b-%Y")
    
    header = f"## 📅 Daily Timetable — {date_formatted} ({day_name}) ✅ Verified"
    items = []
    for e in entries:
        scope = f" (Roll {e[0]}–{e[1]})" if not (e[0] == 1 and e[1] == 155) else ""
        items.append(f"* **{e[2]}:** {e[3]}{scope}")
        
    block = f"{header}\n" + "\n".join(items) + "\n\n---\n\n"
    
    sec_pattern = re.compile(rf"## 📅 Daily Timetable — {re.escape(date_formatted)}[\s\S]*?---\n\n")
    if sec_pattern.search(content):
        content = sec_pattern.sub(block, content)
    else:
        marker = "## 📅 Daily Timetable — "
        pos = content.find(marker)
        if pos != -1:
            content = content[:pos] + block + content[pos:]
        else:
            content += "\n\n" + block
            
    MD_FILE.write_text(content, encoding="utf-8")
    print(f"✓ Updated {MD_FILE.name} for {date_formatted}")

def git_commit_and_push(date_str):
    """Commit changes and push to GitHub Pages."""
    cmd_add = ["git", "-C", str(DIR), "add", "index.html", "TIMETABLE.md"]
    cmd_commit = ["git", "-C", str(DIR), "commit", "-m", f"Update timetable for {date_str}"]
    cmd_push = ["git", "-C", str(DIR), "push", "origin", "main"]
    
    subprocess.run(cmd_add, check=True)
    res = subprocess.run(cmd_commit, capture_output=True, text=True)
    if "nothing to commit" in res.stdout:
        print("ℹ No changes detected to commit.")
        return
    subprocess.run(cmd_push, check=True)
    print("🚀 Pushed to GitHub! Live site updated.")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="High-Speed Timetable Pipeline Engine")
    parser.add_argument("--raw", type=str, help="Raw announcement text (e.g. from WhatsApp)")
    parser.add_argument("--json", type=str, help="Structured JSON timetable input")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    parser.add_argument("--dry-run", action="store_true", help="Preview parsed entries without writing")
    args = parser.parse_args()
    
    if args.json:
        data = json.loads(args.json)
        date_str = data["date"]
        dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = dt_obj.strftime("%A")
        entries = data["entries"]
    elif args.raw:
        date_str, day_name, entries = parse_raw_message(args.raw)
    else:
        print("Error: Either --raw or --json must be provided.")
        sys.exit(1)
        
    print(f"\n--- Parsed Timetable for {date_str} ({day_name}) ---")
    for e in entries:
        flag_str = " [HIGHLIGHT]" if e[4] else ""
        print(f"  Roll {e[0]}-{e[1]} | {e[2]:<12} | {e[3]}{flag_str}")
    print("--------------------------------------------------\n")
    
    if args.dry_run:
        print("Dry run requested. No files modified.")
        return
        
    update_html(date_str, entries)
    update_markdown(date_str, day_name, entries)
    
    if not args.no_push:
        git_commit_and_push(date_str)

if __name__ == "__main__":
    main()
