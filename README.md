# AdaptiveRAG
An adaptive RAG pipeline specified for the user case. 

base_rag:
The most bare-boned RAG model, as seen online. It only retrieves the top k chunks based on vector mappings

firefighter_rag:
The first demo, not relevant anymore. Structure below:
<img width="2286" height="1310" alt="image" src="https://github.com/user-attachments/assets/aa2eda2f-993c-43e9-a92d-a954bb7f4d9f" />

new_rag:
The most current model. Structure below:
<img width="1492" height="1126" alt="image" src="https://github.com/user-attachments/assets/edc7dd01-502b-4be4-b5b4-f3a2064eecab" />

HOW TO USE:
(1) Download all the libraries in requirements.txt
(2) Pull ollama qwen2.5:14b 
(3) Run demo_ui.py and open the extension as you would like.