from flask import Flask, render_template, request, jsonify
import psycopg
import os

app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/bakery')

def get_db():
    # psycopg 3 connect
    conn = psycopg.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def dict_from_row(cursor, row):
    """Konwertuj wiersz PostgreSQL do słownika"""
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))

def init_db():
    """Inicjalizuj bazę danych PostgreSQL"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Twórz tabele jeśli nie istnieją
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            delivery_date TEXT NOT NULL DEFAULT '23.12',
            notes TEXT DEFAULT ''
        )
    ''')
    
    # Dodaj kolumnę notes jeśli nie istnieje (dla istniejących baz)
    try:
        cursor.execute('ALTER TABLE customers ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT \'\'')
        conn.commit()
    except Exception:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            delivered BOOLEAN DEFAULT FALSE,
            delivery_date TEXT NOT NULL DEFAULT '23.12',
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    conn.commit()
    
    # Sprawdź czy produkty już są
    cursor.execute('SELECT COUNT(*) as cnt FROM products')
    cnt = cursor.fetchone()[0]
    
    if cnt == 0:
        default_products = [
            ('pszenny czysty', 13),
            ('pszenny mak', 13),
            ('pszenny sezam', 13),
            ('pszenno-żytni', 13),
            ('pszenno-orkiszowy', 13),
            ('foremowy duży pszenno-żytni', 18),
            ('foremowy duży pszenno-orkiszowy', 18),
            ('foremowy żytni 100% z ziarnami', 18),
            ('foremowy żytni 100% czysty', 18),
            ('mazurek z mleczną czekoladą i maliną', 45),
            ('babka piaskowa z pistacją', 45),
            ('hot cross buns 2 szt', 17),
            ('hot cross buns 4 szt', 30),
            ('panettone 300g', 50),
            ('panettone 500g', 70),
            ('karpatka', 45),
            ('pascha twarogowa (gluten free)', 40)
        ]
        for name, price in default_products:
            try:
                cursor.execute('INSERT INTO products (name, price) VALUES (%s, %s)', (name, price))
            except Exception:
                pass
        conn.commit()
    
    conn.close()



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/customers', methods=['GET'])
def get_customers():
    delivery_date = request.args.get('delivery_date', '23.12')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers WHERE delivery_date = %s ORDER BY name', (delivery_date,))
    customers = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(customers)

@app.route('/customer/add', methods=['POST'])
def add_customer():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    delivery_date = data.get('delivery_date', '23.12')
    notes = data.get('notes', '')
    
    if not name or not phone:
        return jsonify({'error': 'Imię i telefon są wymagane'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO customers (name, phone, delivery_date, notes) VALUES (%s, %s, %s, %s) RETURNING id', (name, phone, delivery_date, notes))
        customer_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return jsonify({'id': customer_id, 'name': name, 'phone': phone, 'delivery_date': delivery_date, 'notes': notes})
    except Exception as e:
        conn.close()
        return jsonify({'error': 'Klient z tym numerem już istnieje w tym dniu'}), 400

@app.route('/customer/<int:customer_id>/update', methods=['PUT'])
def update_customer(customer_id):
    data = request.json
    notes = data.get('notes', '')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE customers SET notes = %s WHERE id = %s', (notes, customer_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/customer/<int:customer_id>/delete', methods=['DELETE'])
def delete_customer(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders WHERE customer_id = %s', (customer_id,))
    cursor.execute('DELETE FROM customers WHERE id = %s', (customer_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/customer/<int:customer_id>', methods=['GET'])
def get_customer_details(customer_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM customers WHERE id = %s', (customer_id,))
    customer_row = cursor.fetchone()
    
    if not customer_row:
        conn.close()
        return jsonify({'error': 'Klient nie znaleziony'}), 404
    
    customer = dict_from_row(cursor, customer_row)
    
    cursor.execute('''
        SELECT o.id, p.name, p.price, o.quantity, o.delivered
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.customer_id = %s
        ORDER BY p.name
    ''', (customer_id,))
    orders = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    
    # Oblicz sumę wartości zamówień
    total_price = sum(o['price'] * o['quantity'] for o in orders if not o['delivered'])
    
    conn.close()
    
    return jsonify({
        'id': customer['id'],
        'name': customer['name'],
        'phone': customer['phone'],
        'notes': customer.get('notes', ''),
        'orders': orders,
        'total_price': total_price
    })

@app.route('/customer/<int:customer_id>/add-order', methods=['POST'])
def add_order(customer_id):
    data = request.json
    product_id = data.get('product_id')
    quantity = data.get('quantity')

    if product_id is None or quantity is None:
        return jsonify({'error': 'Produkt (product_id) i ilość są wymagane'}), 400

    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Nieprawidłowy product_id'}), 400

    try:
        quantity = int(quantity)
        if quantity <= 0:
            return jsonify({'error': 'Ilość musi być większa niż 0'}), 400
    except ValueError:
        return jsonify({'error': 'Ilość musi być liczbą'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Sprawdzenie czy klient istnieje
    cursor.execute('SELECT id FROM customers WHERE id = %s', (customer_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Klient nie znaleziony'}), 404

    # Sprawdzenie czy produkt istnieje w liście
    cursor.execute('SELECT id FROM products WHERE id = %s', (product_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Produkt nie istnieje'}), 400

    # Dodaj zamówienie
    cursor.execute('INSERT INTO orders (customer_id, product_id, quantity) VALUES (%s, %s, %s)',
                   (customer_id, product_id, quantity))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/customer/<int:customer_id>/add-orders', methods=['POST'])
def add_orders(customer_id):
    data = request.json
    items = data.get('items')

    if not items or not isinstance(items, list):
        return jsonify({'error': 'Lista items jest wymagana'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Sprawdzenie czy klient istnieje i pobierz jego delivery_date
    cursor.execute('SELECT id, delivery_date FROM customers WHERE id = %s', (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return jsonify({'error': 'Klient nie znaleziony'}), 404
    
    delivery_date = customer[1]  # tuple index 1 = delivery_date

    inserted = 0
    for it in items:
        try:
            product_id = int(it.get('product_id'))
            quantity = int(it.get('quantity'))
        except Exception:
            continue

        if quantity <= 0:
            continue

        # Sprawdź produkt
        cursor.execute('SELECT id FROM products WHERE id = %s', (product_id,))
        if not cursor.fetchone():
            continue

        cursor.execute('INSERT INTO orders (customer_id, product_id, quantity, delivery_date) VALUES (%s, %s, %s, %s)',
                       (customer_id, product_id, quantity, delivery_date))
        inserted += 1

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'inserted': inserted})


@app.route('/orders/mark-all-delivered', methods=['GET', 'POST', 'PUT'])
def mark_all_delivered():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET delivered = TRUE')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/products', methods=['GET'])
def get_products():
    delivery_date = request.args.get('delivery_date', '23.12')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.name, p.price, COALESCE(SUM(o.quantity), 0) as total_quantity
        FROM products p
        LEFT JOIN orders o ON p.id = o.product_id AND o.delivered = FALSE AND o.delivery_date = %s
        GROUP BY p.id, p.name, p.price
        ORDER BY p.name
    ''', (delivery_date,))
    products = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)


@app.route('/products/ensure-defaults', methods=['POST', 'GET'])
def ensure_default_products():
    default_products = [
        ('pszenny czysty', 13), ('pszenny mak', 13), ('pszenny sezam', 13),
        ('pszenno-żytni', 13), ('pszenno-orkiszowy', 13), ('foremowy duży pszenno-żytni', 18),
        ('foremowy duży pszenno-orkiszowy', 18), ('foremowy żytni 100% z ziarnami', 18), ('foremowy żytni 100% czysty', 18),
        ('mazurek z mleczną czekoladą i maliną', 45), ('babka piaskowa z pistacją', 45),
        ('hot cross buns 2 szt', 17), ('hot cross buns 4 szt', 30), ('panettone 300g', 50), ('panettone 500g', 70),
        ('karpatka', 45), ('pascha twarogowa (gluten free)', 40)
    ]
    conn = get_db()
    cursor = conn.cursor()
    for name, price in default_products:
        try:
            cursor.execute('INSERT INTO products (name, price) VALUES (%s, %s)', (name, price))
        except Exception:
            pass
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/customers/status', methods=['GET'])
def customers_status():
    delivery_date = request.args.get('delivery_date', '23.12')
    conn = get_db()
    cursor = conn.cursor()

    # Dla każdego klienta policz sumę ilości zamówień nieoznaczonych jako dostarczone
    cursor.execute('''
        SELECT c.id, c.name, c.phone,
               COALESCE(SUM(CASE WHEN o.delivered = FALSE THEN o.quantity ELSE 0 END), 0) as pending_quantity
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id AND o.delivery_date = %s
        WHERE c.delivery_date = %s
        GROUP BY c.id
        ORDER BY c.name
    ''', (delivery_date, delivery_date))
    rows = cursor.fetchall()
    pending = []
    delivered = []
    for r in rows:
        row_dict = dict_from_row(cursor, r)
        if row_dict['pending_quantity'] and row_dict['pending_quantity'] > 0:
            pending.append(row_dict)
        else:
            delivered.append(row_dict)

    conn.close()
    return jsonify({'pending': pending, 'delivered': delivered})

@app.route('/order/<int:order_id>/mark-delivered', methods=['PUT'])
def mark_delivered(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET delivered = TRUE WHERE id = %s', (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/order/<int:order_id>/delete', methods=['DELETE'])
def delete_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders WHERE id = %s', (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    delivery_date = request.args.get('delivery_date', '23.12')
    conn = get_db()
    cursor = conn.cursor()
    
    # Szukaj po imieniu lub numerze telefonu
    cursor.execute('''
        SELECT * FROM customers
        WHERE (name LIKE %s OR phone LIKE %s) AND delivery_date = %s
        ORDER BY name
    ''', (f'%{query}%', f'%{query}%', delivery_date))
    customers = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(customers)

# Initialize DB on startup
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, threaded=False)
