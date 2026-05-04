from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel
from typing import List
import os
import joblib
import base64
import io

# EMAIL IMPORTS
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

# Import your local modules
from models import UserCreate, UserLogin, ForgotPasswordRequest
from auth import create_user, authenticate_user, hash_password
from database import users_collection, db 

app = FastAPI()

# Collections
reviews_collection = db["reviews"]
orders_collection = db["orders"] 
predict_collection = db["predictions"]  # New: Stores user search history
model_collection = db["models"]      # New: Stores the .joblib file binary

# ==========================================
# ML MODEL MANAGEMENT (MONGO + LOADING)
# ==========================================

def upload_model_to_mongo():
    """Run once to push local file to MongoDB"""
    try:
        model_path = os.path.join("models_ml", "busy_level_pipeline.joblib")
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode('utf-8')
            model_collection.update_one(
                {"name": "busy_predictor"},
                {"$set": {"data": encoded_string}},
                upsert=True
            )
            print("✅ Model synced from local file to MongoDB!")
    except Exception as e:
        print(f"⚠️ Initial upload notice: {e}")

def load_busy_model():
    """Loads model directly from MongoDB binary data"""
    try:
        model_doc = model_collection.find_one({"name": "busy_predictor"})
        if model_doc:
            model_bytes = base64.b64decode(model_doc["data"])
            model = joblib.load(io.BytesIO(model_bytes))
            print("✅ ML Model loaded successfully from MongoDB!")
            return model
        return None
    except Exception as e:
        print(f"❌ Failed to load model from DB: {e}")
        return None

# Perform sync and then load
upload_model_to_mongo()
busy_model = load_busy_model()

