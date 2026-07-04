from langchain_core.tools import tool
from hermes.tools.registry import register_tool
import io
import base64

try:
    import pyautogui
    from PIL import ImageGrab
    pyautogui.FAILSAFE = False
except ImportError:
    pass

@register_tool
@tool("computer_control")
def computer_control(action: str, instruction: str = "") -> str:
    """
    Take physical control of the computer via screen capture, mouse, and keyboard.
    
    Actions: 
    - "screenshot": Takes a screenshot of the main monitor and returns it as a base64 URI.
                    The LLM can then analyze the image to find coordinates of UI elements.
    - "click": Clicks on coordinates. The 'instruction' MUST be exactly like "x=500 y=600".
    - "type": Types text using the keyboard. The 'instruction' is the text to type.
    """
    if action == "screenshot":
        try:
            screenshot = ImageGrab.grab()
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"Screenshot taken. IMAGE_PAYLOAD: data:image/png;base64,{img_str}"
        except Exception as e:
            return f"Failed to take screenshot: {e}"
            
    elif action == "click":
        try:
            # Parse instruction string like "x=100 y=200"
            parts = instruction.strip().split()
            x = int(parts[0].split("=")[1])
            y = int(parts[1].split("=")[1])
            
            # Add safety bounds or a brief pause
            pyautogui.PAUSE = 0.5
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.click()
            
            return f"Successfully clicked at ({x}, {y})"
        except Exception as e:
            return f"Failed to click. Make sure instruction is strictly formatted as 'x=100 y=200'. Error: {e}"
            
    elif action == "type":
        try:
            pyautogui.PAUSE = 0.1
            pyautogui.write(instruction, interval=0.02)
            return f"Successfully typed text."
        except Exception as e:
            return f"Failed to type: {e}"
            
    return f"Unknown action: {action}. Valid actions are 'screenshot', 'click', 'type'."
