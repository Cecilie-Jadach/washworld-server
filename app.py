from flask import Flask, render_template, request, jsonify
import uuid
import time
import x
from datetime import timedelta

from flask_cors import CORS

from icecream import ic
ic.configureOutput(prefix=f"_____ | ", includeContext=True)

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)
CORS(app)  # allows everything

app.config["JWT_SECRET_KEY"] = "super-secret-key"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)


##############################
@app.get("/")
def index():
    return jsonify({"status":"ok", "message":"Connected"})


##############################
@app.get("/login")
def show_login():
    return render_template("page_login.html")


##############################
@app.post("/login")
def login():
    try:

        user_email = x.validate_email( request.form.get("email", "") )
        user_password = x.validate_user_password( request.form.get("password", "") )

        db, cursor = x.db()
        q = "SELECT * FROM users WHERE user_email = %s"
        cursor.execute(q, (user_email,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Forkert e-mail eller adgangskode"}), 401
        
        if not check_password_hash(row["user_password"], user_password):
            return jsonify({"error": "Forkert e-mail eller adgangskode"}), 401

        user = {
            "user_email": row["user_email"],
            "user_password": row["user_password"]
            }

        access_token = create_access_token(identity=row["user_pk"])
        return jsonify(access_token=access_token), 200

    except Exception as ex: 
        ic(ex)
        if "company_exception email" in str(ex):
            return "Invalid credentials", 400

        if "company_exception user_password" in str(ex):
            return f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters"
        
        return str(ex),500
        
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/profile")
@jwt_required()
def show_profile():
    try:
        user_pk = get_jwt_identity()

        db, cursor = x.db()
        q = "SELECT * FROM users WHERE user_pk = %s"
        cursor.execute(q, (user_pk,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Bruger ikke fundet"}), 404

        return jsonify(dict(row)), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": str(ex)}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/locations")
def show_locations():
    try:
        db, cursor = x.db()
        #NOTE: https://www.w3schools.com/sql/sql_join_inner.asp
        q = """
            SELECT wash_world_locations.*, location_busyness.busyness_status 
            FROM wash_world_locations 
            INNER JOIN location_busyness ON wash_world_locations.location_busyness_fk = location_busyness.busyness_fk
            """
        cursor.execute(q, ())
        rows = cursor.fetchall()
        
        locations = []
        for row in rows:
            location = dict(row)
            location["latitude"] = float(row["latitude"])
            location["longitude"] = float(row["longitude"])
            locations.append(location)

        return jsonify({"locations": locations}), 200
    except Exception as ex:
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/sign-up")
@x.no_cache
def show_signup():
    try:
        db, cursor = x.db()
        # q = "SELECT location_name FROM wash_world_locations"
        q = "SELECT location_name, latitude, longitude FROM wash_world_locations"
        cursor.execute(q, ())
        locations = cursor.fetchall()

        # return jsonify({"locations": locations}), 200
        return render_template("page_sign_up.html", locations=locations, x=x), 200
    except Exception as ex:
        ic(ex)
        return "System under maintenance", 500

##############################
@app.post("/sign-up")
def sign_up():
    try:
        user_membership = request.form.get("membership", "")
        user_email = x.validate_email( request.form.get("email", "") )
        user_confirm_email = request.form.get("confirm_email", "").strip()
        user_password = x.validate_user_password( request.form.get("password", "") )
        user_confirm_password = request.form.get("confirm_password", "").strip()
        user_hashed_password = generate_password_hash(user_password)
        user_phone = x.validate_user_phone( request.form.get("phone", "") )
        user_license_plate = x.validate_user_license_plate( request.form.get("license_plate", "") )
        user_primary_location = request.form.get("primary_location", "")
        user_payment_method = request.form.get("payment", "")

        access_to_all_washes = 1 if request.form.get("access_to_all_washes") else 0
        terms_accepted = 1 if request.form.get("terms_accepted") else 0
        offers_accepted = 1 if request.form.get("offers_accepted") else 0

        membership_created_at = int(time.time())
        user_created_at = int(time.time())
        membership_paused_at = 0
        membership_reactivated_at = 0
        membership_pause_months = 0
        membership_updated_at = 0

        if not user_membership:
            return jsonify({"error": "Membership selection is required"}), 400

        if user_confirm_email != user_email:
            return "Emails do not match", 400

        if user_confirm_password != user_password:
            return "Passwords do not match", 400
        
        if not terms_accepted:
            return jsonify({"error": "Terms accepted selection is required"}), 400

        if not user_payment_method:
            return jsonify({"error": "Payment method selection is required"}), 400
        
        user_pk = uuid.uuid4().hex
        user_verification_key = uuid.uuid4().hex
        ic(user_verification_key)

        user_reset_password_key = uuid.uuid4().hex
        ic(user_reset_password_key)

        #connect to database
        db, cursor = x.db()
        # Indsæt bruger i users tabellen
        q_user = "INSERT INTO users VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )"
        cursor.execute(q_user, (user_pk, user_email, user_membership, user_hashed_password, user_phone, user_primary_location, access_to_all_washes, terms_accepted, offers_accepted, user_payment_method, user_verification_key, 0, user_reset_password_key, membership_created_at, user_created_at, membership_pause_months, membership_paused_at, membership_reactivated_at, membership_updated_at))

        # Indsæt nummerplade i license_plates tabellen med reference til brugeren
        q_license = "INSERT INTO license_plates VALUES (%s, %s)"
        cursor.execute(q_license, (user_pk, user_license_plate))
        db.commit()

        html = render_template("email_welcome.html", user_verification_key=user_verification_key)

        x.send_email("Activate your account", html)

        return render_template("page_confirm_email.html", user_email=user_email)
        # return jsonify({"message": "Please check your email, it may have arrived in the spam folder"}), 201
        # return "Please check your email maybe it arrived in the spam folder"
    except Exception as ex: 
        ic(ex)

        if not user_membership:
            return jsonify({"error": "Membership selection is required"}), 400

        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid credentials"}), 400

        if "company_exception user_password" in str(ex):
            return jsonify({"error": f"Password must be between {x.USER_PASSWORD_MIN} and {x.USER_PASSWORD_MAX} characters"}) , 400
        
        if "company_exception user_phone" in str(ex):
            return jsonify({"error": f"Phonenumber must be {x.USER_PHONE} characters"}), 400

        if "company_exception license_plate" in str(ex):
            return jsonify({"error": "The license plate must consist of 2 letters followed by 5 numbers (e.g. AB12345)"}), 400
        
        if "Duplicate entry" in str(ex) and "user_email" in str(ex):
            return jsonify({"error": "E-mail already exists"}), 400

        if "Duplicate entry" in str(ex) and "user_phone" in str(ex):
            return jsonify({"error": "Phonenumber already exsists"}), 400
        
        if "Duplicate entry" in str(ex) and "license_plate" in str(ex):
            return jsonify({"error": "Licenseplate already exists"}), 400
        
        return jsonify({"error": str(ex)}), 500
        # return str(ex),500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/verify/<key>")
def verify_account(key): 
    try:
        #Validate the key
        user_verification_key = x.validate_uuid4(key)
        user_verified_at = int(time.time())

        #Connect to the DB
        db, cursor = x.db()

        #Update the verified_at column 
        q = """
        UPDATE users 
        SET user_verified_at=%s
        WHERE `user_verification_key`=%s AND user_verified_at = 0
        """
        cursor.execute(q,(user_verified_at, user_verification_key))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({"message": "User already verified"}), 200

        return jsonify({"message": f"Welcome to the system, you are verified"}), 200
    except Exception as ex: 
        ic(ex)

        if "--error-- uuid invalid" in str(ex):
            return jsonify({"error": "Invalid key"}), 400

        return jsonify({"error": str(ex)}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/forgot-password")
def show_forgot_password():
    return render_template("page_forgot_password.html")

##############################
@app.post("/forgot-password")
def forgot_password():
    try:
        user_email = x.validate_email( request.form.get("email", "") )
        ic(user_email)

        db, cursor = x.db()
        q = "SELECT user_reset_password_key AS 'key' FROM users WHERE user_email = %s"
        cursor.execute(q,(user_email,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "E-mail findes ikke i vores system"}), 400

        html = render_template("email_forgot_password.html", user_reset_password_key=row["key"])

        x.send_email("Reset your password", html)

        return jsonify({"message": "Check your email"}),200

    except Exception as ex:
        ic(ex)

        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid credentials"}), 400
        
        return jsonify({"error": str(ex)}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/reset-password/<key>")
def show_reset_password(key): 
    try:
        #Validate the key
        key = x.validate_uuid4(key)
        #Connect to the DB to make sure that the key exist
        db, cursor = x.db()

        q = """SELECT user_reset_password_key FROM users WHERE user_reset_password_key = %s"""
        cursor.execute(q,(key,))
        row = cursor.fetchone()

        if not row: 
            return jsonify({"error": "Ups..."}), 400

        return jsonify({"message": "Reset your password", "key": key}), 200
        # return render_template("page_reset_password.html", key=key)
    except Exception as ex: 
        ic(ex)

        if "--error-- uuid invalid" in str(ex):
            return jsonify({"error": "Invalid key"}), 400

        return jsonify({"error": str(ex)}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.post("/reset-password")
def reset_password():
    try:
        user_password = x.validate_user_password(request.form.get("password", ""))
        confirm_password = request.form.get("confirm-password", "").strip()
        if confirm_password != user_password:
            return "Passwords does not match...", 400

        key = x.validate_uuid4(request.form.get("key", ""))

        db, cursor = x.db()

        # Find user by reset key
        q = "SELECT user_email FROM users WHERE user_reset_password_key = %s"
        cursor.execute(q, (key,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Invalid or expired key"}), 400

        user_hashed_password = generate_password_hash(user_password) 

        q = "UPDATE users SET user_password = %s WHERE user_reset_password_key = %s"
        cursor.execute(q, (user_hashed_password, key))
        db.commit()

        return jsonify({"message": "Password changed, please login"}), 200

    except Exception as ex:
        ic(ex)
        if "company_exception user_password" in str(ex):
            return jsonify({"error": f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters"}), 400
        
        if "company_exception paranoia" in str(ex):
            return jsonify({"error": "Invalid key"}), 400

        return jsonify({"error": str(ex)}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.patch("/api-membership-pause")
@jwt_required()
def pause_membership():
    try:
        user_pk = get_jwt_identity()
        membership_pause_months = request.json.get("membership_pause_months", 0)

        ic(user_pk)

        if membership_pause_months not in [1, 2, 3]:
            return jsonify({"error": "Vælg 1, 2 eller 3 måneder"}), 400

        membership_paused_at = int(time.time())

        db, cursor = x.db() 
        q = """UPDATE users SET membership_paused_at = %s, membership_pause_months = %s, membership_reactivated_at = 0 WHERE user_pk = %s"""
        cursor.execute(q,(membership_paused_at, membership_pause_months, user_pk))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Bruger ikke fundet"}), 404

        return jsonify({"message": f"Medlemsskab pauseret i {membership_pause_months} måneder"}), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": str(ex)}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.patch("/api-membership-reactivate")
@jwt_required()
def reactivate_membership():
    try:
        user_pk = get_jwt_identity()
        membership_reactivated_at = int(time.time())

        db, cursor = x.db() 
        q = """UPDATE users SET membership_paused_at = 0, membership_reactivated_at = %s, membership_pause_months = 0 WHERE user_pk = %s"""
        cursor.execute(q,(membership_reactivated_at, user_pk))
        db.commit()

        return jsonify({"message": f"Medlemsskab genaktiveret"}), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": str(ex)}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/license-plates")
@jwt_required()
def show_license_plate():
    try:
        user_pk = get_jwt_identity()
        if not user_pk: return jsonify({"error": "Unauthorized"}), 401

        db, cursor = x.db()
        q = "SELECT * FROM license_plates WHERE user_fk = %s"
        cursor.execute(q, (user_pk,))
        rows = cursor.fetchall()

        #list comprehension
        license_plates = []
        for row in rows:
            license_plates.append(dict(row))

        return jsonify({"license_plates": license_plates}), 200
    except Exception as ex:
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.patch("/api-update-membership")
@jwt_required()
def update_membership():
    try:
        user_pk = get_jwt_identity()
        if not user_pk: return jsonify({"error": "Unauthorized"}), 401

        parts = []
        values = []
        
        user_membership = request.json.get("user_membership", "")
        membership_updated_at = int(time.time())

        if user_membership:
            parts.append("user_membership = %s")
            values.append(user_membership)

        parts.append("membership_updated_at = %s")
        values.append(membership_updated_at)
        
        partial_query = ", ".join(parts)

        if not parts: return "nothing to update", 400

        values.append(user_pk)

        q = f"""
            UPDATE users
            SET	{partial_query}
            WHERE user_pk = %s
        """
        
        db, cursor = x.db()
        cursor.execute(q, values)
        db.commit()

        return jsonify({"message": "Your membership has been updated"})

    except Exception as ex: 
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()


##############################
@app.patch("/api-update-user")
@jwt_required()
def update_user():
    try:
        user_pk = get_jwt_identity()

        parts = []
        values = []

        if "email" in request.json:
            user_email = x.validate_email(request.json.get("email", ""))
            parts.append("user_email = %s")
            values.append(user_email)

        if "phone" in request.json:
            user_phone = x.validate_user_phone(request.json.get("phone", ""))
            parts.append("user_phone = %s")
            values.append(user_phone)

        if "primary_location" in request.json:
            user_primary_location = request.json.get("primary_location", "").strip()
            if not user_primary_location:
                return jsonify({"error": "Primary location cannot be empty"}), 400
            parts.append("user_primary_location = %s")
            values.append(user_primary_location)

        if not parts:
            return jsonify({"error": "Nothing to update"}), 400

        values.append(user_pk)
        partial_query = ", ".join(parts)

        db, cursor = x.db()
        q = f"UPDATE users SET {partial_query} WHERE user_pk = %s"
        cursor.execute(q, values)
        db.commit()

        return jsonify({"message": "User updated"}), 200

    except Exception as ex:
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()


##############################
@app.delete("/api-delete-user")
@jwt_required()
def delete_user():
    try:
        user_pk = get_jwt_identity()

        db, cursor = x.db()

        cursor.execute("DELETE FROM license_plates WHERE user_fk = %s", (user_pk,))
        cursor.execute("DELETE FROM users WHERE user_pk = %s", (user_pk,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"message": "User deleted"}), 200
    except Exception as ex:
        ic(ex)
        return jsonify({"error": str(ex)}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()
