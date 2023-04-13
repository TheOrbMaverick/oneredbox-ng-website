from datetime import date
from flask import Flask, render_template, url_for, request, redirect
#from flask_mysqldb import MySQL 

# installed mysql-connector-python using pip to be able to access this so I do not need to import the mysql using flask again
import mysql.connector
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask import jsonify, flash, session
from PIL import Image
from dotenv import load_dotenv

import re
import os
import bcrypt
import random
import string

load_dotenv()
dbPath = os.environ['MYSQL_CONFIG']
dbPass = os.environ['DB_PASS']
mailPass = os.environ['MAIL_PASS']
secretK = os.environ['SECRET_KEY']
paystackApiKey = os.environ['PAYSTACK_API_KEY']

#specified the database here with and stored it in cnx
config = {
    'user': 'root',
    'password': dbPass,
    'host': 'localhost',
    'database': "Oneredbox"
}

cnx = mysql.connector.connect(**config)
 
app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.zoho.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'hello@oneredbox.ng'
app.config['MAIL_PASSWORD'] = mailPass
app.secret_key = secretK

mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#user class or user model
class User(UserMixin):
    def __init__(self, user_id, email, name):
        self.id = user_id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    config = {
        'user': 'root',
        'password': dbPass,
        'host': 'localhost',
        'database': "Oneredbox"
    }
    lcnx = mysql.connector.connect(**config)

    id_query = "SELECT * FROM clients WHERE client_id = %s"
    with lcnx.cursor(dictionary=True) as cur:
        cur.execute(id_query, (user_id, ))
        user = cur.fetchone()

    if user is not None:
        return User(user['client_id'], user['client_email'], user['first_name'])

# a decorator with an index function in the decorator this whole section is called routing
@app.route('/')
#this is the route handler
def index():
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cnx.reconnect()
        inputemail = request.form['loginMail']
        password = request.form['inputPass']
        encodedPass = password.encode()

        
        id_query = "SELECT * FROM clients WHERE client_email = %s"
        with cnx.cursor(dictionary=True) as cur:
            cur.execute(id_query, (inputemail, ))
            user = cur.fetchone()
        name = user['first_name']

        hashedPassword = user['password'].encode()

        if user is not None and bcrypt.checkpw(encodedPass, hashedPassword) and inputemail == user['client_email']:
            id = user['client_id']
            login_user(User(id, inputemail, name))
            if user['confirmed'] == 1:   
                return redirect(url_for('dashboard'))
            else:
                email = user['client_email']
                
                confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                with cnx.cursor(dictionary=True) as cur:
                    cur.execute("UPDATE clients SET confirmation_code = %s WHERE client_email = %s", (confirmation_code, inputemail))
                    cnx.commit()

                confirm_link = url_for('confirm_email', email=email, code=confirmation_code, _external=True)
                msg = Message('Please Confirm Your Email', sender='hello@oneredbox.ng', recipients=[email])
                msg.body = f'Thank you for registering! Please confirm your email address by clicking on the following link: {confirm_link}'
                with app.app_context():
                    mail.connect()
                    mail.send(msg)
                return 'Please confirm your e-mail, an email has been sent!'
        
        else:
            print ("no user")

    
    return render_template("login.html")


@app.route('/getfreeQuote', methods = ['GET', 'POST'])
def getfreeQuote():
    return render_template("free_quote.html")


@app.route('/projectquote')
def projectquote():
    return render_template("projectquote.html")


@app.route('/signup', methods = ['GET', 'POST'])
def signup():
    if request.method == 'POST':
        cnx.reconnect()
        firstname = request.form['firstName']
        lastname = request.form['lastName']
        email = request.form['email']
        dateOfBirth = request.form['dOB']
        password = request.form['uPass']
        encodePass = password.encode("utf-8")
        hashedPassword = bcrypt.hashpw(encodePass, bcrypt.gensalt())

        #generate random link
        confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        #adding query to insert into database
        with cnx.cursor(dictionary=True) as cur:
            cur.execute('''INSERT INTO clients (first_name, last_name, client_email, date_of_birth, password, confirmation_code, reset_token, phone_number, client_pic_path) 
                        VALUES (%s, %s, %s, %s, %s, %s, null, null, null)''', (firstname, lastname, email, dateOfBirth, hashedPassword, confirmation_code))
            cnx.commit()

        # Send a confirmation email to the user
        confirm_link = url_for('confirm_email', email=email, code=confirmation_code, _external=True)
        msg = Message('Please Confirm Your Email', sender='hello@oneredbox.ng', recipients=[email])
        msg.body = f'Thank you for registering! Please confirm your email address by clicking on the following link: {confirm_link}'
        mail.send(msg)

        return redirect(url_for('confirm_email'))

    return render_template("signup.html")



