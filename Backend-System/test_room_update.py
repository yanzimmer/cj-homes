# 该文件负责验证房间信息更新接口及数据库写入结果是否正确。
import requests
import json
import sqlite3

BASE_URL = "http://127.0.0.1:5000/api"

def test_room_update_flow():
    print("Running room update tests...")

    # 1. Login to get token
    login_url = f"{BASE_URL}/login"
    try:
        resp = requests.post(login_url, json={"username": "admin", "password": "password"}) # default password is 'password' in init script? Wait, let me check init script again.
        # init script says: sha256(password) and default is 123456 in create_default_admin argument default.
        # But wait, did I run create_default_admin with defaults?
        # Yes, usually.
        # Let's try '123456'.
        if resp.status_code != 200:
             resp = requests.post(login_url, json={"username": "admin", "password": "123456"})

        if resp.status_code != 200:
            print(f"Login failed. Status: {resp.status_code}, Body: {resp.text}")
            return

        token = resp.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

    except Exception as e:
        print(f"Login exception: {e}")
        return

    # 2. Test Image Upload
    print("Testing image field update...")
    
    # Create a test room first
    new_room = {
        "room_no": "Test999",
        "floor": "99楼",
        "room_type": "Single",
        "price": 1000,
        "building": "C栋",
        "water_meter_img": "data:image/png;base64,fakeimagecontent1",
        "electricity_meter_img": "data:image/png;base64,fakeimagecontent2"
    }
    
    try:
        # Create
        response = requests.post(f"{BASE_URL}/rooms", json=new_room, headers=headers)
        if response.status_code == 200 or response.status_code == 201:
            # Note: add_room returns 200 or 201? Code says 200 with json.
            room_id = response.json().get('id')
            print(f"Created test room with ID: {room_id}")
            
            # Verify fields
            response = requests.get(f"{BASE_URL}/rooms", headers=headers)
            rooms = response.json()['rooms']
            target_room = next((r for r in rooms if r['room_no'] == "Test999"), None)
            
            if target_room:
                if (target_room.get('water_meter_img') == new_room['water_meter_img'] and 
                    target_room.get('electricity_meter_img') == new_room['electricity_meter_img']):
                    print("PASS: Create with Image fields saved and retrieved successfully.")
                else:
                    print(f"FAIL: Create with Image fields mismatch. Got: {target_room.get('water_meter_img')}")
            else:
                print("FAIL: Created room not found in list.")
                
            # 3. Test Update
            update_payload = {
                "room_type": "Double",
                "water_meter_img": "data:image/png;base64,UPDATED_WATER_IMG",
                "electricity_meter_img": "data:image/png;base64,UPDATED_ELEC_IMG"
            }
            # The API uses room_no in URL
            response = requests.put(f"{BASE_URL}/rooms/Test999", json=update_payload, headers=headers)
            print(f"Update response status: {response.status_code}")
            
            if response.status_code == 200:
                 # Verify Update
                response = requests.get(f"{BASE_URL}/rooms", headers=headers)
                rooms = response.json()['rooms']
                target_room = next((r for r in rooms if r['room_no'] == "Test999"), None)
                if target_room:
                    if (target_room.get('water_meter_img') == update_payload['water_meter_img']):
                         print("PASS: Update Image fields saved successfully.")
                    else:
                         print(f"FAIL: Update Image fields mismatch. Got: {target_room.get('water_meter_img')}")
            else:
                print(f"FAIL: Update failed. {response.text}")

            # Clean up
            requests.delete(f"{BASE_URL}/rooms/{room_id}", headers=headers)
            print("Test room deleted.")
            
        else:
            print(f"FAIL: Create room failed. Status: {response.status_code}, Body: {response.text}")

    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_room_update_flow()
