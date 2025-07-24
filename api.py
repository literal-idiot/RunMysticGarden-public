from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models import User, Run, CoinWallet, Seed, Plant, Garden, IntensityLevel, PlantStage
from utils import calculate_coins_for_run, create_default_seeds
from datetime import datetime, timezone

api_bp = Blueprint('api', __name__)

@api_bp.route('/runs', methods=['POST'])
@jwt_required()
def log_run():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        distance_km = data.get('distance_km')
        duration_minutes = data.get('duration_minutes')
        intensity = data.get('intensity', 'moderate')
        
        # Validation
        if not distance_km or not duration_minutes:
            return jsonify({'error': 'Distance and duration are required'}), 400
        
        try:
            distance_km = float(distance_km)
            duration_minutes = int(duration_minutes)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid distance or duration format'}), 400
        
        if distance_km <= 0 or duration_minutes <= 0:
            return jsonify({'error': 'Distance and duration must be positive'}), 400
        
        if distance_km > 200:  # Reasonable upper limit
            return jsonify({'error': 'Distance seems unrealistic (max 200km)'}), 400
        
        if duration_minutes > 1440:  # Max 24 hours
            return jsonify({'error': 'Duration seems unrealistic (max 24 hours)'}), 400
        
        # Validate intensity
        try:
            intensity_enum = IntensityLevel(intensity.lower())
        except ValueError:
            return jsonify({'error': 'Invalid intensity level. Use: low, moderate, high, extreme'}), 400
        
        # Calculate pace
        pace_min_per_km = duration_minutes / distance_km
        
        # Calculate coins earned
        coins_earned = calculate_coins_for_run(distance_km, intensity_enum)
        
        # Create run record
        run = Run()
        run.user_id = user_id
        run.distance_km = distance_km
        run.duration_minutes = duration_minutes
        run.intensity = intensity_enum
        run.pace_min_per_km = pace_min_per_km
        run.coins_earned = coins_earned
        
        db.session.add(run)
        
        # Update coin wallet
        wallet = CoinWallet.query.filter_by(user_id=user_id).first()
        if not wallet:
            wallet = CoinWallet()
            wallet.user_id = user_id
            db.session.add(wallet)
        
        wallet.add_coins(coins_earned)
        
        # Update garden and plants
        garden = Garden.query.filter_by(user_id=user_id).first()
        if garden:
            # Add experience to garden
            experience_points = int(distance_km * 10)  # 10 XP per km
            garden.add_experience(experience_points)
            
            # Water all plants in the garden
            for plant in garden.plants:
                plant.water(distance_km, intensity_enum)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Run logged successfully',
            'run': run.to_dict(),
            'coins_earned': coins_earned,
            'total_coins': wallet.balance
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to log run: {str(e)}'}), 500