@app.route('/dashboard', methods = ['GET', 'POST'])
@login_required
def dashboard():
    
    query = '''
    SELECT * FROM clients
    JOIN projects ON clients.client_id = projects.client_id
    LEFT JOIN updates ON projects.project_id = updates.project_id
    WHERE clients.client_id = %s
    '''
    cnx.reconnect()
    with cnx.cursor(dictionary=True) as cur:
        cur.execute(query, (current_user.id,))
        rv = cur.fetchall()

    name = current_user.name
    unique_projects = []
    for item in rv:
        if item['project_id'] not in [p['project_id'] for p in unique_projects]:
            unique_projects.append({
                'project_id': item['project_id'],
                'project_desc': item['project_desc'],
                'contract_sum': item['contract_sum'],
                'amount_paid': item['amount_paid'],
                'amount_due': item['contract_sum'] - item['amount_paid'],
                'proj_image_path': item['proj_image_path'],
                'date_added': item['date_added'],
                'updates': []
            })
        for project in unique_projects:
            if project['project_id'] == item['project_id']:
                project['updates'].append({
                    'update_id': item['update_id'],
                    'update_desc': item['update_desc'],
                    'proj_status': "STARTED" if item['proj_status'] == 0 else "IN PROGRESS" if item['proj_status'] == 1 else "COMPLETED" if item['proj_status'] == 2 else item['proj_status']
                })

    with cnx.cursor(dictionary=True) as cur:
        cur.execute("SELECT client_pic_path FROM clients WHERE client_id = %s", (current_user.id,))
        picpath_dict = cur.fetchone()

    user_photo = picpath_dict['client_pic_path']

    if user_photo is not None:
        profilepic = user_photo.replace("static/", "")
    else:
        profilepic = "images/white_circle.png"

    #write code to bring up an alert box if the project is empty.
    return render_template("dashboard.html", unique_projects=unique_projects, name=name, profilepic = profilepic, paystackApiKey = paystackApiKey)


@app.route('/projects')
def projects():
    return render_template('projects.html')


@app.route('/get_current_user')
def get_current_user():
    if current_user.is_authenticated:
        user = {'id': current_user.id, 'email': current_user.email, 'name': current_user.name}
        return jsonify(user)
    else:
        return jsonify({'error': 'User not authenticated'})
    


