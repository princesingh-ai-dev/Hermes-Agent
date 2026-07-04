import os
import asyncio
import tempfile
import threading
import pygame
import edge_tts
import speech_recognition as sr
from faster_whisper import WhisperModel
from hermes.platforms.gateway import PlatformGateway

class VoiceAssistant:
    def __init__(self, gateway: PlatformGateway, wake_word="hermes", voice="en-US-ChristopherNeural"):
        self.gateway = gateway
        self.wake_word = wake_word.lower()
        self.voice = voice
        
        print("[Voice] Loading local Whisper Model for STT... (This is fast!)")
        # We use a small local model for fast transcription
        self.stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        
        self.recognizer = sr.Recognizer()
        pygame.mixer.init()
        
    async def speak(self, text: str):
        """Generates TTS using Edge-TTS and plays it via Pygame."""
        try:
            print(f"[Jarvis] Speaking: {text}")
            # Create a temporary file for the MP3
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.close()
            
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(temp_file.name)
            
            # Play the audio
            pygame.mixer.music.load(temp_file.name)
            pygame.mixer.music.play()
            
            # Wait until it finishes playing
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
                
            # Cleanup
            pygame.mixer.music.unload()
            os.unlink(temp_file.name)
        except Exception as e:
            print(f"[Voice] Error during speech synthesis: {e}")

    def listen(self):
        """Listens to the microphone continuously and yields transcribed text."""
        with sr.Microphone() as source:
            print("[Voice] Adjusting for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("[Voice] Listening... (Say something!)")
            
            while True:
                try:
                    # Listen for audio phrase
                    audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
                    
                    # We save the wav data to a temp file for whisper to read
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
                        temp_wav.write(audio.get_wav_data())
                        temp_wav.flush()
                        
                        # Transcribe with local faster-whisper
                        segments, info = self.stt_model.transcribe(temp_wav.name, beam_size=1)
                        text = " ".join([segment.text for segment in segments]).strip()
                        
                    os.unlink(temp_wav.name)
                    
                    if text:
                        yield text
                        
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    print(f"[Voice] Listen error: {e}")
                    
    async def process_voice_loop(self):
        """Main loop that bridges STT -> Agent -> TTS."""
        print("[Voice] System Online. Awaiting input...")
        
        # We run the synchronous listen generator in a separate thread 
        # so it doesn't block our asyncio event loop
        loop = asyncio.get_event_loop()
        
        for text in self.listen():
            print(f"\n[You] {text}")
            text_lower = text.lower()
            
            # Optional: Enforce wake word
            # if self.wake_word not in text_lower:
            #     continue
            
            print("[Voice] Processing with AI...")
            try:
                # Route through the central gateway
                # user_id is hardcoded to "voice_user" for local interface
                response = await self.gateway.handle_message("voice", "voice_user", text)
                
                # Speak the response
                await self.speak(response)
                print("[Voice] Ready for next command.")
                
            except Exception as e:
                print(f"[Voice] Agent error: {e}")
                await self.speak("I'm sorry, I encountered an error processing that.")

# Optional: direct execution
if __name__ == "__main__":
    from hermes.api.main import stream_hermes_response
    import hermes.api.main as api_main

    async def dummy_voice_agent(platform, user_id, message):
        from hermes.graph.graph import hermes_graph
        result = await hermes_graph.ainvoke(
            {"messages": [{"role": "user", "content": message}], "task_type": "chat"},
            config={"configurable": {"thread_id": "voice_session"}}
        )
        return result["messages"][-1].content

    gateway = PlatformGateway(dummy_voice_agent)
    assistant = VoiceAssistant(gateway)
    
    try:
        asyncio.run(assistant.process_voice_loop())
    except KeyboardInterrupt:
        print("\n[Voice] Shutting down...")
