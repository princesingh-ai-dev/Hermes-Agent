# hermes/tools/smart_home.py
import requests
from langchain_core.tools import tool
from hermes.tools.registry import register_tool
import hermes.core.config as config
import os

HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "http://homeassistant.local:8123")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")

@register_tool
@tool
def smart_home_get_state(entity_id: str) -> dict:
    """Option C: Smart Home. Gets the current state of a smart home device (e.g. 'light.living_room' or 'media_player.android_tv')."""
    if not HOME_ASSISTANT_TOKEN:
        return {"error": "HOME_ASSISTANT_TOKEN not configured in .env"}
        
    headers = {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        url = f"{HOME_ASSISTANT_URL}/api/states/{entity_id}"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@register_tool
@tool
def smart_home_control(entity_id: str, service: str, domain: str = "homeassistant") -> dict:
    """Option C: Smart Home. Controls a smart device (e.g. domain='light', service='turn_on', entity_id='light.living_room')."""
    if not HOME_ASSISTANT_TOKEN:
        return {"error": "HOME_ASSISTANT_TOKEN not configured in .env"}
        
    headers = {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"entity_id": entity_id}
    
    try:
        url = f"{HOME_ASSISTANT_URL}/api/services/{domain}/{service}"
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        return {"status": "success", "response": response.json()}
    except Exception as e:
        return {"error": str(e)}
