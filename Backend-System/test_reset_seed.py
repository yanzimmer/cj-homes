import requests
import json
import sqlite3

BASE_URL = "http://127.0.0.1:5000/api"

def test_reset_seed_flow():
    print("Running system reset and seed tests...")

    # 1. Login to get token
    login_url = f"{BASE_URL}/login"
    try:
        resp = requests.post(login_url, json={"username": "admin", "password": "password"})
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

    # 2. Reset System (Clear all data except admins)
    print("Resetting system...")
    try:
        response = requests.post(f"{BASE_URL}/system/reset", headers=headers)
        if response.status_code == 200:
            print("System reset successful.")
            
            # Verify data cleared
            # Check rooms count
            resp = requests.get(f"{BASE_URL}/rooms", headers=headers)
            rooms = resp.json()['rooms']
            print(f"Rooms count after reset: {len(rooms)}")
            if len(rooms) == 0:
                print("PASS: Rooms table cleared.")
            else:
                print("FAIL: Rooms table not empty.")
                
        else:
            print(f"FAIL: System reset failed. Status: {response.status_code}, Body: {response.text}")
            return # Stop if reset failed
            
    except Exception as e:
        print(f"Reset exception: {e}")
        return

    # 3. Seed Data (Generate demo data)
    print("Seeding demo data...")
    try:
        response = requests.post(f"{BASE_URL}/system/seed", headers=headers)
        if response.status_code == 200:
            print("Seed data successful.")
            
            # Verify data generated
            # Check rooms
            resp = requests.get(f"{BASE_URL}/rooms", headers=headers)
            rooms = resp.json()['rooms']
            print(f"Rooms count after seed: {len(rooms)}")
            
            # Check tenants
            resp = requests.get(f"{BASE_URL}/tenants", headers=headers)
            tenants = resp.json()['tenants']
            print(f"Tenants count after seed: {len(tenants)}")

            # Check procurements (should be empty as init script doesn't seed it yet, wait, did I check init script?)
            # Init script DOES NOT seed procurements in current version based on my read.
            # But let's check.
            resp = requests.get(f"{BASE_URL}/procurements", headers=headers)
            procurements = resp.json()['procurements']
            print(f"Procurements count after seed: {len(procurements)}")
            
            if len(rooms) > 0 and len(tenants) > 0:
                print("PASS: Demo data generated successfully.")
            else:
                print("FAIL: Demo data missing.")
                
        else:
            print(f"FAIL: Seed data failed. Status: {response.status_code}, Body: {response.text}")
            
    except Exception as e:
        print(f"Seed exception: {e}")

if __name__ == "__main__":
    test_reset_seed_flow()
