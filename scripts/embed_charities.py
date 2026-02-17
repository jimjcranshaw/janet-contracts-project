import sys
import os
import openai
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, settings
from app.models import ServiceProfile

def generate_embeddings():
    db = SessionLocal()
    client = openai.Client(api_key=settings.OPENAI_API_KEY)
    
    charities = db.query(ServiceProfile).filter(ServiceProfile.profile_embedding == None).all()
    print(f"Generating embeddings for {len(charities)} charities...")
    
    for c in charities:
        text = f"{c.name} {c.mission} {c.vision} {c.programs_services} {c.target_population}"
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        c.profile_embedding = response.data[0].embedding
        print(f"✓ {c.name}")
    
    db.commit()
    db.close()

if __name__ == "__main__":
    generate_embeddings()
