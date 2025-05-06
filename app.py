from flask import Flask, render_template, redirect, request, flash, url_for
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = "abc123"

# MySQL configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "inventory_db"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL(app)

def execute_query(query, params=None, fetch_one=False):
    con = mysql.connection.cursor()
    con.execute(query, params or ())
    if fetch_one:
        result = con.fetchone()
    else:
        result = con.fetchall()
    mysql.connection.commit()
    con.close()
    return result

# Routes
@app.route("/")
def home():
    products = execute_query("SELECT product_id, name, quantity, price FROM Product")
    locations = execute_query("SELECT location_id, name FROM Location")
    
    # Get recent movements count
    movements_count = execute_query("""
        SELECT COUNT(*) as count FROM (
            SELECT movement_id FROM Buy_Movement
            UNION ALL
            SELECT movement_id FROM Sale_Movement
            UNION ALL
            SELECT movement_id FROM ProductMovement
        ) AS combined_movements
    """, fetch_one=True)['count']
    
    # Get recent activities for dashboard
    recent_activities = execute_query("""
        (SELECT 
            'Purchase' as type,
            'primary' as type_color,
            CONCAT('Purchased ', movement_qty, ' units of ', p.name, ' to ', l.name) as description,
            timestamp
        FROM Buy_Movement bm
        JOIN Product p ON bm.product_id = p.product_id
        JOIN Location l ON bm.to_location = l.location_id
        ORDER BY timestamp DESC LIMIT 3)
        
        UNION ALL
        
        (SELECT 
            'Sale' as type,
            'success' as type_color,
            CONCAT('Sold ', movement_qty, ' units of ', p.name, ' from ', l.name) as description,
            timestamp
        FROM Sale_Movement sm
        JOIN Product p ON sm.product_id = p.product_id
        JOIN Location l ON sm.from_location = l.location_id
        ORDER BY timestamp DESC LIMIT 3)
        
        UNION ALL
        
        (SELECT 
            'Transfer' as type,
            'info' as type_color,
            CONCAT('Transferred ', movement_qty, ' units of ', p.name, ' from ', fl.name, ' to ', tl.name) as description,
            timestamp
        FROM ProductMovement pm
        JOIN Product p ON pm.product_id = p.product_id
        JOIN Location fl ON pm.from_location = fl.location_id
        JOIN Location tl ON pm.to_location = tl.location_id
        ORDER BY timestamp DESC LIMIT 3)
        
        ORDER BY timestamp DESC LIMIT 5
    """)

    return render_template("home.html",
                         products=products,
                         locations=locations,
                         movements_count=movements_count,
                         recent_activities=recent_activities)

