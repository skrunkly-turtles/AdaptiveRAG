import asyncio
import time
import sqlite3
import os
import pandas as pd
import gradio as gr
import json
import traceback

# Import your existing captain logic
import captain  
from captain import memory, LATEST_DATA, summarize, route_ff, send_stuff, generator

# Path to your firefighter databases
DB_PATHS = {
    "Firefighter 1": "data/vitals.db",
    "Firefighter 2": "data/vitals2.db",
    "Firefighter 3": "data/vitals3.db"
}
def fetch_memory_state():
    """Reads live memory structures directly from the imported memory object,
    fully wrapped to prevent silent Gradio freezes."""
    try:
        # Use the directly imported 'memory' object
        # 1. Fetch & Format Long-Term Master Data Summary
        data_summary = getattr(memory, "data_summary", "No consolidated memory yet.")
        
        # Format the last updated timestamp
        last_updated = getattr(memory, "last_updated", "Never")
        if hasattr(last_updated, "strftime"):
            last_updated_str = f"Last Consolidated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            last_updated_str = f"Last Consolidated: {last_updated}"
            
        # 2. Fetch & Format Firefighter Long-Term Status Profiles
        ff_summary = getattr(memory, "firefighter_summary", {})
        
        # If it's a string, try parsing it to a dictionary
        if isinstance(ff_summary, str):
            try:
                ff_summary = json.loads(ff_summary)
            except Exception:
                pass
                
        ff_html = "<div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;'>"
        colors = {1: "#3b82f6", 2: "#10b981", 3: "#8b5cf6"}
        for idx in [1, 2, 3]:
            # Safeguard lookup whether keys are integers or strings
            status = "No status recorded in long-term memory."
            if isinstance(ff_summary, dict):
                status = ff_summary.get(str(idx)) or ff_summary.get(idx) or status
            elif isinstance(ff_summary, str):
                status = ff_summary  # Fallback if the whole summary is an unparsed string
                
            color = colors[idx]
            ff_html += f"""
            <div style="
                background: var(--block-background-fill, #1f2937); 
                border: 1px solid var(--border-color-primary, #374151); 
                border-radius: 8px; 
                padding: 14px; 
                border-top: 4px solid {color};
                box-shadow: 0 2px 4px rgba(0,0,0,0.02);
                color: var(--body-text-color, #f3f4f6);
            ">
                <strong style="color: {color}; font-size: 0.95em; display: flex; align-items: center; gap: 6px;">Firefighter {idx} Memory Profile</strong>
                <p style="margin: 8px 0 0 0; font-size: 0.88em; color: var(--text-color-subdued, #9ca3af); line-height: 1.4;">{status}</p>
            </div>
            """
        ff_html += "</div>"
        
        # 3. Unpack Short-Term Conversation Buffer safely
        conversation = getattr(memory, "conversation", [])
        conv_rows = []
        
        for turn in conversation:
            if isinstance(turn, dict):
                for q, ans in turn.items():
                    # Filter out those accidental terminal inputs if they exist
                    if q in (1, 2, 3) and ans == "[object Object]":
                        continue
                    conv_rows.append([q, ans])
                    
        if conv_rows:
            conv_df = pd.DataFrame(conv_rows, columns=["User Query", "Captain Agent Response"])
        else:
            conv_df = pd.DataFrame(
                [["No active queries", "Type in Tab 1 to fill the live memory buffer."]], 
                columns=["User Query", "Captain Agent Response"]
            )
            
        return data_summary, ff_html, conv_df, last_updated_str

    except Exception as e:
        # If anything fails, return the error message visually to Tab 3
        error_trace = traceback.format_exc()
        error_html = f"""
        <div style="padding: 15px; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 8px; color: #f87171; font-family: monospace;">
            <strong>Memory Fetch Error:</strong> {str(e)}<br><br>
            <pre style="margin: 0; font-size: 0.85em; overflow-x: auto;">{error_trace}</pre>
        </div>
        """
        err_df = pd.DataFrame([["Error", str(e)]], columns=["User Query", "Captain Agent Response"])
        return f"Error loading summary: {str(e)}", error_html, err_df, "Error occurred"
    
# --- Database Helper to Fetch Isolated DB Data ---

