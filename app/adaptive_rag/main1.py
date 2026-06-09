from document_loader1 import load_and_split
from vector_store1 import create_vector_store
import ollama
import subprocess
import os

import time # This is just to test the amount of time it takes to think, for testing purposes ;)

def ensure_models():
    models = ["llama3.2:3b", "nomic-embed-text"]
    ollama_exe = r"C:\Users\katel\AppData\Local\Programs\Ollama\ollama.exe"
    for model in models:
        subprocess.run([ollama_exe, "pull", model], capture_output=True)

ensure_models()

# Global variables
top = 3  # how many chunks to retrieve
t = 0    # temperature 0-1

SYSTEM_PROMPT = """
You are a lightweight AI assistant. 
Answer queries ONLY with the provided data with minimal token output.
If the query is out of scope, say "I am unsure".
"""

print("waiting...")
# This is to load all of the csv files!
docs_folder = "docs"
all_chunks = []
for filename in os.listdir(docs_folder):
    if filename.endswith(".csv"):
        file_path = os.path.join(docs_folder, filename)
        print(f"Loading and splitting: {file_path}")
        try:
            file_chunks = load_and_split(file_path)
            all_chunks.extend(file_chunks)
        except Exception as e:
            print("whoops this csv didn't work")

chunks = all_chunks

print("creating the vector store")
database = create_vector_store(chunks)
retriever = database.as_retriever(search_kwargs={"k": top})

def ask(question: str):
    docs = retriever.invoke(question)
    context = "\n\n".join([d.page_content for d in docs])

    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ]
    )
    return response["message"]["content"]

if __name__ == "__main__":
    while True:
        question = input("What's your question? ")
        if question.lower() in ["quit", "exit"]:
            break
        print(f"\nOkay gimme one second...\n")
        start = time.time()
        answer = ask(question)
        print(f"I got it! \n{answer}\n")
        end = time.time()
        print("This response took ", end - start, " seconds!")