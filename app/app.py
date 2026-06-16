from flask import Flask, jsonify, request
import psycopg2
import redis
import os
import json

app = Flask(__name__)

# Redis connects using the hostname 'cache' — resolved by Docker DNS
cache_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'cache'),
    port=6379,
    decode_responses=True
)

def get_db():
    # Postgres connects using the hostname 'db' — resolved by Docker DNS
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'db'),
        database=os.getenv('DB_NAME', 'tasksdb'),
        user=os.getenv('DB_USER', 'taskuser'),
        password=os.getenv('DB_PASSWORD')
    )

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/tasks', methods=['GET'])
def get_tasks():
    # Check Redis first — if the result is cached, return it immediately
    cached = cache_client.get('all_tasks')
    if cached:
        return jsonify({"source": "cache", "tasks": json.loads(cached)})

    # Not in cache — go to the database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, done FROM tasks ORDER BY id;")
    tasks = [{"id": r[0], "title": r[1], "done": r[2]} for r in cur.fetchall()]
    cur.close()
    conn.close()

    # Save result to cache for 60 seconds
    cache_client.setex('all_tasks', 60, json.dumps(tasks))

    return jsonify({"source": "database", "tasks": tasks})

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({"error": "title is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING id;",
        (data['title'], False)
    )
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    cache_client.delete('all_tasks')  # Clear the cache so next read is fresh
    return jsonify({"id": task_id, "title": data['title'], "done": False}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)