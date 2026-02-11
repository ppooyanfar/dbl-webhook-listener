import os
import json
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# Get DB_URL from environment variable (for security)
DB_URL = os.environ.get("DB_URL")

# --- HELPER FUNCTION: Shared DB Logic ---
def save_to_db(device_eui, temperature, humidity, co2, battery, full_json):
    """
    Connects to the database and saves the reading.
    Returns True if successful OR if the device is simply ignored.
    """
    if not DB_URL:
        print("Error: DB_URL not found")
        return False
        
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Ensure tables exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS iot_readings (
                id SERIAL PRIMARY KEY,
                device_eui VARCHAR(50),
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                temperature FLOAT,
                humidity FLOAT,
                co2_level FLOAT,
                battery_level FLOAT,
                raw_payload JSONB
            );
        """)

        # Try to insert the data
        try:
            cur.execute("""
                INSERT INTO iot_readings (device_eui, temperature, humidity, co2_level, battery_level, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_eui, temperature, humidity, co2, battery, json.dumps(full_json)))
            conn.commit()
            print(f"Success: Saved data for {device_eui}")
            
        except psycopg2.IntegrityError:
            # This catches the "Foreign Key Violation" (Device not registered)
            conn.rollback()
            print(f"Ignored: Device {device_eui} is not registered in the dashboard.")
            # We return True so The Things Stack thinks everything is fine and keeps the webhook alive!
            return True
            
        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Database Error: {e}")
        return False

# --- ROUTE 1: Original Webhook (Application 1) ---
# URL: https://your-app.onrender.com/webhook
@app.route('/webhook', methods=['POST'])
def receive_data():
    try:
        data = request.json
        
        # 1. Parse Device ID (Clean format)
        raw_id = data.get("end_device_ids", {}).get("dev_eui")
        device_eui = raw_id.replace("eui-", "").upper() if raw_id else None
        
        # 2. Extract Payload
        uplink = data.get("uplink_message", {})
        payload = uplink.get("decoded_payload", {})
        
        # 3. Get Sensor Values (App 1 specific keys)
        temperature = payload.get("temperature") or payload.get("temp") or payload.get("t")
        humidity = payload.get("humidity") or payload.get("hum") or payload.get("rh")
        co2 = payload.get("co2") or payload.get("co2_level")
        battery = payload.get("battery") or payload.get("bat")

        print(f"[App 1] Data for {device_eui}: Temp={temperature}")

        # 4. Save
        if save_to_db(device_eui, temperature, humidity, co2, battery, data):
            return "Data Saved", 200
        else:
            return "DB Error", 500

    except Exception as e:
        print(f"Error processing webhook 1: {e}")
        return "Error", 500

# --- ROUTE 2: New Webhook (Application 2) ---
# URL: https://your-app.onrender.com/webhook2
@app.route('/webhook2', methods=['POST'])
def receive_data_v2():
    try:
        data = request.json
        
        # 1. Parse Device ID (Clean format)
        raw_id = data.get("end_device_ids", {}).get("dev_eui")
        device_eui = raw_id.replace("eui-", "").upper() if raw_id else None
        
        # 2. Extract Payload
        uplink = data.get("uplink_message", {})
        payload = uplink.get("decoded_payload", {})
        
        # 3. Get Sensor Values (App 2 specific keys)
        # Note: If your second app uses different variable names (e.g. "degreesC"), change them here!
        temperature = payload.get("temperature") or payload.get("temp") 
        humidity = payload.get("humidity") or payload.get("hum") 
        co2 = payload.get("co2") or payload.get("co2_level")
        battery = payload.get("battery") or payload.get("bat")

        print(f"[App 2] Data for {device_eui}: Temp={temperature}")

        # 4. Save using the same shared function
        if save_to_db(device_eui, temperature, humidity, co2, battery, data):
            return "Data Saved", 200
        else:
            return "DB Error", 500

    except Exception as e:
        print(f"Error processing webhook 2: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)


