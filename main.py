from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Dental Clinic API")

# CORS middleware to allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = "https://rkotnovdbskfanlbbrqd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJrb3Rub3ZkYnNrZmFubGJicnFkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODgyMDI1OSwiZXhwIjoyMDg0Mzk2MjU5fQ.i4saVDPgKtTXn-DbNv0rux9patQl0rR1029t0-XeBFY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    user: dict = None
    access_token: str = None

@app.get("/")
async def root():
    return {"message": "Dental Clinic API is running"}

@app.post("/api/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    try:
        # Authenticate user with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if auth_response.user and auth_response.session:
            return LoginResponse(
                success=True,
                message="Login successful",
                user={
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                    "created_at": str(auth_response.user.created_at) if auth_response.user.created_at else None
                },
                access_token=auth_response.session.access_token
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        # Check for common authentication errors
        if any(keyword in error_message.lower() for keyword in ["invalid", "credentials", "password", "email", "user not found"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during login: {error_message}"
            )

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "dental-clinic-api"}
