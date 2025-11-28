import os
import json
import datetime
import glob
import argparse

# --- CONFIGURATION ---
DEFAULT_JSON_DIR = "/Users/valerii/Documents/Documents/02_responsibilities/22_work/22.1 — катя пащенко — обработка неструктурированных источников /md/json"
DEFAULT_OUTPUT_FILE = "/Users/valerii/Documents/Documents/02_responsibilities/22_work/22.1 — катя пащенко — обработка неструктурированных источников /md/tufte_timeline.html"

def generate_tufte_html(all_entities, all_events, all_topics, output_path):
    # 1. Prepare Data for Client-Side
    events = sorted(all_events, key=lambda x: x["date"])
    
    # Helper to normalize names
    def normalize_name(name):
        if not name: return ""
        if "(" in name:
            return name.split("(")[0].strip()
        return name.strip()

    # Deduplicate entities and assign groups
    unique_entities = {}
    for e in all_entities:
        norm_name = normalize_name(e['name'])
        if norm_name:
            if norm_name not in unique_entities or unique_entities[norm_name] == 'Other':
                unique_entities[norm_name] = e.get('group', 'Other')
    
    # Filter entities: Keep only those involved in connections
    connected_names = set()
    valid_events = []
    
    # Date parsing for Python side just to filter invalid dates
    def parse_date(date_str):
        clean_date = date_str.split(' ')[0].split('/')[0]
        try:
            return datetime.datetime.strptime(clean_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return None

    for e in events:
        d = parse_date(e["date"])
        if d:
            e["date"] = d # Normalize date format
            valid_events.append(e)
            a = normalize_name(e.get("actor"))
            t = normalize_name(e.get("target"))
            if a and t and a != t:
                connected_names.add(a)
                connected_names.add(t)
            elif a:
                connected_names.add(a) # Keep solo actors too? Yes, for solo events.

    # Re-build sorted_entities
    sorted_entities = sorted(
        [(k, v) for k, v in unique_entities.items() if k in connected_names],
        key=lambda x: x[1]
    )

    # Serialize Data
    json_events = json.dumps(valid_events, ensure_ascii=False)
    json_entities = json.dumps([{"name": k, "group": v} for k, v in sorted_entities], ensure_ascii=False)
    json_topics = json.dumps(sorted(list(all_topics)), ensure_ascii=False)

    # HTML Template with Client-Side Rendering
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Georgia, serif; background: #fdfdfd; color: #111; padding: 0; margin: 0; overflow: hidden; }}
            
            /* Top Control Bar */
            .controls-bar {{
                position: absolute; top: 0; left: 0; right: 0; height: 50px;
                background: #fff; border-bottom: 1px solid #eee;
                padding: 0 40px; z-index: 1000;
                display: flex; align-items: center; gap: 20px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            }}
            
            .controls-title {{ font-size: 20px; font-weight: bold; margin-right: 20px; }}
            
            /* Dropdown Styles */
            .dropdown {{ position: relative; display: inline-block; }}
            
            .dropdown-button {{
                background-color: #f9f9f9; color: #333; padding: 8px 14px;
                font-family: Georgia, serif; font-size: 14px;
                border: 1px solid #ccc; cursor: pointer; border-radius: 4px;
                min-width: 160px; text-align: left;
            }}
            
            .dropdown-button:hover {{ background-color: #f1f1f1; }}
            
            .dropdown-content {{
                display: none; position: absolute; background-color: #fff;
                min-width: 350px; max-height: 500px; overflow-y: auto;
                box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2); z-index: 1001;
                border: 1px solid #ddd; padding: 10px; border-radius: 4px;
            }}
            
            .dropdown-content label {{
                display: block; padding: 8px; cursor: pointer; font-size: 14px;
                border-bottom: 1px solid #f5f5f5;
            }}
            
            .dropdown-content label:hover {{ background-color: #f9f9f9; }}
            
            .show {{ display: block; }}
            
            .reset-btn {{
                padding: 8px 14px; background: #fff; border: 1px solid #ccc;
                cursor: pointer; font-family: Georgia, serif; font-size: 14px;
                border-radius: 4px; margin-left: auto;
            }}
            .reset-btn:hover {{ background: #f1f1f1; }}

            /* Timeline Container */
            #timeline-container {{
                position: absolute; top: 51px; left: 0; right: 0; bottom: 0;
                overflow: hidden; cursor: grab;
            }}
            #timeline-container:active {{ cursor: grabbing; }}
            
            svg {{ display: block; width: 100%; height: 100%; }}
            
            .axis-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #555; font-weight: bold; }}
            .axis-line {{ stroke: #ddd; stroke-width: 1; }}
            .swimlane-line {{ stroke: #eee; stroke-width: 1; }}
            .swimlane-text {{ font-family: Georgia, serif; font-size: 14px; fill: #222; }}
            .group-text {{ font-family: Georgia, serif; font-weight: bold; fill: #111; font-size: 16px; }}
            
            .event-line {{ stroke: #888; stroke-width: 0.5; stroke-dasharray: 4; }}
            .event-marker {{ cursor: pointer; transition: r 0.1s; }}
            .event-marker:hover {{ r: 9 !important; }}
            
            .tooltip {{
                position: absolute; background: #fff; border: 1px solid #ccc; padding: 12px;
                font-size: 14px; box-shadow: 2px 2px 8px rgba(0,0,0,0.15); pointer-events: none;
                opacity: 0; transition: opacity 0.2s; font-family: sans-serif; max-width: 300px; z-index: 2000;
                line-height: 1.4;
            }}
        </style>
    </head>
    <body>
        <div class="controls-bar">
            <div class="controls-title">Хронология</div>
            
            <div class="dropdown">
                <button onclick="toggleDropdown('topics-dropdown')" class="dropdown-button" id="topics-btn">Темы (0/5)</button>
                <div id="topics-dropdown" class="dropdown-content"></div>
            </div>
            
            <div class="dropdown">
                <button onclick="toggleDropdown('participants-dropdown')" class="dropdown-button" id="participants-btn">Участники (0/5)</button>
                <div id="participants-dropdown" class="dropdown-content"></div>
            </div>
            
            <button onclick="resetFilters()" class="reset-btn">Сбросить фильтры</button>
        </div>
        
        <div id="timeline-container">
            <svg id="timeline-svg"></svg>
        </div>
        <div id="tooltip" class="tooltip"></div>

        <script>
            // --- DATA INJECTION ---
            const RAW_EVENTS = {json_events};
            const RAW_ENTITIES = {json_entities};
            const TOPICS = {json_topics};
            
            // --- STATE ---
            let state = {{
                scale: 1, // Pixels per day (base)
                offsetX: 50, // Initial padding
                offsetY: 0, // Vertical scroll
                width: window.innerWidth,
                height: window.innerHeight - 50,
                minDate: null,
                maxDate: null,
                selectedTopics: [],
                selectedParticipants: [],
                filteredEvents: [],
                filteredEntities: [],
                yMap: {{}} // Map name -> y coord
            }};

            const MARGIN_LEFT = 280; // Increased for larger font
            const MARGIN_TOP = 60;
            const ROW_HEIGHT = 35; // Increased for larger font
            
            // --- INITIALIZATION ---
            function init() {{
                // Parse dates
                RAW_EVENTS.forEach(e => {{
                    e.parsedDate = new Date(e.date);
                    e.timestamp = e.parsedDate.getTime();
                }});
                
                // Find range
                const timestamps = RAW_EVENTS.map(e => e.timestamp);
                state.minDate = Math.min(...timestamps);
                state.maxDate = Math.max(...timestamps);
                
                // Initial Scale: Fit all events in width
                const daysSpan = (state.maxDate - state.minDate) / (1000 * 60 * 60 * 24);
                state.scale = (state.width - MARGIN_LEFT - 100) / daysSpan;
                if (state.scale < 0.5) state.scale = 0.5; // Min scale
                
                // Populate Filters
                populateFilters();
                
                // Initial Filter Apply
                applyFilters();
                
                // Setup Events
                setupInteractions();
                
                // Render
                requestAnimationFrame(render);
            }}

            function populateFilters() {{
                const tContainer = document.getElementById('topics-dropdown');
                TOPICS.forEach(t => {{
                    const lbl = document.createElement('label');
                    lbl.innerHTML = `<input type="checkbox" value="${{t}}"> ${{t}}`;
                    lbl.querySelector('input').addEventListener('change', onFilterChange);
                    tContainer.appendChild(lbl);
                }});
                
                const pContainer = document.getElementById('participants-dropdown');
                RAW_ENTITIES.sort((a,b) => a.name.localeCompare(b.name)).forEach(p => {{
                    const lbl = document.createElement('label');
                    lbl.innerHTML = `<input type="checkbox" value="${{p.name}}"> ${{p.name}}`;
                    lbl.querySelector('input').addEventListener('change', onFilterChange);
                    pContainer.appendChild(lbl);
                }});
            }}

            function onFilterChange() {{
                const tChecks = document.querySelectorAll('#topics-dropdown input:checked');
                const pChecks = document.querySelectorAll('#participants-dropdown input:checked');
                
                if (tChecks.length > 5) {{
                    alert("Максимум 5 тем");
                    this.checked = false;
                    return;
                }}
                if (pChecks.length > 5) {{
                    alert("Максимум 5 участников");
                    this.checked = false;
                    return;
                }}
                
                state.selectedTopics = Array.from(tChecks).map(c => c.value);
                state.selectedParticipants = Array.from(pChecks).map(c => c.value);
                
                document.getElementById('topics-btn').innerText = `Темы (${{state.selectedTopics.length}}/5)`;
                document.getElementById('participants-btn').innerText = `Участники (${{state.selectedParticipants.length}}/5)`;
                
                applyFilters();
                requestAnimationFrame(render);
            }}
            
            function applyFilters() {{
                // 1. Filter Events FIRST
                // Logic: Show event if it matches Topic OR Participant filter.
                // If both filters are active, event must match Topic AND Participant criteria?
                // Usually "Filter by Topic" AND "Filter by Participant" implies intersection.
                // But user wants "Show all interactions involved".
                
                state.filteredEvents = RAW_EVENTS.filter(e => {{
                    // Topic Filter
                    let topicMatch = true;
                    if (state.selectedTopics.length > 0) {{
                        const evtTopics = e.topics || [];
                        topicMatch = evtTopics.some(t => state.selectedTopics.includes(t));
                    }}
                    
                    // Participant Filter
                    let participantMatch = true;
                    if (state.selectedParticipants.length > 0) {{
                        const a = normalize(e.actor);
                        const t = normalize(e.target);
                        // Show event if ANY participant is selected (so we see their interactions)
                        participantMatch = state.selectedParticipants.includes(a) || state.selectedParticipants.includes(t);
                    }}
                    
                    return topicMatch && participantMatch;
                }});

                // 2. Derive Entities from Filtered Events
                // We only show entities that are part of the filtered events.
                // This ensures that if we select "Participant A", we see A and B (if they interact).
                // And if we select "Topic X", we see only participants in Topic X.
                
                const activeNames = new Set();
                
                // If NO filters are selected, show ALL entities
                if (state.selectedTopics.length === 0 && state.selectedParticipants.length === 0) {{
                    RAW_ENTITIES.forEach(e => activeNames.add(e.name));
                }} else {{
                    // Otherwise, derive from events
                    state.filteredEvents.forEach(e => {{
                        const a = normalize(e.actor);
                        const t = normalize(e.target);
                        if (a) activeNames.add(a);
                        if (t) activeNames.add(t);
                    }});
                }}
                
                state.filteredEntities = RAW_ENTITIES.filter(e => activeNames.has(e.name));
                
                // Calculate Y positions
                state.yMap = {{}};
                let currentY = MARGIN_TOP;
                let currentGroup = null;
                
                // Sort by group then name
                state.filteredEntities.sort((a,b) => {{
                    if (a.group !== b.group) return a.group.localeCompare(b.group);
                    return a.name.localeCompare(b.name);
                }});
                
                state.filteredEntities.forEach(e => {{
                    if (e.group !== currentGroup) {{
                        currentY += 25;
                        e.isGroupHeader = true; 
                        currentY += 20;
                        currentGroup = e.group;
                    }}
                    state.yMap[e.name] = currentY;
                    e.y = currentY;
                    currentY += ROW_HEIGHT;
                }});
                state.totalHeight = currentY + 50;
            }}
            
            function normalize(name) {{
                if (!name) return "";
                if (name.includes("(")) return name.split("(")[0].trim();
                return name.trim();
            }}

            // --- RENDERING ---
            function render() {{
                const svg = document.getElementById('timeline-svg');
                svg.innerHTML = ''; // Clear
                
                // 1. Draw Swimlanes (Background)
                drawSwimlanes(svg);
                
                // 2. Draw Axis (Foreground/Sticky)
                drawAxis(svg);
                
                // 3. Draw Events
                drawEvents(svg);
            }}
            
            function getX(timestamp) {{
                const days = (timestamp - state.minDate) / (1000 * 60 * 60 * 24);
                return MARGIN_LEFT + days * state.scale + state.offsetX;
            }}
            
            function drawAxis(svg) {{
                // Determine interval
                let intervalType = 'year';
                if (state.scale > 2) intervalType = 'month';
                if (state.scale > 10) intervalType = 'day';
                
                const startDate = new Date(state.minDate);
                const endDate = new Date(state.maxDate);
                
                let current = new Date(startDate);
                if (intervalType === 'year') current.setMonth(0, 1);
                if (intervalType === 'month') current.setDate(1);
                
                const ticks = [];
                while (current <= endDate) {{
                    ticks.push(new Date(current));
                    if (intervalType === 'year') current.setFullYear(current.getFullYear() + 1);
                    else if (intervalType === 'month') current.setMonth(current.getMonth() + 1);
                    else current.setDate(current.getDate() + 1);
                }}
                
                // Draw Ticks
                let pathD = "";
                ticks.forEach(date => {{
                    const x = getX(date.getTime());
                    if (x < MARGIN_LEFT) return;
                    if (x > state.width) return;
                    
                    // Grid line (full height)
                    const maxY = Math.max(state.totalHeight, state.height);
                    pathD += `M${{x}},${{MARGIN_TOP}} L${{x}},${{maxY}} `;
                    
                    // Label
                    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    text.setAttribute("x", x + 5);
                    text.setAttribute("y", MARGIN_TOP - 10);
                    text.setAttribute("class", "axis-text");
                    
                    let label = "";
                    if (intervalType === 'year') label = date.getFullYear();
                    else if (intervalType === 'month') label = date.toLocaleString('default', {{ month: 'short', year: '2-digit' }});
                    else label = date.getDate();
                    
                    text.textContent = label;
                    svg.appendChild(text);
                }});
                
                // Axis Line
                const grid = document.createElementNS("http://www.w3.org/2000/svg", "path");
                grid.setAttribute("d", pathD);
                grid.setAttribute("class", "axis-line");
                grid.setAttribute("stroke-dasharray", "2,2");
                grid.setAttribute("opacity", "0.3");
                svg.insertBefore(grid, svg.firstChild);
            }}
            
            function drawSwimlanes(svg) {{
                state.filteredEntities.forEach(e => {{
                    const y = e.y + state.offsetY;
                    
                    // Optimization: Don't draw if out of view
                    if (y < -50 || y > state.height + 50) return;
                    
                    // Group Header
                    if (e.isGroupHeader) {{
                        const gText = document.createElementNS("http://www.w3.org/2000/svg", "text");
                        gText.setAttribute("x", 10);
                        gText.setAttribute("y", y - 25);
                        gText.setAttribute("class", "group-text");
                        gText.textContent = e.group;
                        svg.appendChild(gText);
                    }}
                    
                    // Line
                    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    line.setAttribute("x1", MARGIN_LEFT);
                    line.setAttribute("y1", y);
                    line.setAttribute("x2", state.width);
                    line.setAttribute("y2", y);
                    line.setAttribute("class", "swimlane-line");
                    svg.appendChild(line);
                    
                    // Label
                    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    text.setAttribute("x", MARGIN_LEFT - 10);
                    text.setAttribute("y", y + 5);
                    text.setAttribute("text-anchor", "end");
                    text.setAttribute("class", "swimlane-text");
                    text.textContent = e.name;
                    svg.appendChild(text);
                }});
            }}
            
            function drawEvents(svg) {{
                state.filteredEvents.forEach(e => {{
                    const x = getX(e.timestamp);
                    if (x < MARGIN_LEFT || x > state.width) return;
                    
                    const a = normalize(e.actor);
                    const t = normalize(e.target);
                    
                    const yA = state.yMap[a] ? state.yMap[a] + state.offsetY : null;
                    const yT = state.yMap[t] ? state.yMap[t] + state.offsetY : null;
                    
                    // Interaction Line
                    if (yA && yT && yA !== yT) {{
                        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                        line.setAttribute("x1", x);
                        line.setAttribute("y1", yA);
                        line.setAttribute("x2", x);
                        line.setAttribute("y2", yT);
                        line.setAttribute("class", "event-line");
                        svg.appendChild(line);
                        
                        // Target Dot
                        drawDot(svg, x, yT, 6, e.type === "Conflict" ? "#b30000" : "#333", e);
                    }} 
                    // Solo Event
                    else if (yA) {{
                        drawDot(svg, x, yA, 4, "#666", e);
                    }}
                }});
            }}
            
            function drawDot(svg, x, y, r, color, event) {{
                const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                circle.setAttribute("cx", x);
                circle.setAttribute("cy", y);
                circle.setAttribute("r", r);
                circle.setAttribute("fill", color);
                circle.setAttribute("class", "event-marker");
                
                // Tooltip
                circle.addEventListener('mouseenter', (evt) => {{
                    const tt = document.getElementById('tooltip');
                    tt.style.opacity = 1;
                    tt.innerHTML = `<b>${{event.date}}</b><br>${{event.desc}}<br><i>${{event.actor}} -> ${{event.target}}</i>`;
                    tt.style.left = (evt.pageX + 10) + 'px';
                    tt.style.top = (evt.pageY - 10) + 'px';
                }});
                circle.addEventListener('mouseleave', () => {{
                    document.getElementById('tooltip').style.opacity = 0;
                }});
                
                svg.appendChild(circle);
            }}

            // --- INTERACTIONS ---
            function setupInteractions() {{
                const container = document.getElementById('timeline-container');
                
                // Zoom
                container.addEventListener('wheel', (e) => {{
                    e.preventDefault();
                    
                    if (e.ctrlKey || e.metaKey) {{
                        // Zoom
                        const zoomSpeed = 0.001;
                        const zoomFactor = Math.exp(-e.deltaY * zoomSpeed);
                        
                        const mouseX = e.clientX - MARGIN_LEFT;
                        const oldScale = state.scale;
                        const newScale = oldScale * zoomFactor;
                        
                        if (newScale < 0.1) return;
                        if (newScale > 50) return;
                        
                        const worldX = (mouseX - state.offsetX) / oldScale;
                        state.offsetX = mouseX - worldX * newScale;
                        state.scale = newScale;
                    }} else {{
                        // Pan Vertical
                        state.offsetY -= e.deltaY;
                        // Limit vertical pan
                        const minOffset = Math.min(0, state.height - state.totalHeight - 50);
                        if (state.offsetY > 0) state.offsetY = 0;
                        if (state.offsetY < minOffset) state.offsetY = minOffset;
                    }}
                    
                    requestAnimationFrame(render);
                }}, {{ passive: false }});
                
                // Pan Drag
                let isDragging = false;
                let lastX = 0;
                let lastY = 0;
                
                container.addEventListener('mousedown', (e) => {{
                    isDragging = true;
                    lastX = e.clientX;
                    lastY = e.clientY;
                    container.style.cursor = 'grabbing';
                }});
                
                window.addEventListener('mousemove', (e) => {{
                    if (!isDragging) return;
                    const dx = e.clientX - lastX;
                    const dy = e.clientY - lastY;
                    lastX = e.clientX;
                    lastY = e.clientY;
                    
                    state.offsetX += dx;
                    state.offsetY += dy;
                    
                    // Limit vertical pan
                    const minOffset = Math.min(0, state.height - state.totalHeight - 50);
                    if (state.offsetY > 0) state.offsetY = 0;
                    if (state.offsetY < minOffset) state.offsetY = minOffset;
                    
                    requestAnimationFrame(render);
                }});
                
                window.addEventListener('mouseup', () => {{
                    isDragging = false;
                    container.style.cursor = 'grab';
                }});
                
                window.addEventListener('resize', () => {{
                    state.width = window.innerWidth;
                    state.height = window.innerHeight - 50;
                    requestAnimationFrame(render);
                }});
            }}

            // --- UTILS ---
            function toggleDropdown(id) {{
                document.getElementById(id).classList.toggle("show");
            }}
            
            function resetFilters() {{
                document.querySelectorAll('input:checked').forEach(c => c.checked = false);
                state.selectedTopics = [];
                state.selectedParticipants = [];
                document.getElementById('topics-btn').innerText = `Темы (0/5)`;
                document.getElementById('participants-btn').innerText = `Участники (0/5)`;
                applyFilters();
                requestAnimationFrame(render);
            }}
            
            window.onclick = function(event) {{
                if (!event.target.matches('.dropdown-button')) {{
                    var dropdowns = document.getElementsByClassName("dropdown-content");
                    for (var i = 0; i < dropdowns.length; i++) {{
                        var openDropdown = dropdowns[i];
                        if (openDropdown.classList.contains('show') && !openDropdown.contains(event.target)) {{
                            openDropdown.classList.remove('show');
                        }}
                    }}
                }}
            }}

            // Start
            init();
        </script>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Generated visualization: {output_path}")

def main(args_list=None):
    parser = argparse.ArgumentParser(description="Generate Tufte Timeline from JSON files.")
    parser.add_argument("input_path", nargs="?", default=DEFAULT_JSON_DIR, help="Path to folder with JSON files or specific JSON file")
    parser.add_argument("--output-file", help="Path to save the generated HTML file")
    
    if args_list:
        args = parser.parse_args(args_list)
    else:
        args = parser.parse_args()

    all_events = []
    all_entities = []
    all_topics = set()

    if os.path.isdir(args.input_path):
        files = glob.glob(os.path.join(args.input_path, "*.json"))
    else:
        files = [args.input_path]

    print(f"Found {len(files)} JSON files in {args.input_path}")

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'metadata' in data: source = data['metadata']
                else: source = data
                
                if 'topics' in source:
                    for t in source['topics']: all_topics.add(t)
                
                doc_topics = source.get('topics', [])
                events = source.get('events', [])
                for e in events:
                    if 'topics' not in e: e['topics'] = doc_topics
                
                all_events.extend(events)
                all_entities.extend(source.get('entities', []))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Determine output path
    if args.output_file:
        output_path = args.output_file
    else:
        # Infer from input path
        if os.path.isdir(args.input_path) and os.path.basename(os.path.normpath(args.input_path)) == 'json':
            # If input is .../json, save to .../tufte_timeline.html
            output_path = os.path.join(os.path.dirname(os.path.normpath(args.input_path)), "tufte_timeline.html")
        else:
            output_path = DEFAULT_OUTPUT_FILE

    if all_events:
        generate_tufte_html(all_entities, all_events, all_topics, output_path)
    else:
        print("No events found to visualize.")

if __name__ == "__main__":
    main()
