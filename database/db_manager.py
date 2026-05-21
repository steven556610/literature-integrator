import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define database directory and path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_PATH = os.path.join(DB_DIR, "literature.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()

class Literature(Base):
    __tablename__ = "literature"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(String, unique=True, index=True, nullable=False)  # arXiv ID or DOI
    title = Column(String, nullable=False)
    authors = Column(String)
    published_date = Column(String)  # YYYY-MM-DD
    summary = Column(Text)  # Original abstract
    url = Column(String)
    source = Column(String)  # arxiv, biorxiv, medrxiv
    
    # Analysis fields
    status = Column(String, default="pending")  # pending, analyzed, failed
    analyzed_at = Column(String)  # Timestamp
    llm_summary = Column(Text)
    code_available = Column(String)  # YES, NO, PARTIAL, UNKNOWN
    code_url = Column(String)
    data_available = Column(String)  # YES, NO, PARTIAL, UNKNOWN
    data_url = Column(String)
    theory_assumptions = Column(Text)
    exp_motivation = Column(Text)
    sota_comparison = Column(Text)
    raw_analysis = Column(Text)  # Full raw LLM output

# Create engine and session maker
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
    print(f"[*] Database initialized at: {DB_PATH}")

def get_session():
    """Get a database session."""
    return SessionLocal()

def add_paper(paper_dict):
    """
    Insert a paper into the database. 
    If a paper with same paper_id exists, does nothing and returns False.
    """
    session = get_session()
    try:
        # Check duplicate
        exists = session.query(Literature).filter(Literature.paper_id == paper_dict["paper_id"]).first()
        if exists:
            return False
            
        new_paper = Literature(
            paper_id=paper_dict["paper_id"],
            title=paper_dict["title"],
            authors=paper_dict.get("authors", ""),
            published_date=paper_dict.get("published_date", ""),
            summary=paper_dict.get("summary", ""),
            url=paper_dict.get("url", ""),
            source=paper_dict.get("source", ""),
            status="pending"
        )
        session.add(new_paper)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[!] Error adding paper {paper_dict.get('paper_id')}: {e}")
        return False
    finally:
        session.close()

def update_analysis(paper_id, analysis_dict):
    """Update analysis results for a paper and set status to analyzed or failed."""
    session = get_session()
    try:
        paper = session.query(Literature).filter(Literature.paper_id == paper_id).first()
        if not paper:
            return False
            
        paper.status = analysis_dict.get("status", "analyzed")
        paper.analyzed_at = datetime.now().isoformat()
        
        if paper.status == "analyzed":
            paper.llm_summary = analysis_dict.get("llm_summary", "")
            paper.code_available = analysis_dict.get("code_available", "UNKNOWN")
            paper.code_url = analysis_dict.get("code_url", "")
            paper.data_available = analysis_dict.get("data_available", "UNKNOWN")
            paper.data_url = analysis_dict.get("data_url", "")
            paper.theory_assumptions = analysis_dict.get("theory_assumptions", "")
            paper.exp_motivation = analysis_dict.get("exp_motivation", "")
            paper.sota_comparison = analysis_dict.get("sota_comparison", "")
            paper.raw_analysis = analysis_dict.get("raw_analysis", "")
            
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[!] Error updating analysis for {paper_id}: {e}")
        return False
    finally:
        session.close()

def get_pending_papers():
    """Retrieve all papers with status='pending'."""
    session = get_session()
    try:
        return session.query(Literature).filter(Literature.status == "pending").all()
    finally:
        session.close()

def get_all_papers(status=None, source=None, limit=None):
    """Retrieve papers with optional filters and sorting."""
    session = get_session()
    try:
        query = session.query(Literature)
        if status:
            query = query.filter(Literature.status == status)
        if source:
            query = query.filter(Literature.source == source)
            
        # Order by published_date descending
        query = query.order_by(Literature.published_date.desc())
        
        if limit:
            query = query.limit(limit)
            
        return query.all()
    finally:
        session.close()

def delete_paper(paper_id):
    """Delete a paper by paper_id."""
    session = get_session()
    try:
        paper = session.query(Literature).filter(Literature.paper_id == paper_id).first()
        if paper:
            session.delete(paper)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"[!] Error deleting paper {paper_id}: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
