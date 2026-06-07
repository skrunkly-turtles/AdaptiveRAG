from app.adaptive_rag.document_loader1 import load_and_split
from app.adaptive_rag.vector_store1 import create_vector_store
from langchain_ollama import ChatOllama

# Global variables I can change at a whim :)
top = 3 # Determines how many chunks should be retrieved!
t =0 # A variable from 0-1 to determine variance and variability for llm

SYSTEM_PROMPT =  """
You are a lightweight AI assistant. 
Answer queries ONLY with the provided data with minimal token output.
If the query is out of scope, say "I am unsure".
"""

print("waiting...")
chunks = load_and_split("docs/Medicaldataset.csv")

print("creating the vector store")
database = create_vector_store(chunks)
retriever = database.as_retriever(search_kwargs={"k": top})

llm = ChatOllama(model="llama3.2:3b", temperature=t, base_url="http://127.0.0.1:11434")

def ask(question: str, context: str):
    docs = retriever.invoke(question)
    context = "\n\n".join([d.page_content for d in docs])

    prompt = f"""Use the following context ONLY to answer the question.

    Context:
    {context}

    Question: {question}
    Answer:"""

    answer = llm.invoke(prompt)
    return answer.content

if __name__ == "__main__":
    while True:
        question = input("What's your question? ")
        if question.lower() == "quit" or question.lower() == "exit":
            break
        print(f"\nOkay gimme one second...\n")
        answer = ask(question, "docs/Medicaldataset.csv")
        print(f"I got it! \n{answer}\n")