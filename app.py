# ==============================
# ADD THESE AT TOP OF app.py
# ==============================

import requests as http_requests
from datetime import date

# URL of your WhatsApp service on Render
WHATSAPP_SERVICE_URL = "https://your-whatsapp-service.onrender.com"  # Change this after deploying!

# ==============================
# ADD THIS HELPER FUNCTION
# ==============================

def notify_absent_students(absent_students, att_date):
    """Call WhatsApp service to send absence notifications."""
    if not absent_students:
        return
    try:
        payload = {
            "students": [
                {"name": s["name"], "phone_number": s["phone_number"]}
                for s in absent_students
                if s.get("phone_number")
            ],
            "date": att_date
        }
        response = http_requests.post(
            f"{WHATSAPP_SERVICE_URL}/send-absence",
            json=payload,
            timeout=10
        )
        print(f"WhatsApp service response: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"WhatsApp service error: {e}")
        # Don't fail attendance saving if WhatsApp fails


# ==============================
# REPLACE YOUR mark_attendance ROUTE WITH THIS
# ==============================

@app.route('/api/attendance', methods=['POST'], strict_slashes=False)
def mark_attendance():
    body = request.get_json()
    if not body or 'records' not in body:
        return jsonify({"error": "Missing records"}), 400
    records = body['records']
    if not records:
        return jsonify({"error": "records list is empty"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()

        # Save attendance records
        for r in records:
            att_date = r.get('date') or date.today().isoformat()
            cur.execute("""
                INSERT INTO attendance (student_id, status, date)
                VALUES (%s, %s, %s)
                ON CONFLICT (student_id, date)
                DO UPDATE SET status = EXCLUDED.status
            """, (r['student_id'], r['status'], att_date))
        conn.commit()

        # Get absent student IDs
        absent_ids = [r['student_id'] for r in records if r.get('status') == 'absent']
        att_date = records[0].get('date') or date.today().isoformat()

        # Fetch phone numbers for absent students
        if absent_ids:
            cur2 = conn.cursor(cursor_factory=RealDictCursor)
            cur2.execute("""
                SELECT name, phone_number FROM students
                WHERE id = ANY(%s) AND phone_number IS NOT NULL
            """, (absent_ids,))
            absent_students = cur2.fetchall()
            cur2.close()

            # Send WhatsApp notifications in background
            import threading
            threading.Thread(
                target=notify_absent_students,
                args=(absent_students, att_date),
                daemon=True
            ).start()

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close(); conn.close()
