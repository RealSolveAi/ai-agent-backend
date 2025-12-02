# app/services/agent_profile_service.py
from sqlalchemy.orm import Session
from app.persistance.db import SessionLocal
from app.models.agent_profile import AgentProfile
from datetime import datetime, timezone
from typing import Optional, Dict, Any


def create_agent_profile(data: dict) -> Dict[str, Any]:
    """
    Crea un nuevo perfil de agente para una empresa.
    """
    db = SessionLocal()
    try:
        agent_profile = AgentProfile(
            company_id=data["company_id"],
            name=data["name"],
            voice=data.get("voice", "coral"),
            temperature=data.get("temperature", 0.8),
            prompt=data.get("prompt"),
            working_hours=data.get("working_hours"),
            timezone=data.get("timezone"),
            is_active=data.get("is_active", True)
        )
        
        db.add(agent_profile)
        db.commit()
        db.refresh(agent_profile)
        
        return {
            "message": "Perfil de agente creado correctamente.",
            "agent_profile": {
                "id": agent_profile.id,
                "company_id": agent_profile.company_id,
                "name": agent_profile.name,
                "voice": agent_profile.voice,
                "temperature": agent_profile.temperature,
                "prompt": agent_profile.prompt,
                "working_hours": agent_profile.working_hours,
                "timezone": agent_profile.timezone,
                "is_active": agent_profile.is_active,
                "created_at": agent_profile.created_at.isoformat() if agent_profile.created_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al crear perfil de agente: {str(e)}"}
    finally:
        db.close()


def get_agent_profiles_by_company(company_id: int, is_active: Optional[bool] = None) -> Dict[str, Any]:
    """
    Obtiene todos los perfiles de agente de una empresa.
    """
    db = SessionLocal()
    try:
        query = db.query(AgentProfile).filter_by(company_id=company_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        
        agent_profiles = query.order_by(AgentProfile.created_at.desc()).all()
        
        return {
            "company_id": company_id,
            "agent_profiles": [
                {
                    "id": ap.id,
                    "name": ap.name,
                    "voice": ap.voice,
                    "temperature": ap.temperature,
                    "prompt": ap.prompt,
                    "working_hours": ap.working_hours,
                    "timezone": ap.timezone,
                    "is_active": ap.is_active,
                    "created_at": ap.created_at.isoformat() if ap.created_at else None,
                    "updated_at": ap.updated_at.isoformat() if ap.updated_at else None,
                }
                for ap in agent_profiles
            ],
            "count": len(agent_profiles)
        }
    except Exception as e:
        return {"error": f"Error al obtener perfiles de agente: {str(e)}"}
    finally:
        db.close()


def get_agent_profile_by_id(agent_profile_id: int) -> Dict[str, Any]:
    """
    Obtiene un perfil de agente por su ID.
    """
    db = SessionLocal()
    try:
        agent_profile = db.query(AgentProfile).filter_by(id=agent_profile_id).first()
        
        if not agent_profile:
            return {"error": "Perfil de agente no encontrado"}
        
        return {
            "id": agent_profile.id,
            "company_id": agent_profile.company_id,
            "name": agent_profile.name,
            "voice": agent_profile.voice,
            "temperature": agent_profile.temperature,
            "prompt": agent_profile.prompt,
            "working_hours": agent_profile.working_hours,
            "timezone": agent_profile.timezone,
            "is_active": agent_profile.is_active,
            "created_at": agent_profile.created_at.isoformat() if agent_profile.created_at else None,
            "updated_at": agent_profile.updated_at.isoformat() if agent_profile.updated_at else None,
        }
    except Exception as e:
        return {"error": f"Error al obtener perfil de agente: {str(e)}"}
    finally:
        db.close()


def update_agent_profile(agent_profile_id: int, data: dict) -> Dict[str, Any]:
    """
    Actualiza un perfil de agente.
    """
    db = SessionLocal()
    try:
        agent_profile = db.query(AgentProfile).filter_by(id=agent_profile_id).first()
        
        if not agent_profile:
            return {"error": "Perfil de agente no encontrado"}
        
        # Actualizar campos permitidos
        if "name" in data:
            agent_profile.name = data["name"]
        if "voice" in data:
            agent_profile.voice = data["voice"]
        if "temperature" in data:
            agent_profile.temperature = data["temperature"]
        if "prompt" in data:
            agent_profile.prompt = data["prompt"]
        if "working_hours" in data:
            agent_profile.working_hours = data["working_hours"]
        if "timezone" in data:
            agent_profile.timezone = data["timezone"]
        if "is_active" in data:
            agent_profile.is_active = data["is_active"]
        
        agent_profile.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(agent_profile)
        
        return {
            "message": "Perfil de agente actualizado correctamente.",
            "agent_profile": {
                "id": agent_profile.id,
                "company_id": agent_profile.company_id,
                "name": agent_profile.name,
                "voice": agent_profile.voice,
                "temperature": agent_profile.temperature,
                "prompt": agent_profile.prompt,
                "working_hours": agent_profile.working_hours,
                "timezone": agent_profile.timezone,
                "is_active": agent_profile.is_active,
                "updated_at": agent_profile.updated_at.isoformat() if agent_profile.updated_at else None,
            }
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Error al actualizar perfil de agente: {str(e)}"}
    finally:
        db.close()


def delete_agent_profile(agent_profile_id: int) -> Dict[str, Any]:
    """
    Elimina un perfil de agente.
    """
    db = SessionLocal()
    try:
        agent_profile = db.query(AgentProfile).filter_by(id=agent_profile_id).first()
        
        if not agent_profile:
            return {"error": "Perfil de agente no encontrado"}
        
        db.delete(agent_profile)
        db.commit()
        
        return {"message": "Perfil de agente eliminado correctamente."}
    except Exception as e:
        db.rollback()
        return {"error": f"Error al eliminar perfil de agente: {str(e)}"}
    finally:
        db.close()

