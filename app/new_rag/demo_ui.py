import asyncio
import time
import sqlite3
import os
import pandas as pd
import gradio as gr

# Import your existing captain logic
import captain  
from captain import memory, LATEST_DATA, summarize, route_ff, send_stuff, generator

# Path to your firefighter databases
DB_PATHS = {
    "Firefighter 1": "data/vitals.db",
    "Firefighter 2": "data/vitals2.db",
    "Firefighter 3": "data/vitals3.db"
}

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
    ff_chips = ""
    colors = {1: "#3b82f6", 2: "#10b981", 3: "#8b5cf6"}
    for ff in decision.firefighters :
        color = colors.get(int(ff), "#6b7280")
        ff_chips += f"""
        <span style="
            background-color: {color}; 
            color: white; 
            padding: 4px 10px; 
            border-radius: 12px; 
            font-weight: 600; 
            font-size: 0.85em;
            margin-right: 6px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        ">FF {ff}</span>
        """
    if not ff_chips:
        ff_chips = "<span style='color: #9ca3af; font-style: italic;'>None Selected</span>"

    urgency_val = float(decision.urgency)
    if urgency_val >= 0.7:
        urgency_bg = "#fef2f2"
        urgency_color = "#ef4444"
        urgency_border = "#fca5a5"
        urgency_text = f"CRITICAL ({urgency_val})"
        pulsing = "animation: pulse 1.5s infinite;"
    elif urgency_val >= 0.4:
        urgency_bg = "#fffbeb"
        urgency_color = "#d97706"
        urgency_border = "#fcd34d"
        urgency_text = f"ELEVATED ({urgency_val})"
        pulsing = ""
    else:
        urgency_bg = "#f0fdf4"
        urgency_color = "#15803d"
        urgency_border = "#bbf7d0"
        urgency_text = f"ROUTINE ({urgency_val})"
        pulsing = ""

    def fmt_lat(val):
        return f"{val:.2f}s" if val is not None else "--"

    html_content = f"""
    <style>
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
            100% {{ opacity: 1; }}
        }}
    </style>
    <div style="
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px;">
            <h3 style="margin: 0; color: #1f2937; font-size: 1.2em; font-weight: 700; display: flex; align-items: center; gap: 8px;">
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
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: #6b7280; font-weight: 600; text-transform: uppercase;">Active Deployments</p>
                <div style="display: flex; flex-wrap: wrap; gap: 4px; padding-top: 4px;">{ff_chips}</div>
            </div>
            <div>
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: #6b7280; font-weight: 600; text-transform: uppercase;">Temporal Window</p>
                <span style="background-color: #f3f4f6; color: #374151; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.9em; font-weight: 600;">⏱{decision.window.upper()}</span>
            </div>
            <div style="grid-column: span 2;">
                <p style="margin: 0 0 4px 0; font-size: 0.8em; color: #6b7280; font-weight: 600; text-transform: uppercase;">Decided Target Horizon</p>
                <div style="font-family: monospace; color: #111827; font-size: 0.95em; background: #fafafa; padding: 8px; border-radius: 6px; border: 1px dashed #e5e7eb;">
                    {decision.time}
                </div>
            </div>
        </div>

        <div style="background: #f8fafc; border-radius: 8px; padding: 12px; border: 1px solid #e2e8f0;">
            <p style="margin: 0 0 8px 0; font-size: 0.8em; color: #475569; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Telemetry Performance Metrics</p>
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #475569;">
                <div>Routing: <strong>{fmt_lat(route_lat)}</strong></div>
                <div>Retrieval: <strong>{fmt_lat(fetch_lat)}</strong></div>
                <div>Synthesis: <strong>{fmt_lat(gen_lat)}</strong></div>
            </div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 0.9em; color: #1e293b;">Total Loop Latency:</span>
                <span style="font-size: 1.1em; font-weight: 800; color: #0f172a;">{fmt_lat(total_lat)}</span>
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
        gr.Markdown("# 🚒 Captain-Firefighter Control Room Dashboard")
        
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