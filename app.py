from flask import Flask, render_template, request, jsonify
import uuid
import time
import x

from flask_cors import CORS

from icecream import ic
ic.configureOutput(prefix=f"_____ | ", includeContext=True)

from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)
CORS(app)  # allows everything

app.config["JWT_SECRET_KEY"] = "super-secret-key"
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

        user = {
            "user_email": row["user_email"],
            "user_password": row["user_password"]
            }

        if not row:
            return "User not found", 401
        
        if not check_password_hash(user["user_password"], user_password):
            return "Wrong password", 401

        access_token = create_access_token(identity=str(user))

        return jsonify(access_token=access_token)

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
    user = get_jwt_identity()
    return jsonify(user)

##############################
@app.get("/sign-up")
@x.no_cache
def show_signup():
    try:
        
        db, cursor = x.db()
        q = "SELECT location_name FROM wash_world_locations"
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
        user_password = x.validate_user_password( request.form.get("password", "") )
        user_hashed_password = generate_password_hash(user_password)
        user_phone = x.validate_user_phone( request.form.get("phone", "") )
        user_license_plate = x.validate_user_license_plate( request.form.get("license_plate", "") )
        user_primary_location = request.form.get("primary_location", "")
        user_payment_method = request.form.get("payment", "")

        access_to_all_washes = 1 if request.form.get("access_to_all_washes") else 0
        terms_accepted = 1 if request.form.get("terms_accepted") else 0
        offers_accepted = 1 if request.form.get("offers_accepted") else 0

        if not user_membership:
            return jsonify({"error": "Membership selection is required"}), 400
        
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
        q_user = "INSERT INTO users VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(q_user, (user_pk, user_email, user_membership, user_hashed_password, user_phone, user_primary_location, access_to_all_washes, terms_accepted, offers_accepted, user_payment_method, user_verification_key, 0, user_reset_password_key))

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
            return jsonify({"error": f"Phinenumber must be {x.USER_PHONE} characters"}), 400

        if "company_exception user_license_plate" in str(ex):
            return jsonify({"error": "The license plate must consist of 2 letters followed by 5 numbers (e.g. AB12345)"}), 400
        
        if "Duplicate entry" in str(ex) and "user_email" in str(ex):
            return jsonify({"error": "E-mail already exists"}), 400

        if "Duplicate entry" in str(ex) and "user_phone" in str(ex):
            return jsonify({"error": "Phonenumber already exsists"}), 400
        
        if "Duplicate entry" in str(ex) and "user_license_plate" in str(ex):
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

        db, cursor = x.db()
        q = "SELECT user_reset_password_key AS 'key' FROM users WHERE user_email = %s"
        cursor.execute(q,(user_email,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Email not found"}), 400

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

        return render_template("page_reset_password.html", key=key)
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

