import os
import json
import psycopg2
from flask import Flask, request

app = Flask(__name__)

# Get DB_URL from environment variable (for security)
DB_URL = os.environ.get("DB_URL")

@app.route('/webhook', methods=['POST'])
def receive_data():
    try:
        data = request.json
        
        # 1. Parse Data from The Things Stack
        # Note: The JSON structure depends on your specific LoRaWAN payload formatter
        raw_id = data.get("end_device_ids", {}).get("device_id")
        # FIX: Remove 'eui-' prefix and force Uppercase to match Dashboard format
        device_eui = raw_id.replace("eui-", "").upper()
        uplink = data.get("uplink_message", {})
        payload = uplink.get("decoded_payload", {})
        
        # Extract sensor values (Update these keys to match your sensor's decoder!)
        # Example: if your decoder outputs {"t": 22.5, "rh": 45}, change keys below.
        temperature = payload.get("temperature") or payload.get("temp") or payload.get("t")
        humidity = payload.get("humidity") or payload.get("hum") or payload.get("rh")
        co2 = payload.get("co2") or payload.get("co2_level")
        battery = payload.get("battery") or payload.get("bat")

        print(f"Received data for {device_eui}: Temp={temperature}, Co2={co2}")

        # 2. Insert into Neon Database
        if DB_URL:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            
            # Ensure tables exist (just in case dashboard wasn't run first)
            # You can remove this check once confident
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

            cur.execute("""
                INSERT INTO iot_readings (device_eui, temperature, humidity, co2_level, battery_level, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (device_eui, temperature, humidity, co2, battery, json.dumps(data)))
            
            conn.commit()
            cur.close()
            conn.close()
            return "Data Saved", 200
        else:
            print("Error: DB_URL not found")
            return "DB Config Error", 500

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return "Error", 500

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=10000)