@app.route('/newproject', methods = ['GET', 'POST'])
def newproject():
    config = {
        'user': 'root',
        'password': dbPass,
        'host': 'localhost',
        'database': "Oneredbox"
    }
    ncnx = mysql.connector.connect(**config)

    client_id = current_user.id
    email = current_user.email
    req = request.get_json()
    spaces = req['spaces']
    totalArea = calculateArea(spaces)
    totalCost = calculateCost(totalArea)

    bedroom = spaces['Bedroom']
    commercial = spaces['Commercial space (number of people)']
    kitchen = spaces['Kitchen']
    livrm = spaces['Living Room']
    study = spaces['Study']
    twBath = spaces['Toilet with bath']
    tWoBath = spaces['Toilet without bath']
    amountPaid = 0
    

    bedrooms = "bedroom" if bedroom == 1 else "bedrooms" if bedroom > 1 else ""
    commercial_spaces = "person commercial space" if commercial == 1 else "people commercial space" if commercial > 1 else ""
    kitchens = "kitchen" if kitchen == 1 else "kitchens" if kitchen > 1 else ""
    living_rooms = "living room" if livrm == 1 else "living rooms" if livrm > 1 else ""
    studies = "study" if study == 1 else "studies" if study > 1 else ""
    toilets_with_bath = "toilet with bath" if twBath == 1 else "toilets with bath" if twBath > 1 else ""
    toilets_without_bath = "toilet without bath" if tWoBath == 1 else "toilets without bath" if tWoBath > 1 else ""

    projDesc = ""
    if bedroom > 0:
        projDesc += "{} {}, ".format(bedroom, bedrooms)
    if livrm > 0:
        projDesc += "{} {}, ".format(livrm, living_rooms)
    if kitchen > 0:
        projDesc += "{} {}, ".format(kitchen, kitchens)
    if study > 0:
        projDesc += "{} {}, ".format(study, studies)
    if twBath > 0:
        projDesc += "{} {}, ".format(twBath, toilets_with_bath)
    if tWoBath > 0:
        projDesc += "{} {}, ".format(tWoBath, toilets_without_bath)
    if commercial > 0:
        projDesc += "{} {}, ".format(commercial, commercial_spaces)

    # Remove the trailing ", " at the end of the string
    if projDesc.endswith(", "):
        projDesc = projDesc[:-2]

    date_added = date.today()

    #adding query to insert into database
    with ncnx.cursor(dictionary=True) as cur:
        cur.execute('''INSERT INTO projects (project_desc, contract_sum, amount_paid, commercial, t_wo_bath, t_w_bath, study, kitchen, livingRm, bedroom, total_sq_area, proj_image_path, date_added, client_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, null, %s, %s)''', (projDesc, totalCost, amountPaid, commercial, tWoBath, twBath, study, kitchen, livrm, bedroom, totalArea, date_added, client_id))
        ncnx.commit()
        # Get the project ID of the newly created project
        project_id = cur.lastrowid


    # Insert a default update for the project
    update_desc = "Project brief created"
    proj_status = 0

    with ncnx.cursor(dictionary=True) as cur:
        cur.execute('''INSERT INTO updates (update_desc, proj_status, project_id) 
                    VALUES (%s, %s, %s)''', (update_desc, proj_status, project_id))
        ncnx.commit()

    # Send a confirmation email to the user
    msg = Message('Your new project', sender='hello@oneredbox.ng', recipients=[email])
    msg.body = f'''
                Hello {current_user.name}!,

                We are excited that you have created a new project. 

                Your project id is: {project_id}

                Your project description is: {projDesc}

                Please reply to this email with any further details about the project that you would like to share and someone from our team will reach out to you.

                Customer service
                Oneredbox.ng
                '''

    msg.body = re.sub(r'^( {4})+', '', msg.body, flags=re.MULTILINE)
    mail.send(msg)
    ncnx.close()

    # Redirect user to dashboard
    return redirect(url_for('dashboard'))


def calculateArea(spaces):
    bedrooom = spaces['Bedroom'] * 19.2
    commercial = spaces['Commercial space (number of people)'] * 6.6
    kitchen = spaces['Kitchen'] * 22
    livrm = spaces['Living Room'] * 30
    study = spaces['Study'] * 12.0
    twBath = spaces['Toilet with bath'] * 4.2
    tWoBath = spaces['Toilet without bath'] * 3.2
    circulation = 15.2

    total = bedrooom + commercial + kitchen + livrm + study + twBath + tWoBath + circulation
    totalArea = round(total, 2)
    
    return totalArea

def calculateCost(area):
    naira = area * 310000
    # cost = round(naira / 720)
    return naira

@app.route('/confirm_email')
def confirm_email():

    # Retrieve the email and confirmation code from the URL parameters
    email = request.args.get('email')
    code = request.args.get('code')

    # Check if the confirmation code is valid for this email
    with cnx.cursor(dictionary=True) as cur:
        cur.execute("SELECT client_id FROM clients WHERE client_email = %s AND confirmation_code = %s", (email, code))
        user = cur.fetchone()
        
    if user:
        # Update the confirmed column value to 1 for this user
        with cnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE clients SET confirmed = 1 WHERE client_email = %s AND confirmation_code = %s", (email, code))
            cnx.commit()

    
        return render_template('confirm_email.html')
    else:
        return 'Please confirm your email'
    

# Function to generate a random token
def generate_token(email, length=30):
    chars = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(chars) for i in range(length))
    return f'{email}-{random_string}'


# Route for the forgot password form
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Get the user's email or username from the form
        forgottenM = request.form['forgot_mail']

        # Check if the email or username is valid and associated with an account
        with cnx.cursor(dictionary=True) as cur:
            cur.execute("SELECT client_email FROM clients where client_email = %s", (forgottenM,))
            user = cur.fetchone()
        
        # If not, display an error message
        if not user:
            flash("No user with that e-mail found")
            return redirect(url_for('login'))
        else:
            email = user['client_email']
            # Otherwise, generate a unique token and store it in your database, associated with the user's account
            token = generate_token(email)
            # Send an email to the user with a link to the password reset page, along with the token in the URL parameters
            # Send a confirmation email to the user
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Reset Your Password', sender='hello@oneredbox.ng', recipients=[email])
            msg.body = f'You requested to reset your password, please ignore this mail if it was not you. Otherwhise please click this link to reset your password: {reset_url}'
            mail.send(msg)
            
            flash("A reset link has been sent to your email")

            cur.close()
            return redirect(url_for('projects'))
            # Redirect the user to a confirmation page
        
        # send email with the reset_url to the user

    return render_template('forgot_password.html')

