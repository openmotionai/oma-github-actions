#!/usr/bin/env python3
"""
Test file to demonstrate Claude's PR-from-PR functionality.
This file contains intentional issues that Claude can fix via @claude commands.
"""

import os
import sys

def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    # BUG: Division by zero not handled
    total = sum(numbers)
    return total / len(numbers)

def validate_email(email):
    """Validate email format."""
    # BUG: Very basic validation, missing many edge cases
    if "@" in email:
        return True
    return False

def process_user_data(users):
    """Process a list of user dictionaries."""
    results = []
    for user in users:
        # BUG: KeyError not handled if 'name' or 'email' missing
        name = user['name']
        email = user['email']
        
        if validate_email(email):
            results.append({
                'name': name,
                'email': email,
                'status': 'valid'
            })
        else:
            results.append({
                'name': name,
                'email': email,
                'status': 'invalid'
            })
    
    return results

def main():
    """Main function to test the functionality."""
    # Test data with potential issues
    test_numbers = [1, 2, 3, 4, 5]
    empty_numbers = []  # This will cause division by zero
    
    test_users = [
        {'name': 'John Doe', 'email': 'john@example.com'},
        {'name': 'Jane Smith', 'email': 'invalid-email'},
        {'name': 'Bob Wilson'},  # Missing email key
    ]
    
    print("Testing calculate_average:")
    print(f"Average of {test_numbers}: {calculate_average(test_numbers)}")
    
    # This will crash due to division by zero
    print(f"Average of empty list: {calculate_average(empty_numbers)}")
    
    print("\nTesting process_user_data:")
    results = process_user_data(test_users)
    for result in results:
        print(f"User: {result['name']}, Email: {result['email']}, Status: {result['status']}")

if __name__ == "__main__":
    main()
