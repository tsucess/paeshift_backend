from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from ninja import Schema
from pydantic import Field, condecimal, validator
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from decimal import Decimal
from accounts.schemas import UserSchema
from pydantic import BaseModel
from typing import List
# Constants
PAYMENT_METHODS = Literal["paystack", "flutterwave"]
WALLET_TOPUP_METHODS = Literal["card", "bank", "transfer"]


class PaymentOut(BaseModel):
    id: int
    amount: str
    status: str
    created_at: str
    payment_method: str
    reference: str

class PaymentListResponse(BaseModel):
    count: int
    results: List[PaymentOut]

class StandardResponse(BaseModel):
    status: str
    message: str
    data: PaymentListResponse

class VerifyPaymentSchema(BaseModel):
    reference: str


class PaymentVerifyResponse(Schema):
    status: str
    message: str
    data: Optional[dict]



class WalletWithdrawSchema(BaseModel):
    user_id: int = Field(..., description="User ID making the withdrawal")
    amount: Decimal = Field(..., gt=0, description="Amount to withdraw")

# ==
# Base Schema
# ==
class PaymentBaseSchema(Schema):
    """
    Base schema for payment operations containing common fields
    """

    total: condecimal(gt=0, decimal_places=2) = Field(
        ..., description="Transaction amount in Naira"
    )
    reference: str = Field(
        ..., min_length=10, description="Unique transaction reference"
    )


# ==
# Initiate Payment
# ==
class InitiatePaymentSchema(PaymentBaseSchema):
    """
    Schema for initiating payment transactions
    """

    user_id: int = Field(..., description="Associated user ID")
    first_name: str = Field(
        ..., min_length=2, max_length=50, description="Payer's first name"
    )
    last_name: str = Field(
        ..., min_length=2, max_length=50, description="Payer's last name"
    )
    phone: str = Field(
        ...,
        min_length=11,
        max_length=15,
        pattern=r"^[0-9]+$",
        description="Payer's phone number",
    )
    payment_method: PAYMENT_METHODS = Field(
        "paystack", description="Payment gateway processor"
    )

    status: str = "initiated"
    job_id : int 
    

    @validator("phone")
    def validate_phone(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v


# ==
# Payment Response & List
# ==
class PaymentResponseSchema(PaymentBaseSchema):
    """
    Schema for payment transaction responses
    """

    id: int = Field(..., description="Payment record ID")
    user_id: int = Field(..., description="Associated user ID")
    payment_method: PAYMENT_METHODS = Field(..., description="Used payment method")
    status: str = Field(
        ...,
        description="Current payment status",
        examples=["pending", "completed", "failed"],
    )
    created_at: datetime = Field(..., description="Transaction timestamp")
    service_fee: condecimal(ge=0, decimal_places=2) = Field(
        ..., description="Applied service fee amount"
    )
    final_amount: condecimal(gt=0, decimal_places=2) = Field(
        ..., description="Amount after fees"
    )


class PaymentListResponse(Schema):
    """
    Schema for paginated payment lists
    """

    count: int = Field(..., description="Total matching records")
    results: List[PaymentResponseSchema] = Field(
        ..., description="Paginated payment records"
    )


# ==
# Payment Filtering
# ==
class PaymentFilterSchema(Schema):
    """
    Schema for filtering payment records
    """

    user_id: int = Field(..., description="User ID to filter by")
    filter: str = Field(
        "all",
        description="Time period filter",
        examples=["all", "today", "yesterday", "this_week", "last_week", "this_month"],
    )


# ==
# Wallet Transactions
# ==
class WalletTopupSchema(Schema):
    """
    Schema for wallet top-up transactions
    """

    amount: condecimal(gt=0, decimal_places=2) = Field(
        ..., description="Amount to add to wallet balance"
    )
    payment_method: WALLET_TOPUP_METHODS = Field(
        ..., description="Funding method for wallet top-up"
    )
    user: UserSchema = Field(..., description="User performing the top-up")


class TransactionResponse(Schema):
    """
    Standardized transaction response schema
    """

    id: int = Field(..., description="Transaction record ID")
    amount: condecimal(ge=0, decimal_places=2) = Field(...)
    transaction_type: str = Field(
        ...,
        description="Type of transaction",
        examples=["deposit", "withdrawal", "payment"],
    )
    status: str = Field(
        ...,
        description="Current transaction status",
        examples=["pending", "completed", "failed", "reversed"],
    )
    created_at: datetime = Field(..., description="Timestamp of transaction")
    reference: str = Field(
        ..., min_length=10, description="Unique transaction reference"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional transaction details"
    )


# ==
# Verification
# ==
class VerificationResponse(Schema):
    """
    Schema for payment verification responses
    """

    status: str = Field(
        ...,
        description="Verification status",
        examples=["verified", "pending", "failed"],
    )
    new_balance: condecimal(ge=0, decimal_places=2) = Field(
        ..., description="Updated wallet balance"
    )
    payment_id: int = Field(..., description="Verified payment record ID")
    verified_at: datetime = Field(..., description="Timestamp of verification")


class PaymentInitSchema(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount to process")
    callback_url: str = Field(..., description="URL to redirect after payment")
