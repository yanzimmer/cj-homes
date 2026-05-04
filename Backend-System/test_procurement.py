import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000/api/procurements"

def test_procurement_flow():
    print("Running procurement API tests...")

    # 1. Test Create
    new_item = {
        "procurement_date": datetime.now().strftime("%Y-%m-%d"),
        "item_name": "Test Item",
        "specification": "Test Spec",
        "quantity": 10,
        "unit": "pcs",
        "total_amount": 100.50,
        "remarks": "Test Remark"
    }
    
    try:
        response = requests.post(BASE_URL, json=new_item)
        print(f"Create response status: {response.status_code}")
        print(f"Create response body: {response.text}")
        
        if response.status_code == 201:
            item_id = response.json()['id']
            print(f"Created item with ID: {item_id}")
            
            # 2. Test List
            response = requests.get(BASE_URL)
            print(f"List response status: {response.status_code}")
            items = response.json()['procurements']
            found = any(item['id'] == item_id for item in items)
            print(f"Item found in list: {found}")
            
            # 3. Test Update
            update_item = new_item.copy()
            update_item['item_name'] = "Updated Test Item"
            response = requests.put(f"{BASE_URL}/{item_id}", json=update_item)
            print(f"Update response status: {response.status_code}")
            
            # 4. Test Delete
            response = requests.delete(f"{BASE_URL}/{item_id}")
            print(f"Delete response status: {response.status_code}")
            
        else:
            print("Create failed, skipping other tests.")

    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_procurement_flow()
