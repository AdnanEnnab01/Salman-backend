from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from typing import List, Optional
from datetime import date
import os
import json
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
        auth_response = supabase.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )

        if auth_response.user and auth_response.session:
            return LoginResponse(
                success=True,
                message="Login successful",
                user={
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                    "created_at": (
                        str(auth_response.user.created_at)
                        if auth_response.user.created_at
                        else None
                    ),
                },
                access_token=auth_response.session.access_token,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        # Check for common authentication errors
        if any(
            keyword in error_message.lower()
            for keyword in [
                "invalid",
                "credentials",
                "password",
                "email",
                "user not found",
            ]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during login: {error_message}",
            )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "dental-clinic-api"}


# --- Patient Models ---
class PatientCreate(BaseModel):
    name: str
    phone: str
    totalAmount: float


class PaymentCreate(BaseModel):
    amount: float
    notes: Optional[str] = ""


# --- Patient Endpoints ---


@app.get("/api/patients")
async def get_patients():
    # Fetch patients with their payment history using Supabase joins
    res = (
        supabase.table("patients")
        .select("*, payments(*)")
        .order("created_at", desc=True)
        .execute()
    )

    # Format data to match your React state exactly
    formatted_data = []
    for p in res.data:
        formatted_data.append(
            {
                "id": p["id"],
                "name": p["name"],
                "phone": p["phone"],
                "totalAmount": p["total_amount"],
                "paidAmount": p["paid_amount"],
                "remainingAmount": p["remaining_amount"],
                "hasRemainingPayment": p["has_remaining_payment"],
                "paymentHistory": p["payments"],  # Nested list
            }
        )
    return formatted_data


@app.post("/api/patients")
async def add_patient(data: PatientCreate):
    new_patient = {
        "name": data.name,
        "phone": data.phone,
        "total_amount": data.totalAmount,
        "remaining_amount": data.totalAmount,
        "paid_amount": 0,
        "has_remaining_payment": data.totalAmount > 0,
    }
    res = supabase.table("patients").insert(new_patient).execute()
    return res.data[0]


@app.post("/api/patients/{patient_id}/payments")
async def add_payment(patient_id: str, py: PaymentCreate):
    # 1. Insert the payment
    supabase.table("payments").insert(
        {"patient_id": patient_id, "amount": py.amount, "notes": py.notes}
    ).execute()

    # 2. Get current patient data to update totals
    p_res = (
        supabase.table("patients").select("*").eq("id", patient_id).single().execute()
    )
    curr = p_res.data

    new_paid = float(curr["paid_amount"]) + py.amount
    new_rem = float(curr["total_amount"]) - new_paid

    # 3. Update the patient record
    update_res = (
        supabase.table("patients")
        .update(
            {
                "paid_amount": new_paid,
                "remaining_amount": max(0, new_rem),
                "has_remaining_payment": new_rem > 0,
            }
        )
        .eq("id", patient_id)
        .execute()
    )

    return update_res.data[0]


class AppointmentCreate(BaseModel):
    patient_name: str
    phone: str
    appointment_date: date
    appointment_time: str  # Format: "HH:MM"
    procedure: str


# --- Appointment Endpoints ---


@app.get("/api/appointments")
async def get_appointments():
    # Fetch all appointments ordered by date and time
    res = (
        supabase.table("appointments")
        .select("*")
        .order("appointment_date")
        .order("appointment_time")
        .execute()
    )
    return res.data


@app.post("/api/appointments")
async def create_appointment(data: AppointmentCreate):
    new_appointment = {
        "patient_name": data.patient_name,
        "phone": data.phone,
        "appointment_date": str(data.appointment_date),
        "appointment_time": data.appointment_time,
        "procedure": data.procedure,
        "status": "Scheduled",
    }
    res = supabase.table("appointments").insert(new_appointment).execute()
    return res.data[0]


@app.patch("/api/appointments/{appt_id}")
async def update_appointment_status(appt_id: str, status: str):
    res = (
        supabase.table("appointments")
        .update({"status": status})
        .eq("id", appt_id)
        .execute()
    )
    return res.data[0]


@app.delete("/api/appointments/{appt_id}")
async def delete_appointment(appt_id: str):
    supabase.table("appointments").delete().eq("id", appt_id).execute()
    return {"message": "Deleted successfully"}
