import asyncio
import time
import gradio as gr

# Import everything from your existing captain.py file
# (Adjust 'captain' if your main file has a different name)
import captain  
from captain import memory, LATEST_DATA, summarize, route_ff, send_stuff, answer, generator

# --- UI Execution Controller ---
# This wrapper handles the timing and formatting without touching your core code!

async def process_query_for_demo(user_query: str):
    if not user_query.strip():
        yield "Please enter a valid question.", "No query processed.", "0.0s"
        return

    # Phase 1: Summarize & Route
    yield "Summarizing history and routing firefighters...", "Routing in progress...", "Calculating..."
    await summarize()
    
    start_route = time.perf_counter()
    # Call your original route_ff function
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

    # Phase 2: Fetch Firefighter Data
    start_fetch = time.perf_counter()
    # Call your original send_stuff function
    LATEST_DATA[:] = await send_stuff(decision, user_query)
    fetch_latency = time.perf_counter() - start_fetch
    
    data_formatted = (
        f"{decision_formatted}\n\n"
        f"🚒 FIREFIGHTER DATA RETRIEVED:\n"
        f"{LATEST_DATA}\n"
        f"⏱️ Retrieval Latency: {fetch_latency:.2f}s"
    )
    
    yield "Synthesizing final compliance answer...", data_formatted, "Generating response..."

    # Phase 3: Synthesize Answer
    start_gen = time.perf_counter()
    # Call your original answer function (which we bypass slightly here to capture exact generation time)
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
    
    # Save to your imported memory
    memory.conversation.append({user_query: final_answer})
    
    yield final_answer, final_telemetry, f"{total_latency:.2f} seconds"


# --- Gradio UI Definition ---

def build_interface():
    with gr.Blocks(title="AdaptiveRAG Command Center", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🚒 Captain-Firefighter Control Room Dashboard")
        gr.Markdown("Watch the Captain coordinate active firefighting telemetry in real-time.")
        
        with gr.Row():
            with gr.Column(scale=1):
                query_input = gr.Textbox(
                    label="Ask Jesslyn (e.g., 'What is the current heart rate of ff1?')", 
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
                    placeholder="Intermediate decisions, data shapes, and per-step latencies will appear here...",
                    lines=13,
                    interactive=False
                )
        
        submit_btn.click(
            fn=process_query_for_demo,
            inputs=[query_input],
            outputs=[output_answer, telemetry_log, system_timer]
        )
        
    return demo


# --- Main Runner ---

# --- Main Runner ---

async def main():
    # 1. Start your background data stream generator
    print("Starting background telemetry stream generator...")
    asyncio.create_task(generator.start_stream())
    
    # 2. Build the Gradio interface
    demo = build_interface()
    demo.queue()
    
    # 3. Launch Gradio (FIXED: Removed 'await' because launch() is synchronous)
    # prevent_thread_lock=True allows Python to continue running past this line
    print("Launching web interface...")
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860, 
        prevent_thread_lock=True
    )
    
    # 4. Keep the asyncio loop alive so the background tasks can run
    print("Dashboard is live at http://127.0.0.1:7860 🚒")
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    print("Initializing Control Room Interface...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")

if __name__ == '__main__':
    print("Initializing Control Room Interface...")
    asyncio.run(main())