@app.route("/products/add", methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        quantity = request.form['quantity']
        price = request.form['price']

        if not name:
            flash("Product name cannot be empty", "danger")
            return redirect(url_for("add_product"))
        try:
            quantity = int(quantity)
            price = float(price)
            if quantity <= 0 or price <= 0:
                flash("Quantity and price must be positive values", "danger")
                return redirect(url_for("add_product"))
        except ValueError:
            flash("Invalid quantity or price", "danger")
            return redirect(url_for("add_product"))

        execute_query(
            "INSERT INTO Product(name, quantity, price) VALUES (%s, %s, %s)",
            [name, quantity, price]
        )
        flash("Product added successfully", "success")
        return redirect(url_for("home"))

    return render_template("products/add.html")

@app.route("/products")
def view_products():
    products = execute_query("SELECT product_id, name, quantity, price FROM Product")
    return render_template("products/view.html", products=products)

@app.route("/locations")
def view_locations():
    locations = execute_query("SELECT location_id, name FROM Location")
    return render_template("locations/view.html", locations=locations)

@app.route("/movements")
def view_movements():
    # Fetch all movement types
    buy_movements = execute_query("""
        SELECT bm.movement_id, p.name AS product_name, bm.movement_qty, l.name AS to_location, bm.timestamp
        FROM Buy_Movement bm
        JOIN Product p ON bm.product_id = p.product_id
        JOIN Location l ON bm.to_location = l.location_id
        ORDER BY bm.timestamp DESC
    """)
    
    sale_movements = execute_query("""
        SELECT sm.movement_id, p.name AS product_name, sm.movement_qty, l.name AS from_location, sm.timestamp
        FROM Sale_Movement sm
        JOIN Product p ON sm.product_id = p.product_id
        JOIN Location l ON sm.from_location = l.location_id
        ORDER BY sm.timestamp DESC
    """)
    
    transfer_movements = execute_query("""
        SELECT pm.movement_id, p.name AS product_name, pm.movement_qty, 
               fl.name AS from_location, tl.name AS to_location, pm.timestamp
        FROM ProductMovement pm
        JOIN Product p ON pm.product_id = p.product_id
        JOIN Location fl ON pm.from_location = fl.location_id
        JOIN Location tl ON pm.to_location = tl.location_id
        ORDER BY pm.timestamp DESC
    """)
    
    return render_template("movements/view.html", 
                         buy_movements=buy_movements,
                         sale_movements=sale_movements,
                         transfer_movements=transfer_movements)

@app.route("/products/edit/<int:id>", methods=['GET', 'POST'])
def edit_product(id):
    product = execute_query("SELECT product_id, name, quantity, price FROM Product WHERE product_id = %s", [id], fetch_one=True)
    if not product:
        flash("Product not found", "danger")
        return redirect(url_for("home"))

    if request.method == 'POST':
        name = request.form['name']
        quantity = request.form['quantity']
        price = request.form['price']

        if not name:
            flash("Product name cannot be empty", "danger")
            return redirect(url_for("edit_product", id=id))
        try:
            quantity = int(quantity)
            price = float(price)
            if quantity <= 0 or price <= 0:
                flash("Quantity and price must be positive values", "danger")
                return redirect(url_for("edit_product", id=id))
        except ValueError:
            flash("Invalid quantity or price", "danger")
            return redirect(url_for("edit_product", id=id))

        execute_query(
            "UPDATE Product SET name=%s, quantity=%s, price=%s WHERE product_id=%s",
            [name, quantity, price, id]
        )
        flash("Product updated successfully", "success")
        return redirect(url_for("home"))

    return render_template("products/edit.html", product=product)

@app.route("/products/delete/<int:id>", methods=['POST'])
def delete_product(id):
    product = execute_query("SELECT product_id FROM Product WHERE product_id = %s", [id], fetch_one=True)
    if not product:
        flash("Product not found", "danger")
        return redirect(url_for("home"))
    execute_query("DELETE FROM Product WHERE product_id = %s", [id])
    flash("Product deleted successfully", "success")
    return redirect(url_for("home"))

@app.route("/locations/add", methods=['GET', 'POST'])
def add_location():
    if request.method == 'POST':
        name = request.form['name'].strip()
        
        if not name:
            flash("Location name cannot be empty", "danger")
            return redirect(url_for("add_location"))
        last_id = execute_query("SELECT location_id FROM Location ORDER BY location_id DESC LIMIT 1", fetch_one=True)

        last_num = 0
        if last_id and 'location_id' in last_id and '-' in last_id['location_id']:
            parts = last_id['location_id'].split('-')
            if len(parts) == 2 and parts[1].isdigit():
                last_num = int(parts[1])

        new_id = f"LOC-{last_num + 1:04d}"
        while True:
            existing_location = execute_query("SELECT location_id FROM Location WHERE location_id = %s", [new_id], fetch_one=True)
            if existing_location:
                last_num += 1
                new_id = f"LOC-{last_num + 1:04d}"
            else:
                break
        execute_query(
            "INSERT INTO Location(location_id, name) VALUES (%s, %s)",
            [new_id, name]
        )
        flash("Location added successfully", "success")
        return redirect(url_for("home"))

    last_id = execute_query("SELECT location_id FROM Location ORDER BY location_id DESC LIMIT 1", fetch_one=True)

    last_num = 0
    if last_id and 'location_id' in last_id and '-' in last_id['location_id']:
        parts = last_id['location_id'].split('-')
        if len(parts) == 2 and parts[1].isdigit():
            last_num = int(parts[1])

    preview_id = f"LOC-{last_num + 1:04d}"

    return render_template("locations/add.html", preview_id=preview_id)


@app.route("/locations/edit/<string:id>", methods=['GET', 'POST'])
def edit_location(id):
    location = execute_query("SELECT location_id, name FROM Location WHERE location_id = %s", [id], fetch_one=True)
    if not location:
        flash("Location not found", "danger")
        return redirect(url_for("home"))

    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash("Location name cannot be empty", "danger")
            return redirect(url_for("edit_location", id=id))
        execute_query(
            "UPDATE Location SET name=%s WHERE location_id=%s",
            [name, id]
        )
        flash("Location updated successfully", "success")
        return redirect(url_for("home"))

    return render_template("locations/edit.html", location=location)

@app.route("/locations/delete/<string:id>", methods=['POST'])
def delete_location(id):
    try:
        location = execute_query("SELECT location_id FROM Location WHERE location_id = %s", [id], fetch_one=True)
        if not location:
            flash("Location not found", "danger")
            return redirect(url_for("home"))
        
        # Check for dependent records in movement tables
        movement_check = execute_query("""
            SELECT (
                (SELECT COUNT(*) FROM Buy_Movement WHERE to_location = %s) +
                (SELECT COUNT(*) FROM Sale_Movement WHERE from_location = %s) +
                (SELECT COUNT(*) FROM ProductMovement WHERE from_location = %s OR to_location = %s)
            ) AS total_dependencies
        """, [id, id, id, id], fetch_one=True)
        
        if movement_check['total_dependencies'] > 0:
            flash("Cannot delete location - it has associated movements. Delete the movements first.", "danger")
            return redirect(url_for("home"))
        
        # If no dependencies, delete the location
        execute_query("DELETE FROM Location WHERE location_id = %s", [id])
        flash("Location deleted successfully", "success")
        
    except Exception as e:
        flash(f"Error deleting location: {str(e)}", "danger")
    
    return redirect(url_for("home"))

@app.route("/movements/add", methods=['GET', 'POST'])
def add_movement():
    products = execute_query("SELECT product_id, name FROM Product")
    locations = execute_query("SELECT location_id, name FROM Location")

    if request.method == 'POST':
        movement_type = request.form['movement_type']
        product_id = request.form['product_id']
        try:
            movement_qty = int(request.form['quantity'])
            if movement_qty <= 0:
                flash("Movement quantity must be positive", "danger")
                return redirect(url_for("add_movement"))
        except ValueError:
            flash("Invalid quantity", "danger")
            return redirect(url_for("add_movement"))

        from_location = request.form.get('from_location')
        to_location = request.form.get('to_location')

        if not product_id:
            flash("Product is required for movement", "danger")
            return redirect(url_for("add_movement"))

        if movement_type == 'Buy':
            if not to_location:
                flash("To Location is required for Buy movement", "danger")
                return redirect(url_for("add_movement"))
            execute_query(
                "INSERT INTO Buy_Movement (product_id, movement_qty, to_location) VALUES (%s, %s, %s)",
                (product_id, movement_qty, to_location)
            )

        elif movement_type == 'Sale':
            if not from_location:
                flash("From Location is required for Sale movement", "danger")
                return redirect(url_for("add_movement"))
            execute_query(
                "INSERT INTO Sale_Movement (product_id, movement_qty, from_location) VALUES (%s, %s, %s)",
                (product_id, movement_qty, from_location)
            )

        elif movement_type == 'Transfer':
            if not from_location or not to_location:
                flash("Both From and To Locations are required for Transfer", "danger")
                return redirect(url_for("add_movement"))
            if from_location == to_location:
                flash("From and To locations cannot be the same for transfer", "danger")
                return redirect(url_for("add_movement"))
            execute_query(
                """INSERT INTO ProductMovement (product_id, movement_qty, from_location, to_location)
                    VALUES (%s, %s, %s, %s)""",
                (product_id, movement_qty, from_location, to_location)
            )

        flash(f"{movement_type} recorded successfully!", "success")
        return redirect(url_for("home"))

    return render_template("movements/add.html", products=products, locations=locations)

@app.route("/movements/edit/<int:id>", methods=['GET', 'POST'])
def edit_movement(id):
    movement = execute_query("SELECT movement_id, product_id, movement_qty, from_location, to_location FROM ProductMovement WHERE movement_id = %s", [id], fetch_one=True)
    if not movement:
        movement = execute_query("SELECT movement_id, product_id, movement_qty, from_location, NULL AS to_location FROM Sale_Movement WHERE movement_id = %s", [id], fetch_one=True)
        if not movement:
            movement = execute_query("SELECT movement_id, product_id, movement_qty, NULL AS from_location, to_location FROM Buy_Movement WHERE movement_id = %s", [id], fetch_one=True)
            if not movement:
                flash("Movement not found", "danger")
                return redirect(url_for("home"))
            movement['movement_type'] = 'Buy'
        else:
            movement['movement_type'] = 'Sale'
    else:
        movement['movement_type'] = 'Transfer'

    products = execute_query("SELECT product_id, name FROM Product")
    locations = execute_query("SELECT location_id, name FROM Location")

    if request.method == 'POST':
        product_id = request.form['product_id']
        try:
            quantity = int(request.form['quantity'])
            if quantity <= 0:
                flash("Movement quantity must be positive", "danger")
                return redirect(url_for("edit_movement", id=id))
        except ValueError:
            flash("Invalid quantity", "danger")
            return redirect(url_for("edit_movement", id=id))
        from_location = request.form['from_location']
        to_location = request.form['to_location']
        movement_type = movement['movement_type'] # Determine the original movement type

        if movement_type == 'Transfer':
            if not from_location or not to_location:
                flash("Both From and To Locations are required for Transfer", "danger")
                return redirect(url_for("edit_movement", id=id))
            if from_location == to_location:
                flash("From and To locations cannot be the same for transfer", "danger")
                return redirect(url_for("edit_movement", id=id))
            execute_query(
                """UPDATE ProductMovement
                   SET from_location=%s, to_location=%s, product_id=%s, movement_qty=%s
                   WHERE movement_id=%s""",
                [from_location, to_location, product_id, quantity, id]
            )
            flash("Transfer updated successfully!", "success")
        elif movement_type == 'Sale':
            if not from_location:
                flash("From Location is required for Sale", "danger")
                return redirect(url_for("edit_movement", id=id))
            execute_query(
                """UPDATE Sale_Movement
                   SET from_location=%s, product_id=%s, movement_qty=%s
                   WHERE movement_id=%s""",
                [from_location, product_id, quantity, id]
            )
            flash("Sale updated successfully!", "success")
        elif movement_type == 'Buy':
            if not to_location:
                flash("To Location is required for Buy", "danger")
                return redirect(url_for("edit_movement", id=id))
            execute_query(
                """UPDATE Buy_Movement
                   SET to_location=%s, product_id=%s, movement_qty=%s
                   WHERE movement_id=%s""",
                [to_location, product_id, quantity, id]
            )
            flash("Buy updated successfully!", "success")

        return redirect(url_for("home"))

    return render_template("movements/edit.html", movement=movement, products=products, locations=locations)

@app.route("/movements/delete/<int:id>", methods=['POST'])
def delete_movement(id):
    try:
        # Attempt to delete from all movement tables
        rows_affected = execute_query("DELETE FROM ProductMovement WHERE movement_id = %s", [id])
        if not rows_affected:
            rows_affected = execute_query("DELETE FROM Sale_Movement WHERE movement_id = %s", [id])
            if not rows_affected:
                rows_affected = execute_query("DELETE FROM Buy_Movement WHERE movement_id = %s", [id])
                if not rows_affected:
                    flash(f"Movement with ID {id} not found!", "warning")
                    return redirect(url_for("home"))
        flash(f"Movement with ID {id} deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting movement: {str(e)}", "danger")

    return redirect(url_for("home"))

@app.route('/report')
def report():
  
    products = execute_query("SELECT product_id, name FROM Product")
    locations = execute_query("SELECT location_id, name FROM Location")

    stock_report = {}
    for product in products:
        product_id = product['product_id']
        stock_report[product_id] = {
            'name': product['name'],
            'locations': {loc['location_id']: 0 for loc in locations}
        }
    
   
    for product in products:
        product_id = product['product_id']
        
        for location in locations:
            loc_id = location['location_id']
            
            incoming_query = """
                SELECT COALESCE(SUM(movement_qty), 0) AS total_in
                FROM (
                    SELECT movement_qty FROM Buy_Movement 
                    WHERE product_id = %s AND to_location = %s
                    UNION ALL
                    SELECT movement_qty FROM ProductMovement 
                    WHERE product_id = %s AND to_location = %s
                ) AS combined_in
            """
            total_in = execute_query(incoming_query, [product_id, loc_id, product_id, loc_id], fetch_one=True)['total_in']
            
            outgoing_query = """
                SELECT COALESCE(SUM(movement_qty), 0) AS total_out
                FROM (
                    SELECT movement_qty FROM Sale_Movement 
                    WHERE product_id = %s AND from_location = %s
                    UNION ALL
                    SELECT movement_qty FROM ProductMovement 
                    WHERE product_id = %s AND from_location = %s
                ) AS combined_out
            """
            total_out = execute_query(outgoing_query, [product_id, loc_id, product_id, loc_id], fetch_one=True)['total_out']
            
            # Calculate net quantity (can't be negative)
            net_quantity = max(0, total_in - total_out)
            stock_report[product_id]['locations'][loc_id] = net_quantity
    
    return render_template('report.html', 
                         stock_report=stock_report,
                         products=products,
                         locations=locations)

if __name__ == '__main__':
    app.run(debug=True)