def fetch_single_ff_db(path: str) -> pd.DataFrame:
    """Queries a single firefighter database and returns the last 5 entries."""
    resolved_path = path if os.path.exists(path) else os.path.join("app", "new_rag", path)
    
    if not os.path.exists(resolved_path):
        return pd.DataFrame([{"Timestamp": "N/A", "Status": "Database not found"}])
        
    try:
        # Connect in read-only mode to prevent write conflicts with the generator
        conn = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # Get table name
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            conn.close()
            return pd.DataFrame([{"Timestamp": "N/A", "Status": "Database is empty"}])
            
        table_name = tables[0][0]
        
        # Fetch 5 latest rows
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 5", conn)
        conn.close()
        
        # Return clean dataframe (remove rowid/id if present to keep it readable)
        if "rowid" in df.columns:
            df = df.drop(columns=["rowid"])
        return df
        
    except Exception as e:
        return pd.DataFrame([{"Timestamp": "N/A", "Error": str(e)}])


def fetch_all_firefighters():
    """Returns three separate dataframes, one for each firefighter DB."""
    df1 = fetch_single_ff_db(DB_PATHS["Firefighter 1"])
    df2 = fetch_single_ff_db(DB_PATHS["Firefighter 2"])
    df3 = fetch_single_ff_db(DB_PATHS["Firefighter 3"])
    return df1, df2, df3


# --- HTML Generator for High-End Demo Visuals ---

def generate_telemetry_html(decision, route_lat=None, fetch_lat=None, gen_lat=None, total_lat=None):
    """Generates a cohesive, theme-adaptive HTML card for the demo UI."""
    
    # 1. Map firefighters to clean visual chips
    ff_chips = ""
    colors = {1: "#3b82f6", 2: "#10b981", 3: "#8b5cf6"}  # Blue, Green, Purple
    for ff in decision.firefighters:
        color = colors.get(int(ff), "#6b7280")
        ff_chips += f"""
        <span style="
            background-color: {color}; 
            color: white; 
            padding: 4px 10px; 
            border-radius: 8px; 
            font-weight: 600; 
            font-size: 0.85em;
            margin-right: 6px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        ">FF {ff}</span>
        """
    if not ff_chips:
        ff_chips = "<span style='color: var(--text-color-subdued, #9ca3af); font-style: italic;'>None Selected</span>"

    # 2. Dynamic Urgency Badges
    urgency_val = float(decision.urgency)
    if urgency_val >= 0.7:
        urgency_bg = "rgba(239, 68, 68, 0.15)"
        urgency_color = "#f87171"
        urgency_border = "#ef4444"
        urgency_text = f"CRITICAL ({urgency_val})"
        pulsing = "animation: pulse 1.5s infinite;"
    elif urgency_val >= 0.4:
        urgency_bg = "rgba(217, 119, 6, 0.15)"
        urgency_color = "#fbbf24"
        urgency_border = "#d97706"
        urgency_text = f"ELEVATED ({urgency_val})"
        pulsing = ""
    else:
        urgency_bg = "rgba(16, 185, 129, 0.15)"
        urgency_color = "#34d399"
        urgency_border = "#10b981"
        urgency_text = f"ROUTINE ({urgency_val})"
        pulsing = ""

    # 3. Format Latencies (if available)
    def fmt_lat(val):
        return f"{val:.2f}s" if val is not None else "--"

    # THEME ADAPTIVE CSS CHANGES HAPPEN HERE:
    html_content = f"""
    <style>
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
            100% {{ opacity: 1; }}
        }}
    </style>
    <div style="
        font-family: var(--font, -apple-system, BlinkMacSystemFont, sans-serif);
        background: var(--block-background-fill, #1f2937);
        border: 1px solid var(--border-color-primary, #374151);
        border-radius: var(--block-radius, 8px);
        padding: 20px;
        color: var(--body-text-color, #f3f4f6);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color-secondary, #4b5563); padding-bottom: 12px; margin-bottom: 16px;">
            <h3 style="margin: 0; color: var(--block-title-text-color, #ffffff); font-size: 1.1em; font-weight: 700; display: flex; align-items: center; gap: 8px;">
                Captain Command Routing
            </h3>
            <span style="
                background-color: {urgency_bg};
                color: {urgency_color};
                border: 1px solid {urgency_border};
                padding: 4px 12px;
                border-radius: 20px;
                font-weight: 700;
                font-size: 0.8em;
                letter-spacing: 0.05em;
                {pulsing}
            ">{urgency_text}</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
            <div>
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: var(--text-color-subdued, #9ca3af); font-weight: 600; text-transform: uppercase;">Active Deployments</p>
                <div style="display: flex; flex-wrap: wrap; gap: 4px; padding-top: 4px;">{ff_chips}</div>
            </div>
            <div>
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: var(--text-color-subdued, #9ca3af); font-weight: 600; text-transform: uppercase;">Temporal Window</p>
                <span style="background-color: var(--neutral-100, #374151); color: var(--body-text-color, #f3f4f6); padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.9em; font-weight: 600;">⏱️ {decision.window.upper()}</span>
            </div>
            <div style="grid-column: span 2;">
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: var(--text-color-subdued, #9ca3af); font-weight: 600; text-transform: uppercase;">Decided Target Horizon</p>
                <div style="font-family: monospace; color: var(--body-text-color, #f3f4f6); font-size: 0.95em; background: var(--input-background-fill, #111827); padding: 8px; border-radius: 6px; border: 1px dashed var(--border-color-primary, #374151);">
                    {decision.time}
                </div>
            </div>
        </div>

        <div style="background: var(--input-background-fill, #111827); border-radius: 8px; padding: 12px; border: 1px solid var(--border-color-secondary, #4b5563);">
            <p style="margin: 0 0 8px 0; font-size: 0.8em; color: var(--text-color-subdued, #9ca3af); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Telemetry Performance Metrics</p>
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: var(--text-color-subdued, #9ca3af);">
                <div>Routing: <strong style="color: var(--body-text-color);">{fmt_lat(route_lat)}</strong></div>
                <div>Retrieval: <strong style="color: var(--body-text-color);">{fmt_lat(fetch_lat)}</strong></div>
                <div>Synthesis: <strong style="color: var(--body-text-color);">{fmt_lat(gen_lat)}</strong></div>
            </div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-color-primary, #374151); display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 0.9em; color: var(--body-text-color, #f3f4f6);">Total Loop Latency:</span>
                <span style="font-size: 1.1em; font-weight: 800; color: var(--block-title-text-color, #ffffff);">{fmt_lat(total_lat)}</span>
            </div>
        </div>
    </div>
    """
    return html_content

