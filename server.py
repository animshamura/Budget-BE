from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import pandas as pd
import os

# Database setup
DATABASE_URL = "postgresql://postgres.fmxcnjdfhqyadszkbums:1234@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
#DATABASE_URL = "postgresql://budget_user:1234@localhost/bud"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class SubsidiaryBudget(Base):
    __tablename__ = "subsidiary_budgets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    allocated_budget = Column(Float, nullable=False)
    used_budget = Column(Float, default=0.0)
    remaining_budget = Column(Float, nullable=False)

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"extend_existing": True} 
    id = Column(Integer, primary_key=True, index=True)
    t_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)
    subsidiary_id = Column(String, nullable=False)
    sector = Column(String, nullable=False)
    user_id = Column(String, nullable=False)

class SectorSpending(Base):
    __tablename__ = "sector_spendings"
    id = Column(Integer, primary_key=True, index=True)
    sector = Column(String, unique=True, nullable=False)
    allocated_budget = Column(Float, nullable=False)
    remaining_budget = Column(Float, nullable=False)
    total_spent = Column(Float, nullable=False)

# FastAPI App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def load_data_from_csv(db: Session):
    file_path = "budget_data.csv"
    if not os.path.exists(file_path):
        print("⚠️ CSV file not found. Skipping data load.")
        return

    df = pd.read_csv(file_path)
    print("CSV Columns:", df.columns.tolist())
    print("First 5 Rows:\n", df.head())
    
    transactions = [
        Transaction(
            t_id=row["Transaction_ID"].strip(),
            amount=row["Spent_Amount"],
            date=datetime.strptime(row["Date"], "%Y-%m-%d"),
            subsidiary_id=row["Subsidiary"].strip(),
            sector=row["Sector"].strip(),
            user_id=row["User_ID"].strip()
        )
        for _, row in df.iterrows()
    ]
    db.bulk_save_objects(transactions)
    db.commit()

    for _, row in df.groupby("Subsidiary").sum().reset_index().iterrows():
        existing_budget = db.query(SubsidiaryBudget).filter_by(name=row['Subsidiary']).first()
        if not existing_budget:
            subsidiary = SubsidiaryBudget(
                name=row["Subsidiary"].strip(),
                allocated_budget=row["Allocated_Budget"],
                used_budget=row["Spent_Amount"],
                remaining_budget=row["Remaining_Budget"]
            )
            db.add(subsidiary)
    db.commit()

    # Add sector spending aggregation
    
    for _, row in df.groupby("Sector").sum().reset_index().iterrows():
        existing_sector = db.query(SectorSpending).filter_by(sector=row['Sector']).first()
        if not existing_sector:
            sector_spending = SectorSpending(
                sector=row["Sector"].strip(),
                allocated_budget=row["Allocated_Budget"],
                remaining_budget=row["Remaining_Budget"],
                total_spent=row["Spent_Amount"]
            )
            db.add(sector_spending)
    
    db.commit()
    print("✅ Data successfully loaded into database!")

        
@app.get("/subsidiaries/")
def get_subsidiaries(db: Session = Depends(get_db)):
    return db.query(SubsidiaryBudget).all()

@app.get("/transactions/")
def get_transactions(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    transactions = db.query(Transaction).offset(skip).limit(limit).all()
    total_count = db.query(Transaction).count()
    return {"transactions": transactions, "total_count": total_count}



@app.get("/sector_spendings/")
def get_sector_spendings(db: Session = Depends(get_db)):
    return db.query(SectorSpending).all()

# Initialize Database
print("🔄 Creating database tables if they don't exist...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db_session = SessionLocal()
print("📥 Loading data from CSV...")
load_data_from_csv(db_session)
db_session.close()
print("✅ Initialization complete!")
