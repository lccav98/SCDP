from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import DB_PATH
from datetime import datetime

engine = create_engine(f"sqlite:///{DB_PATH}")
Base = declarative_base()
Session = sessionmaker(bind=engine)

class PCDPAnalysis(Base):
    __tablename__ = "pcdp_analysis"
    id = Column(Integer, primary_key=True)
    pcdp_number = Column(String(50), nullable=False)
    proposto = Column(String(200))
    status = Column(String(20))
    analysis_date = Column(DateTime, default=datetime.now)
    inconsistencies = Column(Text)
    financial_data = Column(Text)
    report_json = Column(Text)

def init_db():
    Base.metadata.create_all(engine)
