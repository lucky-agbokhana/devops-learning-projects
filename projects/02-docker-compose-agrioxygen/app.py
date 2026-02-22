from flask import Flask, request, jsonify
import socket
import os
import psycopg2
import redis
import json

app = Flask(__name__)

# Redis connection
cache = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=6379,
    decode_responses=True
)

# Database connection
def get_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'agrioxygen'),
        user=os.environ.get('DB_USER', 'farmer'),
        password=os.environ.get('DB_PASSWORD', 'password')
    )

# Initialize database
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id SERIAL PRIMARY KEY,
            farmer_name VARCHAR(100),
            crop VARCHAR(100),
            quantity VARCHAR(50),
            location VARCHAR(100),
            price VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def home():
    return jsonify({
        "platform": "AgriOxygen",
        "message": "Connecting farmers to markets across Africa",
        "hostname": socket.gethostname(),
        "environment": os.environ.get("ENV", "development"),
        "version": "2.0.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/listings', methods=['GET'])
def get_listings():
    # Check Redis cache first
    cached = cache.get('all_listings')
    if cached:
        return jsonify({
            "source": "cache",
            "listings": json.loads(cached)
        })

    # If not in cache get from database
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM listings ORDER BY created_at DESC')
    rows = cur.fetchall()
    cur.close()
    conn.close()

    listings = []
    for row in rows:
        listings.append({
            "id": row[0],
            "farmer_name": row[1],
            "crop": row[2],
            "quantity": row[3],
            "location": row[4],
            "price": row[5],
            "created_at": str(row[6])
        })

    # Store in Redis cache for 60 seconds
    cache.setex('all_listings', 60, json.dumps(listings))

    return jsonify({
        "source": "database",
        "listings": listings
    })

@app.route('/listings', methods=['POST'])
def create_listing():
    data = request.get_json()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO listings (farmer_name, crop, quantity, location, price) VALUES (%s, %s, %s, %s, %s)',
        (data['farmer_name'], data['crop'], data['quantity'], data['location'], data['price'])
    )
    conn.commit()
    cur.close()
    conn.close()

    # Clear cache so next request gets fresh data
    cache.delete('all_listings')

    return jsonify({
        "message": "Listing created successfully",
        "listing": data
    }), 201

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)



