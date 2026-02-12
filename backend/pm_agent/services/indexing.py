# services/indexing.py

from models import SessionLocal, UploadedFile
from services.pinecone_service import pinecone_service
from services.chunking_service import chunking_service
from services.embedding_service import embedding_service
from datetime import datetime
import traceback


def index_file_background(
    file_id: int,
    text: str,
    source_filename: str,
    file_type: str,
    uploaded_by: str,
    uploaded_at
):
    """
    Background task:
    - Chunk text
    - Create embeddings
    - Store in Pinecone
    - Mark file as 'indexed' so it can be reused for 20 days
    """

    db = SessionLocal()
    try:
        uploaded_file = db.query(UploadedFile).filter(
            UploadedFile.id == file_id
        ).first()

        if not uploaded_file:
            print(f"[INDEXING] File {file_id} not found")
            return

        # Use DB text if missing
        text_to_index = text or uploaded_file.extracted_text or ""
        if not text_to_index.strip():
            uploaded_file.indexing_status = "error"
            db.commit()
            print(f"[INDEXING] File {file_id} has no text to index")
            return

        # Normalize datetime
        if isinstance(uploaded_at, str):
            try:
                uploaded_at = datetime.fromisoformat(uploaded_at.replace("Z", "+00:00"))
            except:
                uploaded_at = uploaded_file.upload_time or datetime.utcnow()

        # Chunk text
        chunks = chunking_service.chunk_text_by_characters(
            text=text_to_index,
            chunk_size=400,
            chunk_overlap=100,
            metadata={
                "file_id": str(file_id),
                "file_name": source_filename
            }
        )

        if not chunks:
            uploaded_file.indexing_status = "error"
            db.commit()
            print(f"[INDEXING] No chunks generated for file {file_id}")
            return

        # Create embeddings
        embeddings = embedding_service.embed(
            [chunk["text"] for chunk in chunks]
        )

        # Save to Pinecone (shared index)
        pinecone_service.index_file_chunks(
            file_id=file_id,
            file_name=source_filename,
            chunks=chunks,
            embeddings=embeddings
        )

        # ✅ CRITICAL FOR 20-DAY REUSE
        uploaded_file.indexing_status = "indexed"
        db.commit()

        print(f"[INDEXING] File {file_id} indexed and cached successfully")

    except Exception as e:
        print(f"[INDEXING] Error indexing file {file_id}: {e}")
        print(traceback.format_exc())
        try:
            uploaded_file.indexing_status = "error"
            db.commit()
        except:
            pass
    finally:
        db.close()
