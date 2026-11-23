# 🛠️ Hardened Timetable Update Workflow (`timetable/WORKFLOW.md`)
*Protocol: Foolproof Timetable Extraction, Synchronization, and Deployment*

---

## 🛑 Why It Failed Previously (Root Cause Autopsy)

1. **Content Truncation vs Verbatim Reality:**
   - *Error:* AI paraphrased or truncated syllabus topics (e.g. writing "Health Care Delivery System & PHC" instead of "Concept of Health Care Delivery System in India and Primary Health Care [CM 17.3, CM 17.5]").
   - *Fix:* Topics must match official department source documents and CR announcements **100% verbatim**. No abbreviations. No summaries.

2. **Meta-Commentary Contamination:**
   - *Error:* WhatsApp advisory chatter ("everybody marked present", "read and come") was injected into official timetable rows.
   - *Fix:* Strict timetable schema: **Subject, Time, Venue, and Topic ONLY**. Tactical advice belongs exclusively in `todays_plan.txt` or chat, NEVER inside timetable entries.

3. **The Blogger Iframe & Edge CDN Latency Illusion:**
   - *The Trap:* Pushing git commit succeeds instantly, but:
     1. **Fastly/Varnish CDN Edge Lock:** GitHub Pages assets have `Cache-Control: max-age=600` (10-minute cache window). Edge servers (like `cache-bom` in Mumbai) serve the cached copy until TTL expires.
     2. **Mobile Chrome Iframe Disk Caching:** `rooohan.blogspot.com` embeds `domainexapnsion.github.io/timetable/` in a full-screen iframe. On mobile Chrome, swiping down to refresh the Blogger page **only reloads the outer Blogger HTML wrapper**—Chrome serves the iframe directly from its internal disk cache!
   - *Fix:*
     - Keep `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">` in `index.html`.
     - Direct user to pull-down refresh on the standalone URL (`https://domainexapnsion.github.io/timetable/`) or use Incognito to overwrite mobile Chrome's iframe disk cache.

---

## ⚡ Step-by-Step Execution Protocol

### Step 1: Ingest & Extract Verbatim Topics
* Extract from source document (Excel, Word docx, PDF, or WhatsApp CR notice).
* Retain the full, unshortened competency and syllabus text word-for-word.

### Step 2: Format Clean Timetable Rows
* Format entry strictly as:
  `[min_roll, max_roll, 'time_str', 'Subject: Exact Verbatim Topic (Venue/Faculty)', rs_flag]`
* Zero chat chatter, zero advisory notes.

### Step 3: Atomic Dual-File Sync
* Update `const N = { ... }` in `index.html`.
* Update daily log and master department section in `TIMETABLE.md`.
* Sync topics into `Master Documents/todays_plan.txt`.

### Step 4: Commit, Push & Verify
* Git commit with explicit message and push to `origin/main`.
* Run headless curl verification:
  ```bash
  curl -s "https://domainexapnsion.github.io/timetable/" | grep -A 8 "'YYYY-MM-DD':"
  ```
* If mobile user reports viewing stale version on Blogger:
  - Check CDN edge age via `curl -I -s "https://domainexapnsion.github.io/timetable/" | grep age`.
  - Provide direct link for one-tap hard refresh: `https://domainexapnsion.github.io/timetable/`.
