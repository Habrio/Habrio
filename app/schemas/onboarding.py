from pydantic import BaseModel

class BasicOnboardingRequest(BaseModel):
    name: str
    city: str
    society: str
    role: str
