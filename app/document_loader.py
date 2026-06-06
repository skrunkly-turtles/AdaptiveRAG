from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Global variables that I can change at will :D
size = 300
overlap = 30


def load_and_split(path:str):
    if path.endswith(".csv"): #add other file types as needed. Hopefully not lol
        loader = CSVLoader(file_path=file_path, encoding="utf-8")
    else:
        loader = DirectoryLoader(path, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size = size,
        chunk_overlap = overlap
    )

    return splitter.split_documents(documents)