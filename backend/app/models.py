from __future__ import annotations 
from datetime import datetime

from enum import Enum

from pydantic import BaseModel, Field 

class Segment(BaseModel): 
    id: int
    speaker: str
    start: float
    end: float 
    text: str 

class TranscriptionResult(BaseModel): 
    """Provider output before meeting metadata is attached"""
    segments: list[Segment]
    language: str | None = None 
    segments: list[Segment]

class Transcript(BaseModel): 
    meeting_id: str
    source_file: str 
    duration_sec: float
    language: str | None = None
    provider: str
    created_at: datetime
    speakers: list[str]
    segments: list[Segment]

class ActionItem(BaseModel): 
    task: str
    owner: str | None = None
    due: str | None = None

class TimelineEntry(BaseModel): 
    start: float
    topic: str 

class Notes(BaseModel): 
    summary: str
    action_items: list[ActionItem] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    topic_timeline: list[TimelineEntry] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

class StoredNotes(Notes): 
    meeting_id: str
    model: str
    generated_at: datetime

class JobStatus(str, Enum): 
    pending = "pending"
    extracting = "extracting"
    transcribing = "transcribing"
    transcribed = "transcribed"
    generating_notes = "generating_notes"
    done = "done"
    failed = "failed"

class Job(BaseModel):
    meeting_id: str
    source_file: str
    vad_trim: bool = False
    status: JobStatus = JobStatus.pending
    stage: str = "pending"
    percent: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime

class QAEntry(BaseModel): 
    question: str
    answer: str
    citations: list[str] = Field(default_factory=list)