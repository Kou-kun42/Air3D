from flask import (
    request,
    redirect,
    render_template,
    url_for,
    Blueprint,
    session,
    flash,
    jsonify
)
from werkzeug.utils import secure_filename
from flask_uploads import UploadSet, IMAGES, configure_uploads
from bson.objectid import ObjectId
import requests
import os
from dotenv import load_dotenv
from air3d_app import app, db, socketio
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date, datetime
from air3d_app.models import User, Profile, Requests, Design
from air3d_app.main.forms import ProfileForm, RequestForm, DesignForm
from air3d_app import bcrypt
import stripe

main = Blueprint('main', __name__)


# Create Upload sets for offers and design requests
offers = UploadSet("offers", IMAGES)
design_requests = UploadSet("requests", IMAGES)
configure_uploads(app, (offers, design_requests))

# Set Stripe Variables
load_dotenv()

stripe_keys = {
    "secret_key": os.getenv("STRIPE_SECRET_KEY"),
    "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY"),
    # "endpoint_secret": os.environ["STRIPE_ENDPOINT_SECRET"],
}

stripe.api_key = stripe_keys["secret_key"]


# Homepage
@main.route('/')
def home():
    '''Display homepage'''
    return render_template('home.html')


# Product Offers
@main.route('/product-offers')
def product_offers():
    '''Display product offers'''
    return render_template('product-offers.html')


@main.route('/order-form', methods=['GET', 'POST'])
def create_request():
    """Create a request for a product."""
    form = RequestForm()
    if form.validate_on_submit():
        new_request = Requests(
            username=form.username.data,
            email=form.email.data,
            description=form.description.data
        )
        db.session.add(new_request)
        db.session.commit()

        flash('New request submitted successfully.')
        return redirect(url_for('main.home'))

    # if form was not valid, or was not submitted yet
    return render_template('order-form.html', form=form)


@main.route('/product-requests')
@login_required
def product_requests():
    """View list of all submitted product requests."""
    all_requests = Requests.query.all()
    return render_template('product-requests.html',
                           all_requests=all_requests)


@main.route('/create_profile', methods=['GET', 'POST'])
@login_required
def create_profile():
    """Create a public profile."""
    form = ProfileForm()
    # if form was submitted and contained no errors
    if form.validate_on_submit():
        new_profile = Profile(
            username=form.username.data
        )
        db.session.add(new_profile)
        db.session.commit()

        flash('New profile was created successfully.')
        return redirect(url_for('main.home'))

    # if form was not valid, or was not submitted yet
    return render_template('create_profile.html', form=form)


# Check to make sure the upload type is allowed
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


# Order Form
@main.route('/order-form', methods=['GET', 'POST'])
def order_form():
    '''Display order form'''
    # Handle file upload
    if request.method == 'POST' and 'request' in request.files:
        design_requests.save(request.files['request'])
        flash("Request submitted")
        return render_template('order-form.html')
    return render_template('order-form.html')


@main.route('/profile/<full_name>')
def profile(full_name):
    """View public profile of a user."""
    # user = User.query.filter_by(username=username).one()
    profile = Profile.query.filter_by(username=current_user.username).first()
    return render_template('profile.html', profile=profile)


# Product Offers Upload Form
@main.route('/design-upload-form')
def design_upload_form():
    '''Display design upload form'''
    # Handle file upload
    if request.method == 'POST' and 'offer' in request.files:
        offers.save(request.files['offer'])
        flash("Offer submitted")
        return render_template('design-upload-form.html')
    return render_template('design-upload-form.html')


# Chat Page
@main.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    return render_template('chat.html')


def receive_message(methods=['GET', 'POST']):
    print("New Message")


@socketio.on('message')
def message(json):
    print(str(json))
    socketio.emit('response', json, callback=receive_message)



# Stripe routes

# Homepage
@main.route('/purchase')
def purchase():
    '''Display purchase page'''
    return render_template('stripe.html')

@main.route("/config")
def get_publishable_key():
    stripe_config = {"publicKey": stripe_keys["publishable_key"]}
    return jsonify(stripe_config)

@main.route("/create-checkout-session")
def create_checkout_session():
    domain_url = "https://air3d.herokuapp.com/"
    stripe.api_key = stripe_keys["secret_key"]

    try:
        # Create new Checkout Session for the order
        # Other optional params include:
        # [billing_address_collection] - to display billing address details on the page
        # [customer] - if you have an existing Stripe Customer ID
        # [payment_intent_data] - capture the payment later
        # [customer_email] - prefill the email input in the form
        # For full details see https://stripe.com/docs/api/checkout/sessions/create

        # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
        checkout_session = stripe.checkout.Session.create(
            success_url=domain_url + "success?session_id={CHECKOUT_SESSION_ID}",
            # success_url=domain_url + "success?session_id=price_1KHG2eJSgrm4MfoGb7iF4qFA",
            cancel_url=domain_url + "cancelled",
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "name": "3D Print Service",
                    "quantity": 1,
                    "currency": "usd",
                    "amount": "2000",
                }
            ]
        )
        return jsonify({"sessionId": checkout_session["id"]})
    except Exception as e:
        return jsonify(error=str(e)), 403


@main.route("/success")
def success():
    return render_template("success.html")


@main.route("/cancelled")
def cancelled():
    return render_template("cancelled.html")


@main.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_keys["endpoint_secret"]
        )

    except ValueError as e:
        # Invalid payload
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return "Invalid signature", 400

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        print("Payment was successful.")
        # TODO: run some custom code here

    return "Success", 200
