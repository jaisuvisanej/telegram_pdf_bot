from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.database.connection import Base

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    settings = relationship("UserSetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    pdfs = relationship("UploadedPDF", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")

class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True)
    preferred_language = Column(String, default="Auto")
    max_questions_limit = Column(Integer, default=5)
    current_pdf_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

class UploadedPDF(Base):
    __tablename__ = "uploaded_pdfs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    char_count = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="pdfs")
    chats = relationship("ChatHistory", back_populates="pdf", cascade="all, delete-orphan")
    questions = relationship("GeneratedQuestion", back_populates="pdf", cascade="all, delete-orphan")
    summary = relationship("GeneratedSummary", back_populates="pdf", uselist=False, cascade="all, delete-orphan")

class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    pdf_id = Column(Integer, ForeignKey("uploaded_pdfs.id", ondelete="CASCADE"), nullable=True)
    role = Column(String, nullable=False)  # "user" or "model"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chats")
    pdf = relationship("UploadedPDF", back_populates="chats")

class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pdf_id = Column(Integer, ForeignKey("uploaded_pdfs.id", ondelete="CASCADE"), nullable=False)
    question_type = Column(String, nullable=False)  # "MCQ", "Flashcard", "QA", "Interview"
    content = Column(JSON, nullable=False)  # JSON list of questions
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pdf = relationship("UploadedPDF", back_populates="questions")

class GeneratedSummary(Base):
    __tablename__ = "generated_summaries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pdf_id = Column(Integer, ForeignKey("uploaded_pdfs.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary_text = Column(Text, nullable=False)
    important_topics = Column(Text, nullable=False)
    explain_like_10 = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    pdf = relationship("UploadedPDF", back_populates="summary")
