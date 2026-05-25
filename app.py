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

#######################  LOGIN 
@app.post("/api-login")
def login():
    try:
        user_email = x.validate_email( request.form.get("email", "") )
        user_password = x.validate_user_password( request.form.get("password", "") )

        db, cursor = x.db()
        q = "SELECT * FROM users WHERE user_email = %s"
        cursor.execute(q, (user_email,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Wrong email or password"}), 401
        
        if not check_password_hash(row["user_password"], user_password):
            return jsonify({"error": "Wrong email or password"}), 401

        user = {
            "user_email": row["user_email"],
            "user_password": row["user_password"]
            }

        access_token = create_access_token(identity=row["user_pk"])
        return jsonify(access_token=access_token), 200

    except Exception as ex: 
        ic(ex)
        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid credentials"}), 400

        if "company_exception user_password" in str(ex):
            return jsonify({"error": f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters"}), 400
        
        return jsonify({"error": "System under maintenance."}),500
        
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## PROFILE
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
            return jsonify({"error": "User not found"}), 404

        return jsonify(dict(row)), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## LOCATIONS
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

############################## SIGN UP
@app.post("/api-sign-up")
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
        user_reset_password_key_requested_at = 0

        if not user_membership:
            return jsonify({"error": "Membership is required"}), 400

        if user_confirm_email != user_email:
            return jsonify({"error": "Emails does not match"}), 400

        if user_confirm_password != user_password:
            return jsonify({"error": "Passwords does not match"}), 400
        
        if not terms_accepted:
            return jsonify({"error": "Accepted terms is required"}), 400

        if not user_payment_method:
            return jsonify({"error": "Payment method is required"}), 400
        
        user_pk = uuid.uuid4().hex
        user_verification_key = uuid.uuid4().hex
        ic(user_verification_key)

        user_reset_password_key = uuid.uuid4().hex
        ic(user_reset_password_key)

        db, cursor = x.db()
        q_user = "INSERT INTO users VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )"
        cursor.execute(q_user, (user_pk, user_email, user_membership, user_hashed_password, user_phone, user_primary_location, access_to_all_washes, terms_accepted, offers_accepted, user_payment_method, user_verification_key, 0, user_reset_password_key, membership_created_at, user_created_at, membership_pause_months, membership_paused_at, membership_reactivated_at, membership_updated_at, user_reset_password_key_requested_at))

        q_license = "INSERT INTO license_plates VALUES (%s, %s)"
        cursor.execute(q_license, (user_pk, user_license_plate))
        db.commit()

        html = render_template("email_welcome.html", user_verification_key=user_verification_key)

        x.send_email("Wash World - Aktivér dit medlemsskab", html)

        return render_template("page_confirm_email.html", user_email=user_email)
    except Exception as ex: 
        ic(ex)

        if not user_membership:
            return jsonify({"error": "Membership is required"}), 400

        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid credentials"}), 400

        if "company_exception user_password" in str(ex):
            return jsonify({"error": f"Password must be between {x.USER_PASSWORD_MIN} and {x.USER_PASSWORD_MAX} characters"}) , 400
        
        if "company_exception user_phone" in str(ex):
            return jsonify({"error": f"Phonenumber must be {x.USER_PHONE} characters"}), 400

        if "company_exception license_plate" in str(ex):
            return jsonify({"error": "License plate must consist of 2 letters followed by 5 numbers (e.g. AB12345)"}), 400
        
        if "Duplicate entry" in str(ex) and "user_email" in str(ex):
            return jsonify({"error": "E-mail already exist"}), 400

        if "Duplicate entry" in str(ex) and "user_phone" in str(ex):
            return jsonify({"error": "Phonenumber already exist"}), 400
        
        if "Duplicate entry" in str(ex) and "license_plate" in str(ex):
            return jsonify({"error": "License plate already exist"}), 400
        
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## VERIFY KEY
@app.get("/verify/<key>")
def verify_account(key): 
    try:
        user_verification_key = x.validate_uuid4(key)
        user_verified_at = int(time.time())

        db, cursor = x.db()
        q = """
        UPDATE users 
        SET user_verified_at=%s
        WHERE `user_verification_key`=%s AND user_verified_at = 0
        """
        cursor.execute(q,(user_verified_at, user_verification_key))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "User is already verified"}), 200

        return jsonify({"message": "Welcome to Wash World. You are now verified."}), 200
    except Exception as ex: 
        ic(ex)

        if "company_exception uuid invalid" in str(ex):
            return jsonify({"error": "Invalid key"}), 400

        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## FORGOT PASSWORD
@app.post("/api-forgot-password")
def forgot_password():
    try:
        user_email = x.validate_email( request.form.get("email", "") )
        user_reset_password_key_requested_at = int(time.time())

        db, cursor = x.db()
        q = "SELECT user_reset_password_key AS 'key' FROM users WHERE user_email = %s"
        cursor.execute(q,(user_email,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "E-mail does not exist"}), 400

        q = "UPDATE users SET user_reset_password_key_requested_at=%s WHERE user_email=%s"
        cursor.execute(q,(user_reset_password_key_requested_at, user_email))
        db.commit()

        html = render_template("email_forgot_password.html", user_reset_password_key=row["key"])

        x.send_email("Wash World - Nulstil din adgangskode", html)

        return jsonify({"message": "Check your email"}),200

    except Exception as ex:
        ic(ex)

        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid credentials"}), 400
        
        return jsonify({"error": str(ex)}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## RESET PASSWORD<KEY>
@app.get("/reset-password/<key>")
def show_reset_password(key): 
    try:
        key = x.validate_uuid4(key)
        #Connect to the DB to make sure that the key exist
        db, cursor = x.db()
        q = """SELECT user_reset_password_key, user_reset_password_key_requested_at
            FROM users 
            WHERE user_reset_password_key = %s"""
        cursor.execute(q,(key,))
        row = cursor.fetchone()

        if not row: 
            return jsonify({"error": "Ups..."}), 400
        
        if int(time.time()) - row["user_reset_password_key_requested_at"] > x.RESET_PASSWORD_EXPIRY:
            return jsonify({"error": "Password reset link has expired"}), 400

        return jsonify({"message": "Reset your password", "key": key}), 200
    except Exception as ex: 
        ic(ex)

        if "company_exception uuid invalid" in str(ex):
            return jsonify({"error": "Invalid key"}), 400

        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## RESET PASSWORD
@app.post("/api-reset-password")
def reset_password():
    try:
        user_password = x.validate_user_password(request.form.get("password", ""))
        confirm_password = request.form.get("confirm-password", "").strip()
        
        if confirm_password != user_password:
            return jsonify({"error": "Passwords does not match"}), 400
        
        key = x.validate_uuid4(request.form.get("key", ""))

        user_hashed_password = generate_password_hash(user_password)

        db, cursor = x.db()

        q = "UPDATE users SET user_password = %s WHERE user_reset_password_key = %s"
        cursor.execute(q, (user_hashed_password, key))
        db.commit()

        return jsonify({"message": "Password changed, please login"}), 200

    except Exception as ex:
        ic(ex)
        if "company_exception user_password" in str(ex):
            return jsonify({"error": f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters"}), 400

        return jsonify({"error": "System under maintenance"}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## PAUSE MEMBERSHIP
@app.patch("/api-pause-membership")
@jwt_required()
def pause_membership():
    try:
        user_pk = get_jwt_identity()
        membership_pause_months = request.json.get("membership_pause_months", 0)

        if membership_pause_months not in [1, 2, 3]:
            return jsonify({"error": "Choose 1, 2 or 3 months"}), 400

        membership_paused_at = int(time.time())

        db, cursor = x.db() 
        q = """UPDATE users 
                SET membership_paused_at = %s, membership_pause_months = %s, membership_reactivated_at = 0 
                WHERE user_pk = %s"""
        cursor.execute(q,(membership_paused_at, membership_pause_months, user_pk))
        db.commit()

        return jsonify({"message": "Membership is paused"}), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## REACTIVATE MEMBERSHIP
@app.patch("/api-reactivate-membership") 
@jwt_required()
def reactivate_membership():
    try:
        user_pk = get_jwt_identity()
        membership_reactivated_at = int(time.time())

        db, cursor = x.db() 
        q = """UPDATE users 
                SET membership_paused_at = 0, membership_reactivated_at = %s, membership_pause_months = 0 
                WHERE user_pk = %s"""
        cursor.execute(q,(membership_reactivated_at, user_pk))
        db.commit()

        return jsonify({"message": "Membership reactivated"}), 200
    except Exception as ex: 
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## LICENSE PLATES
@app.get("/license-plates")
@jwt_required()
def show_license_plates():
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

############################## ADD LICENSE PLATE
@app.post("/api-add-license-plate")
@jwt_required()
def add_license_plate():
    try:
        user_pk = get_jwt_identity()
        license_plate = x.validate_user_license_plate(request.json.get("license_plate", ""))

        db, cursor = x.db()
        q = "INSERT INTO license_plates VALUES (%s, %s)"
        cursor.execute(q, (user_pk, license_plate))
        db.commit()

        return jsonify({"message": "License plate added"}), 201
    except Exception as ex:
        ic(ex)
        if "company_exception license_plate" in str(ex):
            return jsonify({"error": "The license plate must consist of 2 letters followed by 5 numbers (e.g. AB12345)"}), 400
        if "Duplicate entry" in str(ex):
            return jsonify({"error": "License plate already exists"}), 400
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## DELETE LICENSE PLATE
@app.delete("/api-delete-license-plate/<plate>")
@jwt_required()
def delete_license_plate(plate):
    try:
        user_pk = get_jwt_identity()
        plate = x.validate_user_license_plate(plate)

        db, cursor = x.db()
        q = "DELETE FROM license_plates WHERE user_license_plate = %s AND user_fk = %s"
        cursor.execute(q, (plate, user_pk))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "License plate not found"}), 404

        return jsonify({"message": "License plate deleted"}), 200
    except Exception as ex:
        ic(ex)
        if "company_exception license_plate" in str(ex):
            return jsonify({"error": "The license plate must consist of 2 letters followed by 5 numbers (e.g. AB12345)"}), 400
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## UPDATE MEMBERSHIP
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

        if not parts: return jsonify({"error": "Nothing to update"}), 400

        values.append(user_pk)

        q = f"""
            UPDATE users
            SET	{partial_query}
            WHERE user_pk = %s
        """
        
        db, cursor = x.db()
        cursor.execute(q, values)
        db.commit()

        return jsonify({"message": "Your membership has been updated"}), 200

    except Exception as ex: 
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## UPDATE USER
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
                return jsonify({"error": "Primary location is required"}), 400
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
        if "company_exception email" in str(ex):
            return jsonify({"error": "Invalid email"}), 400
        if "company_exception user_phone" in str(ex):
            return jsonify({"error": f"Phonenumber must be {x.USER_PHONE} characters"}), 400
        if "Duplicate entry" in str(ex) and "user_email" in str(ex):
            return jsonify({"error": "E-mail already exists"}), 400
        if "Duplicate entry" in str(ex) and "user_phone" in str(ex):
            return jsonify({"error": "Phonenumber already exists"}), 400
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

############################## DELETE USER
@app.delete("/api-delete-user")
@jwt_required()
def delete_user():
    try:
        user_pk = get_jwt_identity()

        db, cursor = x.db()

        q = "DELETE FROM license_plates WHERE user_fk = %s"
        cursor.execute(q, (user_pk,))

        q = "DELETE FROM users WHERE user_pk = %s"
        cursor.execute(q, (user_pk,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"message": "User deleted"}), 200
    except Exception as ex:
        ic(ex)
        return jsonify({"error": "System under maintenance"}), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()