# --- UI Execution Controller (Tab 1 Q&A) ---

async def process_query_for_demo(user_query: str):
    if not user_query.strip():
        yield "Please enter a valid question.", "<div>Enter a query...</div>", "0.0s"
        return

    yield "Summarizing history and routing firefighters...", "<div>Routing in progress...</div>", "Calculating..."
    await summarize()
    
    start_route = time.perf_counter()
    decision = await route_ff(user_query)
    route_latency = time.perf_counter() - start_route
    
    intermediate_html = generate_telemetry_html(decision, route_lat=route_latency)
    yield "Fetching data from mapped firefighters...", intermediate_html, "Fetching data..."

    start_fetch = time.perf_counter()
    LATEST_DATA[:] = await send_stuff(decision, user_query)
    fetch_latency = time.perf_counter() - start_fetch
    
    intermediate_html_2 = generate_telemetry_html(decision, route_lat=route_latency, fetch_lat=fetch_latency)
    yield "Synthesizing final compliance answer...", intermediate_html_2, "Generating response..."

    start_gen = time.perf_counter()
    formatted_history = ""
    for t in memory.conversation:
        for question, response in t.items():
            formatted_history += f"Question: {question}\nAnswer: {response}\n\n"

    response = await captain.client.generate(
        model='qwen2.5:14b',
        system=captain.SYS_PROMPT,
        prompt=f"Query: {user_query}\nFireFighters: {LATEST_DATA}\nData Summary: {memory.data_summary}\nConversation History: {formatted_history}",
    )
    gen_latency = time.perf_counter() - start_gen
    total_latency = route_latency + fetch_latency + gen_latency

    final_telemetry_html = generate_telemetry_html(
        decision, 
        route_lat=route_latency, 
        fetch_lat=fetch_latency, 
        gen_lat=gen_latency, 
        total_lat=total_latency
    )
    
    final_answer = response['response']
    memory.conversation.append({user_query: final_answer})
    
    yield final_answer, final_telemetry_html, f"{total_latency:.2f} seconds"


# --- Gradio UI Definition ---

