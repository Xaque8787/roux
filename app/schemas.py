from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    hourly_wage: Optional[float] = 15.0
    is_admin: bool = False
    is_user: bool = True

class UserOut(BaseModel):
    id: int
    username: str
    hourly_wage: float
    is_admin: bool
    is_user: bool

    class Config:
        from_attributes = True

# Category schemas
class CategoryCreate(BaseModel):
    name: str
    type: str

class CategoryOut(CategoryCreate):
    id: int

    class Config:
        from_attributes = True

# Ingredient schemas
class IngredientCreate(BaseModel):
    name: str
    unit: str
    unit_cost: float
    category_id: Optional[int] = None

class IngredientOut(IngredientCreate):
    id: int

    class Config:
        from_attributes = True

# Recipe schemas
class RecipeIngredientCreate(BaseModel):
    ingredient_id: int
    quantity: float

class RecipeCreate(BaseModel):
    name: str
    instructions: Optional[str] = None
    category_id: Optional[int] = None
    ingredients: List[RecipeIngredientCreate] = []

class RecipeOut(BaseModel):
    id: int
    name: str
    instructions: Optional[str]
    category_id: Optional[int]

    class Config:
        from_attributes = True

# Batch schemas
class BatchCreate(BaseModel):
    recipe_id: int
    yield_amount: float
    yield_unit_id: int
    estimated_labor_minutes: int
    hourly_labor_rate: float = 16.75
    can_be_broken_down: Optional[bool] = False
    can_be_scaled: Optional[bool] = False
    scale_double: Optional[bool] = False
    scale_triple: Optional[bool] = False
    scale_quadruple: Optional[bool] = False
    scale_half: Optional[bool] = False
    scale_quarter: Optional[bool] = False
    scale_eighth: Optional[bool] = False
    scale_sixteenth: Optional[bool] = False

class BatchOut(BatchCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Dish schemas
class DishBatchPortionCreate(BaseModel):
    batch_id: int
    portion_size: float

class DishCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    sale_price: float
    description: Optional[str] = None
    batch_portions: List[DishBatchPortionCreate] = []

class DishOut(BaseModel):
    id: int
    name: str
    category_id: Optional[int]
    sale_price: float
    description: Optional[str]

    class Config:
        from_attributes = True

# Inventory schemas
class InventoryItemCreate(BaseModel):
    name: str
    category_id: Optional[int] = None
    par_level: float = 0.0

class InventoryDayCreate(BaseModel):
    date: date
    employees_working: List[int]

class TaskCreate(BaseModel):
    day_id: int
    assigned_to_id: int
    description: str

# Utility schemas
class UtilityCostCreate(BaseModel):
    name: str
    monthly_cost: float

class UtilityCostOut(UtilityCostCreate):
    id: int
    last_updated: datetime

    class Config:
        from_attributes = True