@api_bp.route('/runs', methods=['GET'])
@jwt_required()
def get_runs():
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        runs = Run.query.filter_by(user_id=user_id).order_by(Run.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'runs': [run.to_dict() for run in runs.items],
            'pagination': {
                'page': runs.page,
                'pages': runs.pages,
                'total': runs.total,
                'per_page': runs.per_page
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get runs: {str(e)}'}), 500

@api_bp.route('/wallet', methods=['GET'])
@jwt_required()
def get_wallet():
    try:
        user_id = get_jwt_identity()
        wallet = CoinWallet.query.filter_by(user_id=user_id).first()
        
        if not wallet:
            wallet = CoinWallet()
            wallet.user_id = user_id
            db.session.add(wallet)
            db.session.commit()
        
        return jsonify({'wallet': wallet.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get wallet: {str(e)}'}), 500

@api_bp.route('/seeds', methods=['GET'])
@jwt_required()
def get_seeds():
    try:
        # Ensure default seeds exist
        if Seed.query.count() == 0:
            create_default_seeds()
            db.session.commit()
        
        seeds = Seed.query.filter_by(is_available=True).all()
        
        return jsonify({
            'seeds': [seed.to_dict() for seed in seeds]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get seeds: {str(e)}'}), 500

@api_bp.route('/seeds/<int:seed_id>/buy', methods=['POST'])
@jwt_required()
def buy_seed(seed_id):
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}
        
        # Get seed
        seed = Seed.query.get(seed_id)
        if not seed or not seed.is_available:
            return jsonify({'error': 'Seed not found or not available'}), 404
        
        # Get user's wallet
        wallet = CoinWallet.query.filter_by(user_id=user_id).first()
        if not wallet or wallet.balance < seed.cost_coins:
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Get user's garden
        garden = Garden.query.filter_by(user_id=user_id).first()
        if not garden:
            return jsonify({'error': 'Garden not found'}), 404
        
        # Check garden space
        max_plants = garden.size_x * garden.size_y
        current_plants = len(garden.plants)
        if current_plants >= max_plants:
            return jsonify({'error': 'Garden is full. Level up to expand!'}), 400
        
        # Get position
        position_x = data.get('position_x', 0)
        position_y = data.get('position_y', 0)
        
        # Validate position
        if position_x < 0 or position_x >= garden.size_x or position_y < 0 or position_y >= garden.size_y:
            return jsonify({'error': 'Invalid position'}), 400
        
        # Check if position is occupied
        existing_plant = Plant.query.filter_by(
            garden_id=garden.id,
            position_x=position_x,
            position_y=position_y
        ).first()
        
        if existing_plant:
            return jsonify({'error': 'Position already occupied'}), 400
        
        # Process purchase
        wallet.spend_coins(seed.cost_coins)
        
        # Plant the seed
        plant = Plant()
        plant.garden_id = garden.id
        plant.seed_id = seed.id
        plant.position_x = position_x
        plant.position_y = position_y
        plant.name = data.get('name', seed.name)
        
        db.session.add(plant)
        db.session.commit()
        
        return jsonify({
            'message': 'Seed purchased and planted successfully',
            'plant': plant.to_dict(),
            'remaining_coins': wallet.balance
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to buy seed: {str(e)}'}), 500

@api_bp.route('/garden', methods=['GET'])
@jwt_required()
def get_garden():
    try:
        user_id = get_jwt_identity()
        garden = Garden.query.filter_by(user_id=user_id).first()
        
        if not garden:
            garden = Garden()
            garden.user_id = user_id
            db.session.add(garden)
            db.session.commit()
        
        return jsonify({'garden': garden.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get garden: {str(e)}'}), 500

@api_bp.route('/garden', methods=['PUT'])
@jwt_required()
def update_garden():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        garden = Garden.query.filter_by(user_id=user_id).first()
        if not garden:
            return jsonify({'error': 'Garden not found'}), 404
        
        # Update garden name
        if 'name' in data:
            garden.name = data['name'][:100]  # Limit length
        
        db.session.commit()
        
        return jsonify({
            'message': 'Garden updated successfully',
            'garden': garden.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update garden: {str(e)}'}), 500

@api_bp.route('/plants/<int:plant_id>', methods=['PUT'])
@jwt_required()
def update_plant(plant_id):
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get plant and verify ownership
        plant = Plant.query.join(Garden).filter(
            Plant.id == plant_id,
            Garden.user_id == user_id
        ).first()
        
        if not plant:
            return jsonify({'error': 'Plant not found'}), 404
        
        # Update plant name
        if 'name' in data:
            plant.name = data['name'][:100]  # Limit length
        
        # Update position if provided
        if 'position_x' in data and 'position_y' in data:
            position_x = int(data['position_x'])
            position_y = int(data['position_y'])
            
            # Validate position
            if (position_x < 0 or position_x >= plant.garden.size_x or 
                position_y < 0 or position_y >= plant.garden.size_y):
                return jsonify({'error': 'Invalid position'}), 400
            
            # Check if position is occupied by another plant
            existing_plant = Plant.query.filter_by(
                garden_id=plant.garden_id,
                position_x=position_x,
                position_y=position_y
            ).filter(Plant.id != plant_id).first()
            
            if existing_plant:
                return jsonify({'error': 'Position already occupied'}), 400
            
            plant.position_x = position_x
            plant.position_y = position_y
        
        db.session.commit()
        
        return jsonify({
            'message': 'Plant updated successfully',
            'plant': plant.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update plant: {str(e)}'}), 500

@api_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    try:
        user_id = get_jwt_identity()
        
        # Get user stats
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Calculate running stats
        runs = Run.query.filter_by(user_id=user_id).all()
        total_distance = sum(run.distance_km for run in runs)
        total_duration = sum(run.duration_minutes for run in runs)
        total_runs = len(runs)
        
        # Get wallet info
        wallet = CoinWallet.query.filter_by(user_id=user_id).first()
        
        # Get garden info
        garden = Garden.query.filter_by(user_id=user_id).first()
        
        # Plant statistics
        plants_by_stage = {}
        if garden:
            for stage in PlantStage:
                count = Plant.query.filter_by(garden_id=garden.id, stage=stage).count()
                plants_by_stage[stage.value] = count
        
        return jsonify({
            'user': user.to_dict(),
            'running_stats': {
                'total_runs': total_runs,
                'total_distance_km': round(total_distance, 2),
                'total_duration_minutes': total_duration,
                'average_distance_km': round(total_distance / total_runs, 2) if total_runs > 0 else 0,
                'average_pace_min_per_km': round(total_duration / total_distance, 2) if total_distance > 0 else 0
            },
            'wallet': wallet.to_dict() if wallet else None,
            'garden': {
                'level': garden.level if garden else 1,
                'experience_points': garden.experience_points if garden else 0,
                'total_plants': len(garden.plants) if garden else 0,
                'plants_by_stage': plants_by_stage
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get stats: {str(e)}'}), 500
