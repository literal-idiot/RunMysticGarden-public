from flask import Blueprint, request, jsonify, redirect, url_for
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from models import User, CoinWallet, Garden, Seed, StravaAccount
from strava_service import strava_service
from datetime import datetime, timezone, timedelta
import re
import os

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    return len(password) >= 8

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').lower().strip()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Validation
        if not email or not username or not password:
            return jsonify({'error': 'Email, username, and password are required'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        if len(username) < 3 or len(username) > 64:
            return jsonify({'error': 'Username must be between 3 and 64 characters'}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already taken'}), 409
        
        # Create new user
        user = User()
        user.email = email
        user.username = username
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create coin wallet
        wallet = CoinWallet()
        wallet.user_id = user.id
        db.session.add(wallet)
        
        # Create garden
        garden = Garden()
        garden.user_id = user.id
        db.session.add(garden)
        
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'User registered successfully',
            'access_token': access_token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Create access token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get profile: {str(e)}'}), 500

@auth_bp.route('/strava/connect', methods=['GET'])
@jwt_required()
def connect_strava():
    """Initiate Strava OAuth connection"""
    try:
        # Get the current domain for redirect URI
        host = request.headers.get('Host', 'localhost:5000')
        protocol = 'https' if 'replit.app' in host else 'http'
        redirect_uri = f"{protocol}://{host}/auth/strava/callback"
        
        # Generate authorization URL
        auth_url = strava_service.get_authorization_url(redirect_uri)
        
        return jsonify({
            'authorization_url': auth_url,
            'message': 'Visit the authorization URL to connect your Strava account'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to initiate Strava connection: {str(e)}'}), 500

@auth_bp.route('/strava/callback', methods=['GET'])
def strava_callback():
    """Handle Strava OAuth callback"""
    try:
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            return jsonify({'error': f'Strava authorization failed: {error}'}), 400
        
        if not code:
            return jsonify({'error': 'No authorization code received'}), 400
        
        # Get redirect URI
        host = request.headers.get('Host', 'localhost:5000')
        protocol = 'https' if 'replit.app' in host else 'http'
        redirect_uri = f"{protocol}://{host}/auth/strava/callback"
        
        # Exchange code for tokens
        token_data = strava_service.exchange_code_for_token(code, redirect_uri)
        
        # For now, return the tokens and athlete info
        # In a real app, you'd want to associate this with a logged-in user
        return jsonify({
            'message': 'Strava connection successful! Please save your access token and use it with the /auth/strava/link endpoint.',
            'access_token': token_data['access_token'],
            'athlete_info': {
                'id': token_data['athlete']['id'],
                'firstname': token_data['athlete']['firstname'],
                'lastname': token_data['athlete']['lastname'],
                'city': token_data['athlete']['city'],
                'country': token_data['athlete']['country']
            },
            'instructions': 'Use POST /auth/strava/link with your JWT token and the access_token to link your account.'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to process Strava callback: {str(e)}'}), 500

@auth_bp.route('/strava/link', methods=['POST'])
@jwt_required()
def link_strava_account():
    """Link Strava account to user profile"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'access_token' not in data:
            return jsonify({'error': 'Access token is required'}), 400
        
        access_token = data['access_token']
        
        # Use the access token to get athlete info - for simplicity, we'll use the token directly
        # In a real implementation, you'd get the full token data from the callback
        # For now, we'll create a placeholder for the missing fields
        try:
            from stravalib.client import Client
            client = Client(access_token=access_token)
            athlete = client.get_athlete()
        except Exception as e:
            return jsonify({'error': f'Invalid access token: {str(e)}'}), 400
        
        # Check if this Strava account is already linked to another user
        existing_account = StravaAccount.query.filter_by(
            strava_athlete_id=athlete.id,
            is_active=True
        ).first()
        
        if existing_account and existing_account.user_id != user_id:
            return jsonify({'error': 'This Strava account is already linked to another user'}), 409
        
        # Check if user already has a Strava account linked
        user_strava_account = StravaAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if user_strava_account:
            # Update existing account
            user_strava_account.strava_athlete_id = athlete.id
            user_strava_account.access_token = access_token
            user_strava_account.refresh_token = 'placeholder_refresh_token'  # Will be updated via full OAuth flow
            user_strava_account.expires_at = datetime.now(timezone.utc) + timedelta(hours=6)  # Strava tokens expire in 6 hours
            user_strava_account.athlete_firstname = athlete.firstname
            user_strava_account.athlete_lastname = athlete.lastname
            user_strava_account.athlete_city = athlete.city
            user_strava_account.athlete_country = athlete.country
            user_strava_account.athlete_profile_picture = str(athlete.profile) if athlete.profile else None
            user_strava_account.connected_at = datetime.now(timezone.utc)
            
            message = 'Strava account updated successfully'
        else:
            # Create new account link
            user_strava_account = StravaAccount()
            user_strava_account.user_id = user_id
            user_strava_account.strava_athlete_id = athlete.id
            user_strava_account.access_token = access_token
            user_strava_account.refresh_token = 'placeholder_refresh_token'  # Will be updated via full OAuth flow
            user_strava_account.expires_at = datetime.now(timezone.utc) + timedelta(hours=6)  # Strava tokens expire in 6 hours
            user_strava_account.athlete_firstname = athlete.firstname
            user_strava_account.athlete_lastname = athlete.lastname
            user_strava_account.athlete_city = athlete.city
            user_strava_account.athlete_country = athlete.country
            user_strava_account.athlete_profile_picture = str(athlete.profile) if athlete.profile else None
            
            db.session.add(user_strava_account)
            message = 'Strava account linked successfully'
        
        db.session.commit()
        
        return jsonify({
            'message': message,
            'strava_account': user_strava_account.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to link Strava account: {str(e)}'}), 500

@auth_bp.route('/strava/disconnect', methods=['POST'])
@jwt_required()
def disconnect_strava():
    """Disconnect Strava account"""
    try:
        user_id = get_jwt_identity()
        
        strava_account = StravaAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if not strava_account:
            return jsonify({'error': 'No Strava account connected'}), 404
        
        # Deactivate the account instead of deleting to preserve history
        strava_account.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Strava account disconnected successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to disconnect Strava account: {str(e)}'}), 500

@auth_bp.route('/strava/status', methods=['GET'])
@jwt_required()
def strava_status():
    """Get Strava connection status"""
    try:
        user_id = get_jwt_identity()
        
        strava_account = StravaAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if not strava_account:
            return jsonify({
                'connected': False,
                'message': 'No Strava account connected'
            }), 200
        
        return jsonify({
            'connected': True,
            'strava_account': strava_account.to_dict(),
            'token_expired': strava_account.is_token_expired()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get Strava status: {str(e)}'}), 500
