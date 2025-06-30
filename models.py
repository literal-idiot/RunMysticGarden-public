from app import db
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import enum

class IntensityLevel(enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"

class PlantStage(enum.Enum):
    SEED = "seed"
    SPROUT = "sprout"
    SAPLING = "sapling"
    MATURE = "mature"
    BLOOMING = "blooming"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    runs = db.relationship('Run', backref='user', lazy=True, cascade='all, delete-orphan')
    coin_wallet = db.relationship('CoinWallet', backref='user', uselist=False, cascade='all, delete-orphan')
    garden = db.relationship('Garden', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

class Run(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    distance_km = db.Column(db.Float, nullable=False)  # Distance in kilometers
    duration_minutes = db.Column(db.Integer, nullable=False)  # Duration in minutes
    intensity = db.Column(db.Enum(IntensityLevel), nullable=False)
    pace_min_per_km = db.Column(db.Float)  # Calculated pace (minutes per km)
    coins_earned = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        # Calculate pace
        if self.duration_minutes and self.distance_km:
            self.pace_min_per_km = self.duration_minutes / self.distance_km
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'distance_km': self.distance_km,
            'duration_minutes': self.duration_minutes,
            'intensity': self.intensity.value,
            'pace_min_per_km': self.pace_min_per_km,
            'coins_earned': self.coins_earned,
            'created_at': self.created_at.isoformat()
        }

class CoinWallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def add_coins(self, amount):
        self.balance += amount
        self.total_earned += amount
        self.updated_at = datetime.now(timezone.utc)
    
    def spend_coins(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.total_spent += amount
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'balance': self.balance,
            'total_earned': self.total_earned,
            'total_spent': self.total_spent,
            'updated_at': self.updated_at.isoformat()
        }

class Seed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    cost_coins = db.Column(db.Integer, nullable=False)
    growth_requirements = db.Column(db.JSON)  # JSON object with requirements
    rarity = db.Column(db.String(20), default='common')  # common, rare, epic, legendary
    plant_type = db.Column(db.String(50))  # flower, tree, herb, etc.
    is_available = db.Column(db.Boolean, default=True)
    
    # Relationships
    plants = db.relationship('Plant', backref='seed', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'cost_coins': self.cost_coins,
            'growth_requirements': self.growth_requirements,
            'rarity': self.rarity,
            'plant_type': self.plant_type,
            'is_available': self.is_available
        }

class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=False)
    seed_id = db.Column(db.Integer, db.ForeignKey('seed.id'), nullable=False)
    name = db.Column(db.String(100))  # Custom name given by user
    stage = db.Column(db.Enum(PlantStage), default=PlantStage.SEED)
    growth_progress = db.Column(db.Float, default=0.0)  # 0.0 to 100.0
    health = db.Column(db.Float, default=100.0)  # 0.0 to 100.0
    last_watered = db.Column(db.DateTime)  # Metaphorical watering through running
    planted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    position_x = db.Column(db.Integer, default=0)  # Garden position
    position_y = db.Column(db.Integer, default=0)  # Garden position
    
    def water(self, run_distance, run_intensity):
        """Update plant growth based on running activity"""
        # Base growth from distance
        growth_boost = run_distance * 2  # 2 points per km
        
        # Intensity multiplier
        intensity_multipliers = {
            IntensityLevel.LOW: 1.0,
            IntensityLevel.MODERATE: 1.2,
            IntensityLevel.HIGH: 1.5,
            IntensityLevel.EXTREME: 2.0
        }
        
        growth_boost *= intensity_multipliers.get(run_intensity, 1.0)
        
        # Add to growth progress
        self.growth_progress = min(100.0, self.growth_progress + growth_boost)
        self.last_watered = datetime.now(timezone.utc)
        
        # Update stage based on progress
        if self.growth_progress >= 80:
            self.stage = PlantStage.BLOOMING
        elif self.growth_progress >= 60:
            self.stage = PlantStage.MATURE
        elif self.growth_progress >= 40:
            self.stage = PlantStage.SAPLING
        elif self.growth_progress >= 20:
            self.stage = PlantStage.SPROUT
    
    def to_dict(self):
        return {
            'id': self.id,
            'garden_id': self.garden_id,
            'seed_id': self.seed_id,
            'name': self.name,
            'stage': self.stage.value,
            'growth_progress': self.growth_progress,
            'health': self.health,
            'last_watered': self.last_watered.isoformat() if self.last_watered else None,
            'planted_at': self.planted_at.isoformat(),
            'position_x': self.position_x,
            'position_y': self.position_y,
            'seed': self.seed.to_dict() if self.seed else None
        }

class SeedInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seed_id = db.Column(db.Integer, db.ForeignKey('seed.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Allows you to access the specific seed that was purchased (?)
    seed = db.relationship('Seed')

    # Ensures that for each seed there is only one row (prevents duplicate rows of 1 seed)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'seed_id', name='unique_seed_per_user'),
    )

    def add_quantity(self, amount):
        if amount < 0:
            raise ValueError("Amount to add must be non-negative")
        self.quantity += amount

    def remove_quantity(self, amount):
        if amount < 0:
            raise ValueError("Amount to remove must be non-negative")
        if self.quantity < amount:
            raise ValueError("Insufficient quantity to remove")
        self.quantity -= amount
    
    def to_dict(self):
        return {
            'seed_id': self.seed_id,
            'quantity': self.quantity,
            'seed': {
                'name': self.seed.name,
                'plant_type': self.seed.plant_type,
                'rarity': self.seed.rarity,
            } if self.seed else None
        }

class Garden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), default='My Mystical Garden')
    size_x = db.Column(db.Integer, default=10)  # Garden dimensions
    size_y = db.Column(db.Integer, default=10)
    level = db.Column(db.Integer, default=1)
    experience_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    plants = db.relationship('Plant', backref='garden', lazy=True, cascade='all, delete-orphan')
    
    def add_experience(self, points):
        self.experience_points += points
        # Level up every 1000 XP
        new_level = (self.experience_points // 1000) + 1
        if new_level > self.level:
            self.level = new_level
            # Expand garden size with each level
            self.size_x = min(20, 10 + self.level)
            self.size_y = min(20, 10 + self.level)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'size_x': self.size_x,
            'size_y': self.size_y,
            'level': self.level,
            'experience_points': self.experience_points,
            'created_at': self.created_at.isoformat(),
            'plants': [plant.to_dict() for plant in self.plants]
        }
