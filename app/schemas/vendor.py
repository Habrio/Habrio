from pydantic import BaseModel, Field
from typing import Optional

class VendorProfileRequest(BaseModel):
    business_type: str
    business_name: str
    address: str
    gst_number: Optional[str] = None

class AddItemRequest(BaseModel):
    title: str
    price: float
    brand: Optional[str] = None
    description: Optional[str] = ""
    mrp: Optional[float] = None
    discount: Optional[float] = None
    quantity_in_stock: int = Field(default=100, ge=0)
    unit: str = "pcs"
    pack_size: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    sku: Optional[str] = None
    expiry_date: Optional[str] = None
    image_url: Optional[str] = None


class VendorDocumentRequest(BaseModel):
    document_type: str
    file_url: str


class PayoutSetupRequest(BaseModel):
    bank_name: str
    account_number: str
    ifsc_code: str
