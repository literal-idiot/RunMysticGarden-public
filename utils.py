from app import db
from models import Seed, IntensityLevel

def calculate_coins_for_run(distance_km, intensity):
    """Calculate coins earned for a run based on distance and intensity"""
    # Base coins: 10 coins per km
    base_coins = int(distance_km * 10)
    
    # Intensity multipliers
    intensity_multipliers = {
        IntensityLevel.LOW: 1.0,
        IntensityLevel.MODERATE: 1.2,
        IntensityLevel.HIGH: 1.5,
        IntensityLevel.EXTREME: 2.0
    }
    
    multiplier = intensity_multipliers.get(intensity, 1.0)
    total_coins = int(base_coins * multiplier)
    
    # Bonus for longer runs
    if distance_km >= 10:
        total_coins += 50  # Bonus for 10K+
    if distance_km >= 21.1:
        total_coins += 100  # Bonus for half marathon+
    if distance_km >= 42.2:
        total_coins += 200  # Bonus for marathon+
    
    return total_coins

def create_default_seeds():
    """Create default seeds if they don't exist"""
    default_seeds = [
        {
            'name': 'Mystic Rose',
            'description': 'A beautiful rose that blooms with magical energy. Requires consistent running to flourish.',
            'cost_coins': 50,
            'growth_requirements': {
                'min_weekly_distance': 10,
                'preferred_intensity': 'moderate'
            },
            'rarity': 'common',
            'plant_type': 'flower'
        },
        {
            'name': 'Runner\'s Mint',
            'description': 'An energizing herb that thrives on high-intensity workouts.',
            'cost_coins': 75,
            'growth_requirements': {
                'min_weekly_distance': 15,
                'preferred_intensity': 'high'
            },
            'rarity': 'common',
            'plant_type': 'herb'
        },
        {
            'name': 'Endurance Oak',
            'description': 'A mighty oak tree that grows stronger with long-distance runs.',
            'cost_coins': 150,
            'growth_requirements': {
                'min_weekly_distance': 25,
                'preferred_intensity': 'low'
            },
            'rarity': 'rare',
            'plant_type': 'tree'
        },
        {
            'name': 'Speed Lotus',
            'description': 'An exotic lotus that responds to bursts of extreme intensity.',
            'cost_coins': 200,
            'growth_requirements': {
                'min_weekly_distance': 20,
                'preferred_intensity': 'extreme'
            },
            'rarity': 'rare',
            'plant_type': 'flower'
        },
        {
            'name': 'Phoenix Fern',
            'description': 'A legendary fern that only grows for the most dedicated runners.',
            'cost_coins': 500,
            'growth_requirements': {
                'min_weekly_distance': 50,
                'preferred_intensity': 'high'
            },
            'rarity': 'epic',
            'plant_type': 'fern'
        },
        {
            'name': 'Celestial Bamboo',
            'description': 'Divine bamboo that reaches toward the heavens with every mile you run.',
            'cost_coins': 1000,
            'growth_requirements': {
                'min_weekly_distance': 100,
                'preferred_intensity': 'moderate'
            },
            'rarity': 'legendary',
            'plant_type': 'bamboo'
        }
    ]
    
    for seed_data in default_seeds:
        existing_seed = Seed.query.filter_by(name=seed_data['name']).first()
        if not existing_seed:
            seed = Seed(**seed_data)
            db.session.add(seed)
