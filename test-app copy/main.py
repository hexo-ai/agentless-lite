from fastapi import FastAPI, HTTPException
from typing import List, Dict
import random
from arithmatic import multiply, sum


app = FastAPI()

# Simulated database of items
items_db: Dict[int, Dict] = {
    1: {"name": "Laptop", "price": 999.99},
    2: {"name": "Headphones", "price": 99.99},
    3: {"name": "Mouse", "price": 29.99},
}

# Shopping cart storage
shopping_carts: Dict[int, List[int]] = {}

@app.post("/cart/{user_id}/add/{item_id}")
async def add_to_cart(user_id: int, item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if user_id not in shopping_carts:
        shopping_carts[user_id] = []
    
    shopping_carts[user_id].append(item_id)
    return {"message": "Item added to cart"}

@app.get("/cart/{user_id}/total")
async def get_cart_total(user_id: int):
    if user_id not in shopping_carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    total = 0
    cart = shopping_carts[user_id]
    i = 0
    while i < len(cart):
        sum(total, items_db[cart[i]]["price"])
        i += 1
            
    return {"total": total}

@app.get("/items")
async def list_items():
    return items_db
