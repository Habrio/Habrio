# --- models/user.py ---
from models import db
from datetime import datetime

# --- OTP Model ---
class OTP(db.Model):
    __tablename__ = "otp"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)

    
    def __repr__(self):
        return f"<OTP phone={self.phone} otp={self.otp}>"

# --- User Profile Model ---

class UserProfile(db.Model):
    __tablename__ = "user_profile"

    phone = db.Column(db.String(15), primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    society = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=True)
    basic_onboarding_done = db.Column(db.Boolean, default=False)
    role_onboarding_done = db.Column(db.Boolean, default=False)
    auth_token = db.Column(db.String(64), unique=True)
    device_info = db.Column(db.String(300), nullable=True) 
    token_created_at = db.Column(db.DateTime, default=datetime.utcnow)
    kyc_status = db.Column(db.String, default="pending")

    def __repr__(self):
        return f"<User phone={self.phone} role={self.role}>"

 # Consumer Profile------------

class ConsumerProfile(db.Model):
    __tablename__ = "consumer_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(15), db.ForeignKey("user_profile.phone"), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    society = db.Column(db.String(100), nullable=False)
    flat_number = db.Column(db.String(50), nullable=True)
    profile_image_url = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    preferred_language = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.user_phone,
            "city": self.city,
            "society": self.society,
            "flat_number": self.flat_number,
            "profile_image_url": self.profile_image_url,
            "gender": self.gender,
            "date_of_birth": str(self.date_of_birth) if self.date_of_birth else None,
            "preferred_language": self.preferred_language
        }
