from flask import request, make_response
import mysql.connector
import re # Regular expressions also called Regex
from functools import wraps
from datetime import datetime

from icecream import ic
ic.configureOutput(prefix=f"_____ | ", includeContext=True)

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

##############################
def db():
    try:
        db = mysql.connector.connect(
            host = "mariadb",
            user = "root",  
            password = "password",
            database = "washworld"
        )
        cursor = db.cursor(dictionary=True)
        return db, cursor
    except Exception as e:
        print(e, flush=True)
        raise Exception("Database under maintenance", 500)

##############################
def no_cache(view):
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache_view

##############################
REGEX_EMAIL = "^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$"
def validate_email( email ):
    email = email.strip()
    if not re.match(REGEX_EMAIL, email): 
        raise Exception("company_exception email")
    return email

##############################
# [a-z0-9æøå]
USER_PASSWORD_MIN = 8
USER_PASSWORD_MAX = 50
REGEX_USER_PASSWORD = f"^.{{{USER_PASSWORD_MIN},{USER_PASSWORD_MAX}}}$"
def validate_user_password( password ):
    user_password = password.strip()
    if not re.match(REGEX_USER_PASSWORD, user_password):
        raise Exception("company_exception user_password")
    return user_password

##############################
#0 to 9 letters a to f
REGEX_UUID4 = "^[0-9a-f]{32}$"
def validate_uuid4(uuid):
    uuid = uuid.strip()
    if not re.match(REGEX_UUID4, uuid):
        raise Exception("--error-- uuid invalid")
    return uuid

##############################
USER_PHONE = 8
REGEX_USER_PHONE = f"^[1-9][0-9]{{{USER_PHONE - 1}}}$"
def validate_user_phone( phone ):
    user_phone = phone.strip()
    if not re.match(REGEX_USER_PHONE, user_phone):
        raise Exception("company_exception user_phone")
    return user_phone

##############################
REGEX_USER_LICENSE_PLATE = "^[A-Za-z]{2}[0-9]{5}$"
def validate_user_license_plate(license_plate):
    user_license_plate = license_plate.strip().upper()
    if not re.match(REGEX_USER_LICENSE_PLATE, user_license_plate):
        raise Exception("company_exception user_license_plate")
    return user_license_plate

##############################
#0 to 9 letters a to f
REGEX_UUID4 = "^[0-9a-f]{32}$"
def validate_uuid4(uuid):
    uuid = uuid.strip()
    if not re.match(REGEX_UUID4, uuid):
        raise Exception("--error-- uuid invalid")
    return uuid

##############################
def send_email(subject, html):
    try:    
        # Create a gmail 
        # Enable (turn on) 2 step verification/factor in the google account manager
        # Visit: https://myaccount.google.com/apppasswords
        # Copy the key :

        # Email and password of the sender's Gmail account
        # sender_email = "ceciliejadach95@gmail.com"
        # password = "qeft rfkd ryvm kvrt"  # If 2FA is on, use an App Password instead
        sender_email = "linekofod1305@gmail.com"
        password = "wxio otmi wexw wmtn"  # Lines password

        # Receiver email address
        # receiver_email = "ceciliejadach95@gmail.com"
        receiver_email = "linekofod1305@gmail.com"
        
        # Create the email message
        message = MIMEMultipart()
        message["From"] = "Washworld"
        message["To"] = receiver_email
        message["Subject"] = subject

        # Body of the email
        # body = f"""<h1>Hi</h1><h2>Hi again</h2>"""
        message.attach(MIMEText(html, "html"))

        # Connect to Gmail's SMTP server and send the email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Upgrade the connection to secure
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        ic("Email sent successfully!")

        return "email sent"

    except Exception as ex:
        return "cannot send email", 500
    finally:
        pass