# =========================
# EMAIL CONFIGURATION
# =========================
conf = ConnectionConfig(
    MAIL_USERNAME = "begad.ahmed124@gmail.com",
    MAIL_PASSWORD = "wdxe eblu mnbi clms", 
    MAIL_FROM = "begad.ahmed124@gmail.com",
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# =========================
# SCHEMAS
# =========================
class ProfileUpdate(BaseModel):
    bio: str
    birthday: str
    favorite_drink: str

class ReviewCreate(BaseModel):
    text: str

class OrderItem(BaseModel):
    item_name: str
    unit_price: float
    qty: int
    size: str = None

class OrderCreate(BaseModel):
    email: str
    items: List[OrderItem]
    total_price: float

class PredictionInput(BaseModel):
    time: str
    day_type: str
    group_type: str

# =========================
# CORS SETUP
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# EMAIL HELPER FUNCTION
# =========================
async def send_order_email(user_email: str, order_details: dict):
    # Professional Table-based Item Row
    items_html = "".join([
        f"""
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 15px; border-bottom: 1px solid #333; padding-bottom: 10px;">
            <tr>
                <td style="text-align: left; vertical-align: top;">
                    <div style="font-weight: bold; color: #ffffff; font-size: 16px;">{item['qty']}x {item['item_name']}</div>
                    <div style="color: #a0aec0; font-size: 13px; margin-top: 4px;">Size: {item['size'] or 'Standard'}</div>
                </td>
                <td style="text-align: right; vertical-align: top; white-space: nowrap;">
                    <div style="color: #63b3ed; font-weight: bold; font-size: 16px; margin-left: 20px;">
                        {item['unit_price'] * item['qty']} EGP
                    </div>
                </td>
            </tr>
        </table>
        """ 
        for item in order_details['items']
    ])

    # Body with fixed spacing for Total Amount
    html_content = f"""
    <html>
    <body style="background-color: #121212; margin: 0; padding: 20px; font-family: Arial, sans-serif;">
        <div style="max-width: 450px; margin: 0 auto; background-color: #1e1e1e; border-radius: 15px; overflow: hidden; border: 1px solid #333;">
            <div style="background-color: #d1d5db; padding: 25px; text-align: center;">
                <h1 style="margin: 0; color: #000; letter-spacing: 2px; font-size: 24px;">JACKELS CAFE</h1>
                <p style="margin: 5px 0 0; color: #444; font-size: 12px; text-transform: uppercase;">Order Confirmation</p>
            </div>
            <div style="padding: 30px;">
                <p style="color: #e2e8f0; font-size: 15px;">Hi there,</p>
                <p style="color: #a0aec0; font-size: 14px; line-height: 1.5;">Your order has been received and is currently being prepared by our baristas.</p>
                
                <p style="color: #718096; font-size: 11px; font-weight: bold; text-transform: uppercase; margin: 25px 0 15px;">Your Items</p>
                
                {items_html}

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 20px;">
                    <tr>
                        <td style="text-align: left; font-size: 18px; font-weight: bold; color: #ffffff;">Total Amount</td>
                        <td style="text-align: right; font-size: 20px; font-weight: bold; color: #63b3ed;">{order_details['total_price']} EGP</td>
                    </tr>
                </table>
            </div>
            <div style="background-color: #171717; padding: 20px; text-align: center; color: #718096; font-size: 11px;">
                <p style="margin: 0;">Jackels Cafe | Alexandria, Egypt</p>
                <p style="margin: 5px 0 0;">Thank you for your visit!</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="☕ Your Jackels Cafe Receipt",
        recipients=[user_email],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)

# =========================
# ML PREDICTION ROUTE
# =========================
@app.post("/predict-busy-level")
def predict_busy_level(data: PredictionInput):
    if not busy_model:
        raise HTTPException(status_code=500, detail="ML Model not available")
    
    try:
        # 1. Format for Model
        formatted_time = f"{int(data.time):02d}:00"
        input_df = pd.DataFrame([{
            "time": formatted_time,
            "day_type": data.day_type.lower(),
            "group_type": "alone" if data.group_type == "solo" else "group"
        }])
        
        # 2. Predict
        prediction_result = busy_model.predict(input_df)[0]
        
        # 3. Store prediction history in Mongo
        predict_collection.insert_one({
            "time_requested": formatted_time,
            "day_type": data.day_type,
            "group_type": data.group_type,
            "result": str(prediction_result),
            "timestamp": pd.Timestamp.now()
        })
        
        return {"busy_level": str(prediction_result)}
        
    except Exception as e:
        print(f"❌ ML ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# ONLINE ORDERING & HISTORY
# =========================

@app.get("/menu")
def get_menu():
    try:
        path = os.path.join("data", "menujackels.csv")
        if not os.path.exists(path):
            return []
        df = pd.read_csv(path)
        df = df.fillna({"unit_price": 0, "size": "Standard"})
        active_menu = df[df["is_active"] == 1]
        return active_menu.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading menu: {str(e)}")

@app.post("/place-order")
async def place_order(order: OrderCreate):
    try:
        order_dict = order.dict()
        result = orders_collection.insert_one(order_dict)
        
        try:
            await send_order_email(order.email, order_dict)
            email_status = "Email sent"
        except Exception as email_err:
            print(f"📧 Email Error: {email_err}")
            email_status = "Email failed"

        return {
            "message": "Order placed successfully!", 
            "email_status": email_status,
            "order_id": str(result.inserted_id)
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/my-orders/{email}")
def get_my_orders(email: str):
    try:
        orders = list(orders_collection.find({"email": email}).sort("_id", -1))
        for order in orders:
            order["_id"] = str(order["_id"])
        return orders
    except Exception as e:
        print(f"❌ Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch order history")

# =========================
# ANALYTICS
# =========================
@app.get("/analytics/top-items")
def top_items():
    df = pd.read_csv("results/top_10_items.csv")
    return df.to_dict(orient="records")

@app.get("/analytics/top-revenue-items")
def top_revenue_items():
    df = pd.read_csv("results/top_10_revenue_items.csv")
    return df.to_dict(orient="records")

@app.get("/analytics/customer-behavior")
def customer_behavior():
    data = [
        {"metric": "Average visit duration", "value": "45 minutes"},
        {"metric": "New customers this month", "value": 120},
        {"metric": "Returning customer rate", "value": "65%"}
    ]
    return data

# =========================
# AUTH & PROFILE
# =========================
@app.post("/signup")
def signup(user: UserCreate):
    try:
        create_user(user.dict())
        return {"message": "User created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
def login(user: UserLogin):
    db_user = authenticate_user(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"message": "Login successful", "user": {"name": db_user["name"], "email": db_user["email"]}}

@app.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    user = users_collection.find_one({"email": data.email})
    if not user: raise HTTPException(status_code=404, detail="Email not found")
    users_collection.update_one({"email": data.email}, {"$set": {"password": hash_password(data.new_password)}})
    return {"message": "Password updated successfully"}

@app.get("/profile/{email}")
def get_profile(email: str):
    user = users_collection.find_one({"email": email}, {"password": 0})
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"])
    return user

@app.put("/update-profile/{email}")
def update_profile(email: str, data: ProfileUpdate):
    result = users_collection.update_one({"email": email}, {"$set": data.dict()})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Profile updated successfully"}

@app.delete("/delete/{email}")
def delete_user(email: str):
    result = users_collection.delete_one({"email": email})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

@app.post("/add-review")
def add_review(review: ReviewCreate):
    reviews_collection.insert_one({"review_text": review.text, "status": "anonymous"})
    return {"message": "Review sent anonymously!"}
@app.get("/prediction-history")
def get_prediction_history():
    try:
        # Get last 10 predictions, sorted by most recent
        history = list(db["predictions"].find().sort("_id", -1).limit(10))
        for item in history:
            item["_id"] = str(item["_id"]) # Convert MongoDB ID to string
        return history
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        raise HTTPException(status_code=500, detail="Could not load history")
    