def build_interface():
    with gr.Blocks(title="AdaptiveRAG Command Center", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Captain-Firefighter Control Room Dashboard")
        
        with gr.Tabs():
            # TAB 1: COMMAND AND CONTROL
            with gr.Tab("Dispatch & Analysis"):
                with gr.Row():
                    with gr.Column(scale=12):
                        query_input = gr.Textbox(
                            label="Ask Jesslyn (e.g., 'Compare the vitals of ff1 and ff2')", 
                            placeholder="Type your question here...",
                            lines=2
                        )
                        submit_btn = gr.Button("Transmit Query to Captain", variant="primary")
                        
                        output_answer = gr.Textbox(
                            label="Captain's Dispatch Response", 
                            placeholder="Awaiting transmission...",
                            lines=10,
                            interactive=False
                        )
                        
                    with gr.Column(scale=10):
                        system_timer = gr.Label(label="Total Roundtrip Processing Latency")
                        
                        telemetry_log = gr.HTML(
                            value="<div style='color: #9ca3af; font-style: italic; text-align: center; padding: 40px 0;'>Transmit a query to view real-time command routing...</div>"
                        )
                
                submit_btn.click(
                    fn=process_query_for_demo,
                    inputs=[query_input],
                    outputs=[output_answer, telemetry_log, system_timer]
                )

            # TAB 2: LIVE TELEMETRY STREAM (UPDATED SIDE-BY-SIDE TABLES)
            with gr.Tab("Active Telemetry Live Feed"):
                gr.Markdown("### Real-Time Individual Database Streams")
                gr.Markdown("These tables independently poll each firefighter's database files every 2 seconds.")
                
                with gr.Row():
                    # Column 1: Firefighter 1
                    with gr.Column():
                        gr.Markdown("#### Firefighter")
                        live_table_1 = gr.Dataframe(interactive=False, wrap=True)
                        
                    # Column 2: Firefighter 2
                    with gr.Column():
                        gr.Markdown("#### Firefighter 2")
                        live_table_2 = gr.Dataframe(interactive=False, wrap=True)
                        
                    # Column 3: Firefighter 3
                    with gr.Column():
                        gr.Markdown("#### Firefighter 3")
                        live_table_3 = gr.Dataframe(interactive=False, wrap=True)
                
                # Hidden timer component (ticks every 2.0 seconds)
                timer = gr.Timer(value=2.0, active=True)
                
                # Tie the tick event to update all three dataframes simultaneously
                timer.tick(
                    fn=fetch_all_firefighters,
                    inputs=None,
                    outputs=[live_table_1, live_table_2, live_table_3]
                )
                
                # Load immediately when navigating to the page
                demo.load(
                    fn=fetch_all_firefighters,
                    inputs=None,
                    outputs=[live_table_1, live_table_2, live_table_3]
                )
            # TAB 3: CAPTAIN MEMORY ENGINE
            with gr.Tab("Captain Memory Engine"):
                gr.Markdown("### Live Cognitive Memory States")
                gr.Markdown("Inspect how the Captain compresses conversation details, discards redundancy, and maintains individual firefighter histories.")
                
                with gr.Row():
                    # Left Side: Long-term Rolling Summary
                    with gr.Column(scale=1):
                        gr.Markdown("#### Rolling Master History (`data_summary`)")
                        memory_time_badge = gr.Markdown("**Last Consolidated:** Never")
                        master_summary_box = gr.Textbox(
                            label="Consolidated Context (Replaces Old Summary)",
                            lines=6,
                            interactive=False
                        )
                        
                    # Right Side: Active Short-term Memory Buffer
                    with gr.Column(scale=1):
                        gr.Markdown("#### Active Conversation Buffer (Will compress at MAX_TURNS)")
                        conversation_buffer_table = gr.Dataframe(
                            headers=["User Query", "Captain Agent Response"],
                            interactive=False,
                            wrap=True
                        )
                
                # Bottom Row: Firefighter Profiles
                gr.Markdown("#### Persistent Firefighter Status Summaries (`firefighter_summary`)")
                ff_profiles_html = gr.HTML()
                
                # Update loop for Tab 3
                # Reuses the same 2-second timer you set up for Tab 2
                timer.tick(
                    fn=fetch_memory_state,
                    inputs=None,
                    outputs=[master_summary_box, ff_profiles_html, conversation_buffer_table, memory_time_badge]
                )
                
                # Load immediately when starting the app
                demo.load(
                    fn=fetch_memory_state,
                    inputs=None,
                    outputs=[master_summary_box, ff_profiles_html, conversation_buffer_table, memory_time_badge]
                )
                
    return demo


# --- Main Runner ---

async def main():
    print("Starting background telemetry stream generator...")
    asyncio.create_task(generator.start_stream())
    
    demo = build_interface()
    demo.queue()
    
    print("Launching web interface...")
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860, 
        prevent_thread_lock=True,
        share=True
    )
    
    print("Dashboard is live at http://127.0.0.1:7860")
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    print("Initializing Control Room Interface...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")