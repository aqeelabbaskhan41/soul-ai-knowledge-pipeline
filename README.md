Google Drive / Local Documents
            │
            ▼
      Extract Text
            │
            ▼
       Clean Text
            │
            ▼
      Token Chunking
            │
            ▼
   Generate Summaries
            │
            ▼
 Generate OpenAI Embeddings
            │
            ▼
Insert into Supabase pgvector
            │
            ▼
     LangGraph AI Agent

## Directory info:
knowledge_ingestion/
│
├── documents/
│   ├── Original PDF and DOCX files
│   └── Source knowledge base documents received from the client
│
├── output/
│   ├── Raw extracted text (.txt)
│   └── Direct output from the document extraction process (no cleaning applied)
│
├── cleaned/
│   ├── Basic cleaned text
│   └── Whitespace normalized, tabs removed, consistent line endings, and formatting standardized
│
├── knowledge_base/
│   ├── energy_cleaned/
│   ├── children_energy_cleaned/
│   ├── compatibility_cleaned/
│   ├── energy_related_actions_cleaned/
│   ├── misc_cleaned/
│   └── OTHER/
│
│   Final cleaned knowledge base used for RAG ingestion.
│   Matrix-specific noise has been removed, including:
│   - Repeated page headers
│   - Repeated footers
│   - Standalone page numbers
│   - Repeated website references
│
│   This directory is the single source of truth for the ingestion pipeline.
│
├── pipeline/
│   ├── extractor.py
│   ├── cleaner.py
│   └── cleaners/
│       └── energy_cleaner.py
│
├── extract.py
├── clean.py
└── requirements.txt