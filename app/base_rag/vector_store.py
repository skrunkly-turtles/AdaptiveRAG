from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

def create_vector_store(chunks):
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://127.0.0.1:11434")
    return FAISS.from_documents(chunks, embeddings)
