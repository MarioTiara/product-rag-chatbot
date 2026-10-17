# Product RAG Chatbot

## Summary

Product RAG Chatbot is an AI-powered chatbot application that helps customers retrieve product information through natural language conversations.

The application combines **Retrieval-Augmented Generation (RAG)** with structured database queries to provide accurate and relevant answers about products, including pricing, stock availability, specifications, and warranty information.

It integrates the OpenAI API to understand customer questions, select the appropriate retrieval tools, and generate responses based on retrieved data.

The project aims to demonstrate how Large Language Models (LLMs), vector databases, and traditional relational databases can work together to build an intelligent product assistant.

## Features

- **Natural Language Conversations** — Allow customers to ask product-related questions using everyday language.
- **Product Search** — Search products by name, SKU, category, or price range.
- **Real-Time Stock Lookup** — Retrieve stock quantities from the product database.
- **Price Information** — Provide product prices based on structured database records.
- **Semantic Search** — Retrieve relevant product descriptions and specifications using vector embeddings.
- **Retrieval-Augmented Generation (RAG)** — Generate context-aware responses based on retrieved product information.
- **Tool Calling** — Enable the LLM to invoke backend functions for product searches and stock lookups.
- **REST API** — Expose chatbot functionality through a FastAPI endpoint.

## Architecture

The application uses a hybrid retrieval architecture that combines structured queries and semantic search.

- **FastAPI** handles incoming chat requests.
- **OpenAI API** interprets questions, selects tools, and generates responses.
- **SQLite** stores structured product information, including prices and stock quantities.
- **ChromaDB** stores vector embeddings for product descriptions, specifications, and warranty information.
- **OpenAI Embeddings** convert product documents into vectors for semantic retrieval.

### Request Flow

1. A customer submits a question through the chatbot interface or REST API.
2. The backend sends the question to the OpenAI API.
3. The model determines which retrieval tools are needed.
4. The backend executes the requested database query or semantic search.
5. The retrieved information is returned to the model as context.
6. The model generates a response based on the available information.
7. The backend returns the answer to the customer.

Structured database queries are the source of truth for stock quantities and prices, while RAG is used to retrieve descriptive product knowledge.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend Framework | FastAPI |
| LLM Integration | OpenAI API |
| LLM Communication | OpenAI Responses API and Function Calling |
| Relational Database | SQLite |
| Vector Database | ChromaDB |
| Embedding Model | `text-embedding-3-small` |
| Data Source | CSV product catalog |
| Frontend | Streamlit (planned) |

## Project Structure

```text
product-rag-chatbot/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── product_service.py
│   ├── rag_service.py
│   └── chatbot.py
├── data/
│   └── prodct.csv
├── scripts/
│   └── import_products.py
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

### Directory Description

| File or Directory | Description |
|---|---|
| `app/main.py` | Defines the FastAPI application and chatbot endpoints. |
| `app/database.py` | Initializes and manages the SQLite database connection. |
| `app/product_service.py` | Implements structured product search and stock lookup operations. |
| `app/rag_service.py` | Handles document embeddings, vector indexing, and semantic retrieval. |
| `app/chatbot.py` | Integrates the OpenAI API with backend retrieval tools. |
| `data/prodct.csv` | Contains the initial product catalog. |
| `scripts/import_products.py` | Imports product data from CSV into the database. |
| `.env` | Stores environment variables and API configuration. |
| `.gitignore` | Excludes sensitive files and generated artifacts from version control. |
| `requirements.txt` | Lists the Python dependencies. |

## Prerequisites

Before running the application, make sure you have:

- Python 3.10 or later.
- An OpenAI API key with access to the required models.
- `pip` for installing Python dependencies.

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd product-rag-chatbot
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate the virtual environment.

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows**

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` has not been created yet, install the initial dependencies:

```bash
pip install openai fastapi uvicorn python-dotenv pandas chromadb streamlit
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

Replace the placeholder API key with your own key. The model name is configurable and must be available to your OpenAI API project.

**Security:** Never commit your `.env` file or expose your API key in frontend code or public repositories.

### 5. Import product data

Prepare `data/prodct.csv` with the required product fields, then run the CSV import script:

```bash
python -m scripts.import_products
```

The importer should create or update product records in the SQLite database.

### 6. Run the API server

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## API Usage

### Chat Endpoint

**Endpoint:** `POST /chat`

Example request:

```json
{
  "message": "How many Lenovo ThinkPad E14 laptops are available?"
}
```

Example response:

```json
{
  "conversation_id": "b8c7f7f1-7d4f-4a7f-9c57-3e8d3a9b2f30",
  "answer": "There are 12 Lenovo ThinkPad E14 laptops available."
}
```

The response above is illustrative. Actual answers depend on the product records in the database.

### Start a Conversation

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Tell me about ASUS VivoBook 14"}'
```

### Continue a Conversation

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"b8c7f7f1-7d4f-4a7f-9c57-3e8d3a9b2f30","message":"What about the 8 GB version?"}'
```

### Get Conversation History

```bash
curl http://127.0.0.1:8000/chat/b8c7f7f1-7d4f-4a7f-9c57-3e8d3a9b2f30/history
```

## Example Questions

Customers can ask questions such as:

- How much does the Lenovo ThinkPad E14 cost?
- How many units are currently available?
- Which laptops cost less than IDR 8,000,000?
- What are the specifications of this product?
- What is the warranty period?
- Which products are suitable for office work?
- Can you compare two products based on their specifications?



Stock quantities and prices should be retrieved from the relational database rather than inferred from vector search results.

## Development Roadmap

- [ ] Create and populate the product catalog.
- [ ] Implement SQLite database initialization.
- [ ] Implement CSV import and update functionality.
- [ ] Implement product search and stock lookup services.
- [ ] Integrate the OpenAI Responses API and function calling.
- [ ] Implement document indexing and semantic retrieval with ChromaDB.
- [ ] Integrate RAG tools into the chatbot workflow.
- [ ] Build a Streamlit chat interface.
- [ ] Add automated tests for retrieval and chatbot behavior.
- [ ] Add logging, error handling, and API rate limiting.
- [ ] Containerize the application with Docker.
- [ ] Evaluate answer accuracy and retrieval relevance.

## Future Improvements

Potential improvements include:

- Replace SQLite with PostgreSQL for a more production-oriented database.
- Add conversation history and context management.
- Implement hybrid search combining keyword search and vector similarity.
- Add reranking to improve retrieval relevance.
- Provide product source references in chatbot responses.
- Add authentication and role-based access control.
- Deploy the application using Docker and a cloud hosting platform.
- Build an evaluation dataset to measure retrieval accuracy and answer quality.

## Disclaimer

This project is intended for learning and demonstration purposes. Any sample product information or stock quantities used during development may be synthetic and should not be treated as real inventory data.

## License

Add a license file if you intend to distribute or publish this project. Ensure that any third-party datasets used in the project permit your intended use.
