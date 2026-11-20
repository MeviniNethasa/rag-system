# RAG System

A Retrieval-Augmented Generation (RAG) system: it finds the documents relevant to a question and gives them to a language model as context, so answers are grounded in your own data.

## Status

Early stage. The code is not in the repository yet.

## Planned structure

- **Ingestion:** load documents and split them into chunks
- **Embedding:** turn chunks into vectors and store them in a vector database
- **Retrieval:** find the chunks most relevant to a query
- **Generation:** send the query plus the retrieved context to an LLM to produce an answer

## Getting started

```bash
git clone https://github.com/MeviniNethasa/rag-system.git
cd rag-system
```

Setup steps will be added as the project develops.