# Route for the password reset form
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        # Get the new password from the form
        new_password = request.form['new_password']
        # Split the token into email and random string components
        email, random_string = token.split('-')

        
        # Check if the token is valid and associated with an account
        with cnx.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM clients WHERE client_email= %s", (email,))
            user = cur.fetchone()
        
        # If not, display an error message
        if not user:
            flash('Invalid or expired reset link', 'error')
            return redirect(url_for('forgot_password'))
        
        # Otherwise, update the user's password in your database
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
        with cnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE clients SET password = %s, reset_token = NULL WHERE client_email = %s", (hashed_password, email))
            cnx.commit()
        
        # Send a confirmation email to the user
        msg = Message('Your password has been reset', sender='hello@oneredbox.ng', recipients=[email])
        msg.body = 'Your password has been successfully reset. If you did not initiate this request, please contact our support team.'
        mail.send(msg)
        
        flash('Your password has been reset. Please log in with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)


@app.route('/update_database', methods=['POST'])
def update_database():
    data =request.get_json()
    projectId = data['jsonProjectId']
    paidAmount = data['paymentAmount']

    with cnx.cursor(dictionary=True) as cur:
        cur.execute("SELECT * FROM projects WHERE project_id = %s", (projectId,))
        project = cur.fetchone()
    
    if project:
        if project['amount_paid'] == 0:
            totalAmountPaid = paidAmount
        else:
            totalAmountPaid = project['amount_paid'] + paidAmount

        # Update the confirmed column 
        with cnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE projects SET amount_paid = %s WHERE project_id = %s", (totalAmountPaid, projectId))
            cnx.commit()

        return "Payment updated"
    else:
        print(f"No project found for project_id {projectId}")
        return "Project not found"
    

@app.route('/update_profile', methods=['POST'])
def update_profile():
    config = {
        'user': 'root',
        'password': dbPass,
        'host': 'localhost',
        'database': "Oneredbox"
    }
    pcnx = mysql.connector.connect(**config)

    phoneNumber = request.form.get('phoneNumber')
    file = request.files.get('profilePic')

    if file and phoneNumber:
        # Both phone number and profile picture provided
        filename = f"user_{current_user.id}.jpg"

        # Save uploaded image to disk
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Open the image and compress it
        with Image.open(filepath) as img:
            img.save(filepath, optimize=True, quality=50)

        # Update the user's profile with the new data
        with pcnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE clients SET client_pic_path = %s, phone_number = %s WHERE client_id = %s", (filepath, phoneNumber, current_user.id))
            pcnx.commit()
        # Close the connection after using it
        pcnx.close()

        return jsonify({"message": "Profile updated with phone number"})

    elif file:
        # Only profile picture provided
        filename = f"user_{current_user.id}.jpg"

        # Save uploaded image to disk
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Open the image and compress it
        with Image.open(filepath) as img:
            img.save(filepath, optimize=True, quality=50)

        # Update the user's profile with the new data
        with pcnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE clients SET client_pic_path = %s WHERE client_id = %s", (filepath, current_user.id))
            pcnx.commit()
        # Close the connection after using it
        pcnx.close()

        return jsonify({"message": "Profile picture updated"})

    elif phoneNumber:
        # Only phone number provided
        with pcnx.cursor(dictionary=True) as cur:
            cur.execute("UPDATE clients SET phone_number = %s WHERE client_id = %s", (phoneNumber, current_user.id))
            pcnx.commit()
        # Close the connection after using it
        pcnx.close()

        return jsonify({"message": "Phone number updated"})

    else:
        # Neither phone number nor profile picture provided
        return jsonify({"message": "No update provided"})


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # Clear the session
    session.clear()
    cnx.close()

    # Redirect to the home page
    return redirect(url_for('index'))


#if the name arugment is same as main run the app
if __name__ == "__main__":
    app.config['UPLOAD_FOLDER'] = 'static/userpics'
    app.run(host="0.0.0.0", port=5000)


'''
#adding <pagename> edits the route parameter
@app.route('/<firstname>/<lastname>')
def userpage(firstname, lastname):
    pyname = f'{firstname} {lastname}' #using an f string to assign two variables
    return render_template("userpage.html", name = pyname)
'''