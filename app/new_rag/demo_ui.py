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

# --- Database Helper to Fetch Live Data ---

def fetch_latest_vitals_from_db():
    """Queries all three DBs and returns a unified DataFrame of latest events."""
    all_data = []
    
    for ff_name, path in DB_PATHS.items():
        # Handle cases where the relative paths might be deep in the directory tree
        resolved_path = path if os.path.exists(path) else os.path.join("app", "new_rag", path)
        
        if not os.path.exists(resolved_path):
            # Fallback placeholder if DB isn't generated yet
            all_data.append({
                "Firefighter": ff_name, 
                "Timestamp": "N/A", 
                "Heart Rate": "No DB found yet", 
                "Temperature": "N/A"
            })
            continue
            
        try:
            # Connect in read-only mode to prevent write locks with your generator
            conn = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # Dynamically fetch the table name
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if not tables:
                conn.close()
                continue
                
            table_name = tables[0][0]
            
            # Query the 5 most recent entries
            df = pd.read_sql_query(
                f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 5", 
                conn
            )
            conn.close()
            
            # Format dataframe for presentation
            df.insert(0, "Firefighter", ff_name)
            all_data.append(df)
            
        except Exception as e:
            all_data.append(pd.DataFrame([{
                "Firefighter": ff_name, 
                "Status": f"Error reading DB: {str(e)}"
            }]))

    if all_data:
        # Combine all data into one clean table
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame([{"System Status": "Waiting for database initialization..."}])


# --- UI Execution Controller (Tab 1 Q&A) ---

async def process_query_for_demo(user_query: str):
    if not user_query.strip():
        yield "Please enter a valid question.", "No query processed.", "0.0s"
        return

    yield "Summarizing history and routing firefighters...", "Routing in progress...", "Calculating..."
    await summarize()
    
    start_route = time.perf_counter()
    decision = await route_ff(user_query)
    route_latency = time.perf_counter() - start_route
    
    decision_formatted = (
        f"🎯 CAPTAIN DECISION:\n"
        f"- Targeted Firefighters: {decision.firefighters}\n"
        f"- Time Window: {decision.window}\n"
        f"- Urgency Level: {decision.urgency}\n"
        f"- Decided Target Time: {decision.time}\n"
        f"⏱️ Routing Latency: {route_latency:.2f}s"
    )
    
    yield "Fetching data from mapped firefighters...", decision_formatted, "Fetching data..."

    start_fetch = time.perf_counter()
    LATEST_DATA[:] = await send_stuff(decision, user_query)
    fetch_latency = time.perf_counter() - start_fetch
    
    data_formatted = (
        f"{decision_formatted}\n\n"
        f"🚒 FIREFIGHTER DATA RETRIEVED:\n"
        f"{LATEST_DATA}\n"
        f"⏱️ Retrieval Latency: {fetch_latency:.2f}s"
    )
    
    yield "Synthesizing final compliance answer...", data_formatted, "Generating response..."

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

    final_telemetry = (
        f"{data_formatted}\n\n"
        f"📊 PERFORMANCE METRICS:\n"
        f"- Total Loop Time: {total_latency:.2f}s\n"
        f"  └ Routing: {route_latency:.2f}s\n"
        f"  └ Fetching: {fetch_latency:.2f}s\n"
        f"  └ Generation: {gen_latency:.2f}s"
    )
    
    final_answer = response['response']
    memory.conversation.append({user_query: final_answer})
    
    yield final_answer, final_telemetry, f"{total_latency:.2f} seconds"


# --- Gradio UI Definition ---

def build_interface():
    with gr.Blocks(title="AdaptiveRAG Command Center", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🚒 Captain-Firefighter Control Room Dashboard")
        
        with gr.Tabs():
            # TAB 1: COMMAND AND CONTROL (Your Q&A)
            with gr.Tab("Dispatch & Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        query_input = gr.Textbox(
                            label="Ask Jesslyn (e.g., 'Compare the vitals of ff1 and ff2')", 
                            placeholder="Type your question here...",
                            lines=2
                        )
                        submit_btn = gr.Button("Transmit Query to Captain", variant="primary")
                        
                        output_answer = gr.Textbox(
                            label="Captain's Dispatch Response", 
                            placeholder="Awaiting transmission...",
                            lines=8,
                            interactive=False
                        )
                        
                    with gr.Column(scale=1):
                        system_timer = gr.Label(label="Total Roundtrip Processing Latency")
                        telemetry_log = gr.Textbox(
                            label="Live Pipeline Telemetry & Routing Log", 
                            placeholder="Intermediate decisions, data shapes, and per-step latencies...",
                            lines=13,
                            interactive=False
                        )
                
                # Wire up the submission actions
                submit_btn.click(
                    fn=process_query_for_demo,
                    inputs=[query_input],
                    outputs=[output_answer, telemetry_log, system_timer]
                )

            # TAB 2: LIVE TELEMETRY STREAM
            with gr.Tab("Active Telemetry Live Feed"):
                gr.Markdown("### 📡 Real-Time Database Stream (vitals.db, vitals2.db, vitals3.db)")
                gr.Markdown("This table polls your physical SQLite databases every 2 seconds to show incoming telemetry updates.")
                
                # Dynamic Gradio Dataframe component
                live_table = gr.Dataframe(
                    headers=["Firefighter", "Timestamp", "Vitals Data"],
                    interactive=False,
                    wrap=True
                )
                
                # Use Gradio's automatic stream loop to refresh this table every 2 seconds
                demo.load(
                    fn=fetch_latest_vitals_from_db,
                    inputs=None,
                    outputs=[live_table],
                    every=2.0
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
        prevent_thread_lock=True
    )
    
    print("Dashboard is live at http://127.0.0.1:7860 🚒")
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    print("Initializing Control Room Interface...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")