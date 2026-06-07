import ollama
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

class OllamaDirectEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [ollama.embed(model="nomic-embed-text", input=t)["embeddings"][0] for t in texts]
    
    def embed_query(self, text):
        return ollama.embed(model="nomic-embed-text", input=text)["embeddings"][0]

def create_vector_store(chunks):
    embeddings = OllamaDirectEmbeddings()
    return FAISS.from_documents(chunks, embeddings)