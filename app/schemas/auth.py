from pydantic import BaseModel, constr


class SendOTPRequest(BaseModel):
    phone: constr(pattern=r"^\d{10}$")


class VerifyOTPRequest(BaseModel):
    phone: constr(pattern=r"^\d{10}$")
    otp: str
