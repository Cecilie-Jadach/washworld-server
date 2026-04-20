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
@app.get("/login")
def show_login():
    return render_template("page_login.html")


##############################
@app.post("/login")
def login():
    try:

        email = x.validate_email( request.form.get("email", "") )
        password = x.validate_user_password( request.form.get("password", "") )

        db, cursor = x.db()
        q = "SELECT * FROM users WHERE user_email = %s"
        cursor.execute(q, (email,))
        row = cursor.fetchone()

        user = {
            "user_name": row["user_name"],
            "user_email": row["user_email"],
            "user_password": row["user_password"]
            }

        if not user:
            return "user not found", 401
        
        if not check_password_hash(user["user_password"], password):
            return "wrong password", 401

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
@app.get("/")
def index():
    return jsonify({"status":"ok", "message":"Connected"})


##############################
@app.route("/people")
def get_people():

    return jsonify({
        "people": [
            {"first_name":"A", "last_name": "Aa", "cpr":"1"},
            {"first_name":"B", "last_name": "Bb", "cpr":"2"},
            {"first_name":"C", "last_name": "Cc", "cpr":"3"},
        ]
    })    

##############################
@app.get("/sign-up")
@x.no_cache
def show_signup():
    try:
        return render_template("page_sign_up.html", x=x)
    except Exception as ex:
        ic(ex)
        return "System under maintenance", 500

##############################
@app.post("/sign-up")
def sign_up():
    try:
        user_name = x.validate_user_name()
        email = x.validate_email( request.form.get("em", "") )
        password = x.validate_user_password( request.form.get("password", "") )
        user_hashed_password = generate_password_hash(password)

        user_pk = uuid.uuid4().hex
        verification_key = uuid.uuid4().hex
        ic(verification_key)

        #Laver to uuid og sætter dem sammen - gør det endnu mere usansynligt, at der opstår to ens keys
        user_reset_password_key = uuid.uuid4().hex + uuid.uuid4().hex
        ic(user_reset_password_key)

        db, cursor = x.db()
        q = "INSERT INTO users VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(q, (user_pk, user_name, verification_key, 0, user_reset_password_key, email, user_hashed_password))
        db.commit()
        
        html = render_template("email_welcome.html", verification_key=verification_key)

        x.send_email("Activate your account", html)

        return "Please check your email maybe it arrived in the spam folder"
        # return html
    except Exception as ex: 
        ic(ex)
        if "--error-- user_name" in str(ex):
            error_message = f"user name {x.USER_NAME_MIN} to {x.USER_NAME_MAX} characters"
            return error_message, 400
        if "company_exception email" in str(ex):
            return "invalid email", 400
        if "company_exception user_password" in str(ex):
            return f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters"
        
        return str(ex),500
        
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()


##############################
@app.get("/verify/<key>")
def verify_account(key): 
    try:
        #Validate the key
        verification_key = x.validate_uuid4(key)
        user_verified_at = int(time.time())

        #Connect to the DB
        db, cursor = x.db()

        #Update the verified_at column 
        q = """
        UPDATE users 
        SET user_verified_at=%s
        WHERE `user_verification_key`=%s AND user_verified_at = 0
        """
        cursor.execute(q,(user_verified_at, verification_key))
        db.commit()
        if cursor.rowcount == 0:
            return "user already verified"

        return f"Welcome to the system, you are verified"
    except Exception as ex: 
        ic(ex)

        if "--error-- uuid invalid" in str(ex):
            error_message = "Invalid key"
            return error_message, 400

        return str(ex), 500
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
        email = x.validate_email( request.form.get("email", "") )

        db, cursor = x.db()
        q = "SELECT user_reset_password_key AS 'key' FROM users WHERE user_email = %s"
        cursor.execute(q,(email,))
        row = cursor.fetchone()
        
        if not row:
            return "Email not found", 400

        html = render_template("email_forgot_password.html", user_reset_password_key=row["key"])

        x.send_email("Reset your password", html)

        return "Check your email"

    except Exception as ex:
        ic(ex)

        if "company_exception email" in str(ex):
            return "invalid email", 400
        return str(ex), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.get("/reset-password/<key>")
def show_reset_password(key): 
    try:
        #Validate the key
        key = x.validate_uuid4_paranoia(key)
        #Connect to the DB to make sure that the key exist
        db, cursor = x.db()

        q = """SELECT user_reset_password_key FROM users WHERE user_reset_password_key = %s"""
        cursor.execute(q,(key,))
        row = cursor.fetchone()

        if not row: 
            return "ups...", 400

        return render_template("page_reset_password.html", key=key)
    except Exception as ex: 
        ic(ex)

        if "--error-- uuid invalid" in str(ex):
            error_message = "Invalid key"
            return error_message, 400

        return str(ex), 500
    finally:
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

##############################
@app.post("/reset-password")
def reset_password():
    try:

        password = x.validate_user_password(request.form.get("password", ""))
        confirm_password = request.form.get("confirm-password", "").strip()
        if confirm_password != password:
            return "Passwords does not match...", 400

        key = x.validate_uuid4_paranoia(request.form.get("key", ""))

        db, cursor = x.db()

        # Find user by reset key
        q = "SELECT user_email FROM users WHERE user_reset_password_key = %s"
        cursor.execute(q, (key,))
        row = cursor.fetchone()

        if not row:
            return "Invalid or expired key", 400

        user_hashed_password = generate_password_hash(password) 

        q = "UPDATE users SET user_password = %s WHERE user_reset_password_key = %s"
        cursor.execute(q, (user_hashed_password, key))
        db.commit()

        return "Password changed, please login"

    except Exception as ex:
        ic(ex)
        if "company_exception user_password" in str(ex):
            return f"Password must be {x.USER_PASSWORD_MIN} to {x.USER_PASSWORD_MAX} characters", 400
        
        if "company_exception paranoia" in str(ex):
            return "Invalid key", 400

        return str(ex), 500
    finally: 
        if "cursor" in locals(): cursor.close()
        if "db" in locals(): db.close()

"""
##############################
@app.route("/forgot-password", methods=["GET", "POST"])
def show_forgot_password():
    try:
        if request.method == "GET":
            return render_template("page_forgot_password.html")

        if request.method == "POST":
            return "ok"
    except Exception as ex: 
        ic(ex)
    finally:
        pass
"""


