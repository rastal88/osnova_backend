from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.example import Example

router = APIRouter()

@router.get("/examples/")
def read_examples(db: Session = Depends(get_db)):
    examples = db.query(Example).all()
    return examples
