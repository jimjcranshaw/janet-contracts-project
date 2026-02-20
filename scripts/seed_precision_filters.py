import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def seed_filters():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set!")
        return
        
    engine = create_engine(url)
    
    exclusions = {
        "Nacro": ["cleaning", "drones", "orthopaedic", "defence", "military", "window cleaning", "school cleaning"],
        "Shelter, National Campaign For Homeless People Limited": ["children’s activities", "occupational health", "holiday activity", "food programme", "sensory support"],
        "Mind (The National Association For Mental Health)": ["weight management", "sensory support", "obesity", "sight impairment", "hearing impairment"],
        "The Charities Aid Foundation": ["drone", "military", "defence", "welfare rights", "interception"]
    }
    
    with engine.connect() as conn:
        for name, keywords in exclusions.items():
            print(f"Updating {name} with {len(keywords)} exclusion keywords...")
            query = text("""
                UPDATE service_profile 
                SET exclusion_keywords = :keywords 
                WHERE name = :name
            """)
            conn.execute(query, {"keywords": keywords, "name": name})
        conn.commit()
    print("Seeding complete.")

if __name__ == "__main__":
    seed_filters()
