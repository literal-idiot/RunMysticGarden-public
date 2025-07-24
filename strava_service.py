import os
import time
import requests
from datetime import datetime, timezone, timedelta
from stravalib.client import Client
from stravalib import exc
from app import db
from models import StravaAccount, User, Run, IntensityLevel
from utils import calculate_coins_for_run
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class StravaService:
    def __init__(self):
        self.client_id = os.environ.get('STRAVA_CLIENT_ID', '167433')
        self.client_secret = os.environ.get('STRAVA_CLIENT_SECRET', '15e7b8ff9efa35ec7e4d770d7161b3ae7b52f526')
        self.redirect_uri = None  # Will be set dynamically
        
        if not self.client_id or not self.client_secret:
            logger.warning("Strava credentials not found in environment variables")
    
    def get_authorization_url(self, redirect_uri):
        """Generate Strava OAuth authorization URL"""
        self.redirect_uri = redirect_uri
        client = Client()
        
        auth_url = client.authorization_url(
            client_id=int(self.client_id),
            redirect_uri=redirect_uri,
            scope=['read', 'activity:read_all', 'profile:read_all']
        )
        
        return auth_url
    
    def exchange_code_for_token(self, code, redirect_uri):
        """Exchange authorization code for access token"""
        client = Client()
        
        try:
            token_response = client.exchange_code_for_token(
                client_id=int(self.client_id),
                client_secret=self.client_secret,
                code=code
            )
            
            return {
                'access_token': token_response.get('access_token'),
                'refresh_token': token_response.get('refresh_token'),
                'expires_at': datetime.fromtimestamp(token_response.get('expires_at', 0), tz=timezone.utc),
                'athlete': token_response.get('athlete')
            }
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {str(e)}")
            raise
    
    def refresh_access_token(self, refresh_token):
        """Refresh expired access token"""
        try:
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post('https://www.strava.com/oauth/token', data=payload)
            response.raise_for_status()
            
            token_data = response.json()
            
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'],
                'expires_at': datetime.fromtimestamp(token_data['expires_at'], tz=timezone.utc)
            }
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise
    
    def get_client_for_user(self, user_id):
        """Get authenticated Strava client for user"""
        strava_account = StravaAccount.query.filter_by(user_id=user_id, is_active=True).first()
        
        if not strava_account:
            return None
        
        # Check if token needs refresh
        if strava_account.is_token_expired():
            try:
                new_tokens = self.refresh_access_token(strava_account.refresh_token)
                
                # Update tokens in database
                strava_account.access_token = new_tokens['access_token']
                strava_account.refresh_token = new_tokens['refresh_token']
                strava_account.expires_at = new_tokens['expires_at']
                
                db.session.commit()
                
                logger.info(f"Refreshed Strava token for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to refresh token for user {user_id}: {str(e)}")
                return None
        
        # Create authenticated client
        client = Client(access_token=strava_account.access_token)
        return client
    
    def sync_recent_activities(self, user_id, days_back=7):
        """Sync recent activities from Strava"""
        client = self.get_client_for_user(user_id)
        if not client:
            return {"error": "No valid Strava connection"}
        
        try:
            # Get activities from the last week
            after_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            activities = client.get_activities(after=after_date, limit=50)
            
            synced_count = 0
            skipped_count = 0
            
            for activity in activities:
                # Only sync running activities
                activity_type = str(activity.type).lower() if activity.type else ''
                if activity_type not in ['run', 'virtualrun']:
                    continue
                
                # Check if activity already exists
                start_date = activity.start_date_local
                if start_date and hasattr(start_date, 'replace'):
                    start_date = start_date.replace(tzinfo=timezone.utc)
                else:
                    start_date = datetime.now(timezone.utc)
                
                existing_run = Run.query.filter_by(
                    user_id=user_id,
                    created_at=start_date
                ).first()
                
                if existing_run:
                    skipped_count += 1
                    continue
                
                # Convert Strava activity to our Run model
                distance_km = float(activity.distance or 0) / 1000  # Convert meters to km
                moving_time = activity.moving_time
                if moving_time and hasattr(moving_time, 'total_seconds'):
                    duration_minutes = int(moving_time.total_seconds() / 60)
                else:
                    duration_minutes = 0
                
                # Determine intensity based on pace
                pace_min_per_km = duration_minutes / distance_km if distance_km > 0 else 0
                
                if pace_min_per_km <= 4:
                    intensity = IntensityLevel.EXTREME
                elif pace_min_per_km <= 5:
                    intensity = IntensityLevel.HIGH
                elif pace_min_per_km <= 6.5:
                    intensity = IntensityLevel.MODERATE
                else:
                    intensity = IntensityLevel.LOW
                
                # Calculate coins
                coins_earned = calculate_coins_for_run(distance_km, intensity)
                
                # Create run record
                run = Run()
                run.user_id = user_id
                run.distance_km = distance_km
                run.duration_minutes = duration_minutes
                run.intensity = intensity
                run.pace_min_per_km = pace_min_per_km
                run.coins_earned = coins_earned
                run.created_at = start_date
                
                db.session.add(run)
                synced_count += 1
            
            # Update user's coins and garden
            if synced_count > 0:
                from models import CoinWallet, Garden
                
                wallet = CoinWallet.query.filter_by(user_id=user_id).first()
                if wallet:
                    total_coins = sum(run.coins_earned for run in Run.query.filter_by(user_id=user_id).all())
                    wallet.balance = total_coins
                    wallet.total_earned = total_coins
                
                # Update garden experience
                garden = Garden.query.filter_by(user_id=user_id).first()
                if garden:
                    total_distance = sum(run.distance_km for run in Run.query.filter_by(user_id=user_id).all())
                    garden.add_experience(int(total_distance * 10))
                    
                    # Water plants based on recent activity
                    for plant in garden.plants:
                        # Use the most recent run for watering
                        recent_run = Run.query.filter_by(user_id=user_id).order_by(Run.created_at.desc()).first()
                        if recent_run:
                            plant.water(recent_run.distance_km, recent_run.intensity)
            
            # Update last sync time
            strava_account = StravaAccount.query.filter_by(user_id=user_id, is_active=True).first()
            if strava_account:
                strava_account.last_sync = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return {
                "success": True,
                "synced_activities": synced_count,
                "skipped_activities": skipped_count,
                "total_checked": synced_count + skipped_count
            }
            
        except exc.RateLimitExceeded as e:
            logger.warning(f"Strava rate limit exceeded: {str(e)}")
            return {"error": "Strava rate limit exceeded. Please try again later."}
        except Exception as e:
            logger.error(f"Failed to sync activities: {str(e)}")
            return {"error": f"Failed to sync activities: {str(e)}"}
    
    def get_athlete_stats(self, user_id):
        """Get athlete statistics from Strava"""
        client = self.get_client_for_user(user_id)
        if not client:
            return None
        
        try:
            strava_account = StravaAccount.query.filter_by(user_id=user_id, is_active=True).first()
            if not strava_account:
                return None
            
            athlete_stats = client.get_athlete_stats(strava_account.strava_athlete_id)
            
            recent_totals = athlete_stats.recent_run_totals
            all_totals = athlete_stats.all_run_totals
            
            return {
                'recent_run_totals': {
                    'count': getattr(recent_totals, 'count', 0),
                    'distance': float(getattr(recent_totals, 'distance', 0) or 0) / 1000,  # Convert to km
                    'moving_time': getattr(recent_totals, 'moving_time', 0),
                    'elapsed_time': getattr(recent_totals, 'elapsed_time', 0),
                    'elevation_gain': getattr(recent_totals, 'elevation_gain', 0)
                },
                'all_run_totals': {
                    'count': getattr(all_totals, 'count', 0),
                    'distance': float(getattr(all_totals, 'distance', 0) or 0) / 1000,  # Convert to km
                    'moving_time': getattr(all_totals, 'moving_time', 0),
                    'elapsed_time': getattr(all_totals, 'elapsed_time', 0),
                    'elevation_gain': getattr(all_totals, 'elevation_gain', 0)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get athlete stats: {str(e)}")
            return None

# Global service instance
strava_service = StravaService()