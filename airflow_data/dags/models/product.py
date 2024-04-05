from uuid import uuid4

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    wmo_collective_id: str | None = Field(alias="wmoCollectiveId", default=None)
    issuing_office: str | None = Field(alias="issuingOffice", default=None)
    issuance_time: str | None = Field(alias="issuanceTime", default=None)
    product_code: str | None = Field(alias="productCode", default=None)
    product_name: str | None = Field(alias="productName", default=None)
    product_text: str | None = Field(alias="productText", default_factory=lambda: str(uuid4()))
