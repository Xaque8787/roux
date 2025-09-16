from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import require_admin, get_current_user, require_manager_or_admin
from ..models import Ingredient, Category, Vendor, VendorUnit
from ..utils.helpers import get_today_date

router = APIRouter(prefix="/ingredients", tags=["ingredients"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def ingredients_page(request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ingredients = db.query(Ingredient).all()
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredients.html", {
        "request": request,
        "current_user": current_user,
        "ingredients": ingredients,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units,
        "today_date": get_today_date()
    })

@router.post("/new")
async def create_ingredient(
    request: Request,
    name: str = Form(...),
    usage_type: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    vendor_unit_id: int = Form(None),
    use_item_count_pricing: bool = Form(False),
    net_weight_volume_item: float = Form(None),
    net_unit: str = Form(...),
    purchase_total_cost: float = Form(None),
    purchase_total_cost_item: float = Form(None),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    net_weight_volume_case: float = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: str = Form(None),
    baking_weight_amount: float = Form(None),
    baking_weight_unit: str = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    # Validate required fields based on pricing type
    if not use_item_count_pricing:
        if net_weight_volume_item is None:
            raise HTTPException(status_code=400, detail="Net weight/volume per item is required when not using item count pricing")
        if not net_unit:
            raise HTTPException(status_code=400, detail="Net unit is required when not using item count pricing")
        if purchase_total_cost is None:
            raise HTTPException(status_code=400, detail="Purchase total cost is required when not using item count pricing")
    else:
        if purchase_total_cost_item is None:
            raise HTTPException(status_code=400, detail="Purchase total cost is required when using item count pricing")
    
    # Use the appropriate cost field based on pricing type
    final_purchase_cost = purchase_total_cost_item if use_item_count_pricing else purchase_total_cost
    
    ingredient = Ingredient(
        name=name,
        usage_type=usage_type,
        category_id=category_id if category_id else None,
        vendor_id=vendor_id if vendor_id else None,
        vendor_unit_id=vendor_unit_id if vendor_unit_id else None,
        purchase_type=purchase_type,
        purchase_unit_name=purchase_unit_name,
        purchase_total_cost=final_purchase_cost,
        breakable_case=breakable_case,
        use_item_count_pricing=use_item_count_pricing,
        net_weight_volume_item=net_weight_volume_item if not use_item_count_pricing else None,
        net_unit=net_unit if not use_item_count_pricing else None,
        has_baking_conversion=has_baking_conversion
    )
    
    # Handle case-specific fields
    if purchase_type == "case":
        ingredient.items_per_case = items_per_case
        if not use_item_count_pricing:
            ingredient.net_weight_volume_case = (net_weight_volume_item * items_per_case if items_per_case and net_weight_volume_item else None)
        else:
            ingredient.net_weight_volume_case = None
    else:
        # For single items, set case fields to None/default values
        ingredient.items_per_case = None
        if not use_item_count_pricing:
            ingredient.net_weight_volume_case = net_weight_volume_item
        else:
            ingredient.net_weight_volume_case = None
    
    # Handle baking conversion
    if has_baking_conversion and not use_item_count_pricing:
        ingredient.baking_measurement_unit = baking_measurement_unit
        ingredient.baking_weight_amount = baking_weight_amount
        ingredient.baking_weight_unit = baking_weight_unit
    
    db.add(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)

@router.get("/{ingredient_id}", response_class=HTMLResponse)
async def ingredient_detail(ingredient_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    return templates.TemplateResponse("ingredient_detail.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient
    })

@router.get("/{ingredient_id}/edit", response_class=HTMLResponse)
async def ingredient_edit_page(ingredient_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    categories = db.query(Category).filter(Category.type == "ingredient").all()
    vendors = db.query(Vendor).all()
    vendor_units = db.query(VendorUnit).all()
    
    return templates.TemplateResponse("ingredient_edit.html", {
        "request": request,
        "current_user": current_user,
        "ingredient": ingredient,
        "categories": categories,
        "vendors": vendors,
        "vendor_units": vendor_units
    })

@router.post("/{ingredient_id}/edit")
async def update_ingredient(
    ingredient_id: int,
    request: Request,
    name: str = Form(...),
    category_id: int = Form(None),
    vendor_id: int = Form(None),
    purchase_type: str = Form(...),
    purchase_unit_name: str = Form(...),
    vendor_unit_id: int = Form(None),
    use_item_count_pricing: bool = Form(False),
    net_weight_volume_item: float = Form(None),
    net_unit: str = Form(None),
    purchase_total_cost: float = Form(None),
    purchase_total_cost_item: float = Form(None),
    breakable_case: bool = Form(False),
    items_per_case: int = Form(None),
    net_weight_volume_case: float = Form(None),
    has_baking_conversion: bool = Form(False),
    baking_measurement_unit: str = Form(None),
    baking_weight_amount: float = Form(None),
    baking_weight_unit: str = Form(None),
    uses_price_per_weight_volume: bool = Form(False),
    price_per_weight_volume: float = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    # Validate required fields based on pricing type
    if not use_item_count_pricing:
        if net_weight_volume_item is None:
            raise HTTPException(status_code=400, detail="Net weight/volume per item is required when not using item count pricing")
        if not net_unit:
            raise HTTPException(status_code=400, detail="Net unit is required when not using item count pricing")
        if purchase_total_cost is None:
            raise HTTPException(status_code=400, detail="Purchase total cost is required when not using item count pricing")
    else:
        if purchase_total_cost_item is None:
            raise HTTPException(status_code=400, detail="Purchase total cost is required when using item count pricing")
    
    # Use the appropriate cost field based on pricing type
    final_purchase_cost = purchase_total_cost_item if use_item_count_pricing else purchase_total_cost
    
    ingredient.name = name
    ingredient.category_id = category_id if category_id else None
    ingredient.vendor_id = vendor_id if vendor_id else None
    ingredient.vendor_unit_id = vendor_unit_id if vendor_unit_id else None
    ingredient.purchase_type = purchase_type
    ingredient.purchase_unit_name = purchase_unit_name
    ingredient.purchase_total_cost = final_purchase_cost
    ingredient.breakable_case = breakable_case
    ingredient.use_item_count_pricing = use_item_count_pricing
    ingredient.net_weight_volume_item = net_weight_volume_item if not use_item_count_pricing else None
    ingredient.net_unit = net_unit if not use_item_count_pricing else None
    ingredient.has_baking_conversion = has_baking_conversion
    ingredient.uses_price_per_weight_volume = uses_price_per_weight_volume
    ingredient.price_per_weight_volume = price_per_weight_volume if uses_price_per_weight_volume else None
    
    # Handle case-specific fields
    if purchase_type == "case":
        ingredient.items_per_case = items_per_case
        if not use_item_count_pricing:
            ingredient.net_weight_volume_case = (net_weight_volume_item * items_per_case if items_per_case and net_weight_volume_item else None)
        else:
            ingredient.net_weight_volume_case = None
    else:
        if not use_item_count_pricing:
            ingredient.net_weight_volume_case = net_weight_volume_item
        else:
            ingredient.net_weight_volume_case = None
        ingredient.items_per_case = None
    
    # Handle baking conversion
    if has_baking_conversion and not use_item_count_pricing:
        ingredient.baking_measurement_unit = baking_measurement_unit
        ingredient.baking_weight_amount = baking_weight_amount
        ingredient.baking_weight_unit = baking_weight_unit
        ingredient.uses_price_per_weight_volume = uses_price_per_weight_volume
        ingredient.price_per_weight_volume = price_per_weight_volume if uses_price_per_weight_volume else None
    else:
        ingredient.baking_measurement_unit = None
        ingredient.baking_weight_amount = None
        ingredient.baking_weight_unit = None
    
    db.commit()
    
    return RedirectResponse(url=f"/ingredients/{ingredient_id}", status_code=302)

@router.get("/{ingredient_id}/delete")
async def delete_ingredient(ingredient_id: int, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    
    return RedirectResponse(url="/ingredients", status_code=302)