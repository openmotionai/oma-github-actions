#!/usr/bin/env python3
"""
Test file for Claude code review functionality.
This file intentionally contains some issues for testing.
"""

import os
import json

def process_user_data(data):
    # TODO: Add error handling
    user_info = json.loads(data)
    
    # Potential security issue - no input validation
    username = user_info['username']
    password = user_info['password']
    
    # Hardcoded database connection (bad practice)
    db_host = "localhost"
    db_password = "admin123"
    
    # No error handling for file operations
    with open(f"/tmp/{username}.log", "w") as f:
        f.write(f"User {username} logged in")
    
    return True

def calculate_discount(price, user_type):
    # Logic could be clearer
    if user_type == "premium":
        return price * 0.8
    elif user_type == "regular":
        return price * 0.9
    else:
        return price

# Main execution
if __name__ == "__main__":
    # Sample data (should probably come from command line or config)
    sample_data = '{"username": "testuser", "password": "secret123"}'
    
    result = process_user_data(sample_data)
    print(f"Result: {result}")
    
    # Test discount calculation
    price = 100.0
    discount_price = calculate_discount(price, "premium")
    print(f"Discounted price: ${discount_price}") 