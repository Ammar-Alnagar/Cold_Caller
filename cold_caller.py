import asyncio
import base64
import json
import os
import pathlib
import datetime
from typing import AsyncGenerator, Literal, Optional, List, Dict, Any

import gradio as gr
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastrtc import (
    AsyncStreamHandler,
    Stream,
    wait_for_item,
)
from google import genai
from google.genai.types import (
    LiveConnectConfig,
    PrebuiltVoiceConfig,
    SpeechConfig,
    VoiceConfig,
    Content,
    Part,
)
from gradio.utils import get_space
from pydantic import BaseModel

current_dir = pathlib.Path(__file__).parent

load_dotenv()


def encode_audio(data: np.ndarray) -> str:
    """Encode Audio data to send to the server"""
    return base64.b64encode(data.tobytes()).decode("UTF-8")


# Simple ICE server configuration with free STUN servers
def get_free_ice_servers():
    return {
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"},
            {"urls": "stun:stun2.l.google.com:19302"},
            {"urls": "stun:stun3.l.google.com:19302"},
            {"urls": "stun:stun4.l.google.com:19302"},
        ]
    }


# Default system prompt for the assistant
DEFAULT_SYSTEM_PROMPT = """
You are Maxwell , a high-performing, proactive sales representative AI for Critical Future LTD, a leading global consultancy specializing in AI strategy, digital transformation, market intelligence, and strategic foresight.
You initiate conversations, uncover client needs, and lead prospects toward meaningful engagements with Critical Future's consulting services.

🎯 Your Goals:
Start by introducing yourself and your goal.
Initiate conversations confidently with potential clients—you do not wait to be prompted.

Lead the dialogue: Uncover business pain points, challenges, and goals through intelligent, open-ended questions.

Position Critical Future as the ideal partner to help businesses adapt, transform, and grow using AI-driven strategy and data-backed insights.

Tailor your messaging to the client's role, industry, and business context.

Drive the conversation toward actionable next steps: booking consultations, scheduling a discovery call, or sharing relevant documents/case studies.

💼 Company Background (Use to Inform Your Sales Pitch):
Critical Future is a global strategy consulting firm that leverages artificial intelligence and deep market research to help businesses future-proof themselves. Our services include:

AI Strategy Consulting: Crafting data-informed AI roadmaps aligned with business goals.

Digital Transformation: Guiding companies through end-to-end digital evolution.

Market Intelligence: Offering powerful insights into emerging trends, competitors, and global shifts.

Strategic Foresight: Using predictive analysis to help clients plan for future disruption and opportunity.

Critical Future serves enterprises, C-suites, and innovation leaders seeking to thrive in fast-moving markets.

🧠 Your Personality:
Proactive: You always take initiative. You're not reactive or passive.

Strategic: You think like a consultant, not a pushy salesperson.

Empathetic: You listen actively and respond to real pain points.

Confident but not arrogant: You inspire trust and curiosity.

🗣️ Conversation Structure:
1. Icebreaker & Contextual Opener

Open with a relevant, intelligent question or insight based on the client's industry, role, or sector trends.

Example: "Hi there! With AI rapidly reshaping the [industry name] space, have you started exploring how it could impact your strategy over the next 12 months?"

2. Discovery Phase

Ask smart, targeted questions to uncover:

Their current challenges

Innovation or growth goals

Existing AI/digital transformation efforts

3. Solution Mapping

Connect their needs to Critical Future services.

Explain how our AI strategy, market intelligence, or transformation consulting solves their problems.

4. Credibility Building

Mention global presence, trusted by executives, backed by research, known for cutting-edge foresight and practical outcomes.

5. Call to Action (CTA)

Always guide the next step:

"Would you be open to a short discovery call with our consulting team?"

"I can send over a tailored proposal or some of our recent success stories—would that be helpful?"

🛑 What to Avoid:
Don't wait for the user to ask you for help.

Don't use vague or generic phrases.

Don't oversell—be consultative, not aggressive.

Don't pitch without understanding the client's context.

🧩 Prompt Examples for You to Use During Conversations:
"Can I ask—how are you currently approaching innovation or digital strategy in your organization?"

"Where do you see AI fitting into your competitive strategy over the next 6 to 18 months?"

"If I could show you a way to increase operational intelligence using real market foresight, would you be open to exploring it?"

"""
class ConversationLogger:
    """Logs conversations between the user and the assistant"""

    def __init__(self, log_dir: str = "conversation_logs"):
        self.log_dir = pathlib.Path(log_dir)
        try:
            # Create the log directory if it doesn't exist
            self.log_dir.mkdir(exist_ok=True, parents=True)

            # Check if the directory is writable
            test_file_path = self.log_dir / ".test_write"
            with open(test_file_path, "w") as f:
                f.write("test")
            test_file_path.unlink()  # Delete the test file

            print(f"Conversation log directory ready: {self.log_dir.absolute()}")
        except Exception as e:
            print(f"ERROR setting up conversation log directory: {e}")
            import traceback
            traceback.print_exc()
            # Try to use a fallback directory in the current working directory
            fallback_dir = pathlib.Path("./logs")
            try:
                fallback_dir.mkdir(exist_ok=True)
                self.log_dir = fallback_dir
                print(f"Using fallback log directory: {fallback_dir.absolute()}")
            except:
                print("CRITICAL ERROR: Cannot create any log directory!")

        self.current_log_file = None
        self.conversation_id = None
        self.message_count = 0
        self.user_message_count = 0
        self.assistant_message_count = 0

    def start_new_conversation(self) -> str:
        """Start a new conversation with a unique ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_id = f"conversation_{timestamp}"
        self.current_log_file = self.log_dir / f"{self.conversation_id}.txt"
        self.message_count = 0
        self.user_message_count = 0
        self.assistant_message_count = 0

        # Initialize the log file with a header
        with open(self.current_log_file, "w") as f:
            f.write(f"Conversation ID: {self.conversation_id}\n")
            f.write(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            # Add more metadata about the conversation
            f.write(f"Log Directory: {self.log_dir.absolute()}\n")
            f.write("-" * 60 + "\n\n")

            # Create a JSON version of the log file for easier parsing
            json_log_file = self.log_dir / f"{self.conversation_id}.json"
            with open(json_log_file, "w") as jf:
                json.dump({
                    "conversation_id": self.conversation_id,
                    "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "messages": []
                }, jf, indent=2)

        print(f"Started new conversation: {self.conversation_id}")
        print(f"Logging to: {self.current_log_file}")
        return self.conversation_id
        def start_new_conversation(self) -> str:
            """Start a new conversation with a unique ID"""
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.conversation_id = f"conversation_{timestamp}"
            self.current_log_file = self.log_dir / f"{self.conversation_id}.txt"

            # Create additional files for raw transcripts and debug logs
            self.raw_transcript_file = self.log_dir / f"{self.conversation_id}_raw.txt"
            self.debug_log_file = self.log_dir / f"{self.conversation_id}_debug.log"

            self.message_count = 0
            self.user_message_count = 0
            self.assistant_message_count = 0

            # Initialize the log file with a header
            with open(self.current_log_file, "w") as f:
                f.write(f"Conversation ID: {self.conversation_id}\n")
                f.write(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

                # Add more metadata about the conversation
                f.write(f"Log Directory: {self.log_dir.absolute()}\n")
                f.write(f"Raw Transcript: {self.raw_transcript_file.name}\n")
                f.write(f"Debug Log: {self.debug_log_file.name}\n")
                f.write("-" * 60 + "\n\n")

            # Initialize raw transcript file
            with open(self.raw_transcript_file, "w") as f:
                f.write(f"RAW TRANSCRIPT - Conversation ID: {self.conversation_id}\n")
                f.write(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("This file contains all raw transcripts including partial ones.\n")
                f.write("-" * 60 + "\n\n")

            # Initialize debug log file
            with open(self.debug_log_file, "w") as f:
                f.write(f"DEBUG LOG - Conversation ID: {self.conversation_id}\n")
                f.write(f"Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 60 + "\n\n")

            # Create a JSON version of the log file for easier parsing
            json_log_file = self.log_dir / f"{self.conversation_id}.json"
            with open(json_log_file, "w") as jf:
                json.dump({
                    "conversation_id": self.conversation_id,
                    "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "raw_transcript_file": self.raw_transcript_file.name,
                    "debug_log_file": self.debug_log_file.name,
                    "messages": []
                }, jf, indent=2)

            print(f"Started new conversation: {self.conversation_id}")
            print(f"Logging to: {self.current_log_file}")
            print(f"Raw transcript: {self.raw_transcript_file}")
            print(f"Debug log: {self.debug_log_file}")
            return self.conversation_id

        def log_to_raw_transcript(self, speaker: str, message: str, is_partial: bool = False) -> None:
            """Log a message to the raw transcript file"""
            if not hasattr(self, 'raw_transcript_file') or not self.raw_transcript_file:
                return

            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                with open(self.raw_transcript_file, "a") as f:
                    f.write(f"[{timestamp}] {speaker} {'(PARTIAL)' if is_partial else ''}: {message}\n\n")
            except Exception as e:
                print(f"Error writing to raw transcript: {e}")

        def log_debug(self, message: str) -> None:
            """Log a debug message to the debug log file"""
            if not hasattr(self, 'debug_log_file') or not self.debug_log_file:
                return

            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                with open(self.debug_log_file, "a") as f:
                    f.write(f"[{timestamp}] {message}\n")
            except Exception as e:
                print(f"Error writing to debug log: {e}")

    def log_message(self, speaker: str, message: str, timestamp=None, is_partial=False) -> None:
        """Log a message from either the user or the assistant"""
        if not message or not isinstance(message, str):
            print(f"Warning: Attempting to log invalid message from {speaker}: {type(message)}")
            if not isinstance(message, str):
                # Try to convert to string
                try:
                    message = str(message)
                except:
                    message = "<Non-string message>"

        if not self.current_log_file:
            self.start_new_conversation()

        # Only increment counters for non-partial messages
        if not is_partial and not speaker.lower().find("partial") >= 0:
            self.message_count += 1
            if speaker.lower().startswith("user"):
                self.user_message_count += 1
            elif speaker.lower().startswith("assistant"):
                self.assistant_message_count += 1

        if timestamp is None:
            timestamp = datetime.datetime.now()

        if isinstance(timestamp, datetime.datetime):
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds
        else:
            timestamp_str = str(timestamp)

        # Write to text log file
        try:
            with open(self.current_log_file, "a") as f:
                # Add metadata about message type
                message_type = "PARTIAL" if is_partial or "partial" in speaker.lower() else "COMPLETE"
                f.write(f"[{timestamp_str}] {speaker} [{message_type}]: {message}\n\n")
            print(f"Message logged successfully to text file from {speaker} ({len(message)} chars)")
        except Exception as e:
            print(f"ERROR writing to log file: {e}")

        # Update JSON log file
        try:
            json_log_file = self.log_dir / f"{self.conversation_id}.json"
            data = {}
            if json_log_file.exists():
                with open(json_log_file, "r") as jf:
                    data = json.load(jf)

            if "messages" not in data:
                data["messages"] = []

            # Create message entry with more metadata
            message_entry = {
                "timestamp": timestamp_str,
                "speaker": speaker,
                "message": message,
                "message_number": self.message_count if not is_partial else f"partial-{datetime.datetime.now().timestamp()}",
                "is_partial": is_partial or "partial" in speaker.lower(),
                "length": len(message)
            }

            data["messages"].append(message_entry)

            # Update conversation statistics
            data["message_count"] = self.message_count
            data["user_message_count"] = self.user_message_count
            data["assistant_message_count"] = self.assistant_message_count
            data["last_updated"] = timestamp_str
            data["total_text_logged"] = sum(len(m.get("message", "")) for m in data["messages"])

            with open(json_log_file, "w") as jf:
                json.dump(data, jf, indent=2)
            print(f"Message logged successfully to JSON file from {speaker}")
        except Exception as e:
            print(f"ERROR updating JSON log: {e}")
            import traceback
            traceback.print_exc()

    def log_system_message(self, message: str) -> None:
        """Log a system message or event"""
        self.log_message("System", message)

    def end_conversation(self) -> None:
        """Mark the end of a conversation"""
        if not self.current_log_file or not self.current_log_file.exists():
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration = "Unknown"

        try:
            # Read the start time from the file
            with open(self.current_log_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("Started:"):
                        start_time_str = line.replace("Started:", "").strip()
                        start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                        end_time = datetime.datetime.now()
                        duration = str(end_time - start_time)
                        break
        except Exception as e:
            print(f"Error calculating conversation duration: {e}")

        # Write to text log file
        with open(self.current_log_file, "a") as f:
            f.write("\n" + "-" * 60 + "\n")
            f.write(f"Conversation ended: {timestamp}\n")
            f.write(f"Duration: {duration}\n")
            f.write(f"Total messages: {self.message_count}\n")
            f.write(f"User messages: {self.user_message_count}\n")
            f.write(f"Assistant messages: {self.assistant_message_count}\n")

        # Update JSON log file
        try:
            json_log_file = self.log_dir / f"{self.conversation_id}.json"
            if json_log_file.exists():
                with open(json_log_file, "r") as jf:
                    data = json.load(jf)

                data["ended"] = timestamp
                data["duration"] = duration
                data["message_count"] = self.message_count
                data["user_message_count"] = self.user_message_count
                data["assistant_message_count"] = self.assistant_message_count

                with open(json_log_file, "w") as jf:
                    json.dump(data, jf, indent=2)
        except Exception as e:
            print(f"Error updating JSON log end: {e}")

        print(f"Ended conversation: {self.conversation_id}")
        print(f"Duration: {duration}, Total messages: {self.message_count}")

    def log_system_prompt(self, system_prompt: str) -> None:
        """Log the system prompt used for this conversation"""
        if not self.current_log_file:
            self.start_new_conversation()

        # Add to the text log file
        with open(self.current_log_file, "a") as f:
            f.write("SYSTEM PROMPT:\n")
            f.write("-" * 60 + "\n")
            f.write(system_prompt + "\n")
            f.write("-" * 60 + "\n\n")

        # Update the JSON log
        try:
            json_log_file = self.log_dir / f"{self.conversation_id}.json"
            if json_log_file.exists():
                with open(json_log_file, "r") as jf:
                    data = json.load(jf)

                # Add the system prompt
                data["system_prompt"] = system_prompt

                with open(json_log_file, "w") as jf:
                    json.dump(data, jf, indent=2)
        except Exception as e:
            print(f"Error updating JSON with system prompt: {e}")

        print(f"Logged system prompt for conversation: {self.conversation_id}")


class GeminiHandler(AsyncStreamHandler):
    """Handler for the Gemini API"""

    def __init__(
        self,
        expected_layout: Literal["mono"] = "mono",
        output_sample_rate: int = 24000,
        output_frame_size: int = 480,
        system_prompt: Optional[str] = None,
        debug_logging: bool = True,
        log_partial_responses: bool = True,
    ) -> None:
        super().__init__(
            expected_layout,
            output_sample_rate,
            output_frame_size,
            input_sample_rate=16000,
        )
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.output_queue: asyncio.Queue = asyncio.Queue()
        self.quit: asyncio.Event = asyncio.Event()
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.logger = ConversationLogger()
        self.conversation_history: List[Dict[str, Any]] = []
        # Initialize with system prompt
        self.conversation_history.append({"role": "system", "parts": [self.system_prompt]})
        self.current_user_message = ""
        self.current_model_response = ""
        self.session = None
        self.transcription_complete = False

        # Debug and logging options
        self.debug_logging = debug_logging
        self.log_partial_responses = log_partial_responses
        self.last_partial_log_time = datetime.datetime.now()
        self.partial_log_interval = datetime.timedelta(seconds=1)  # Log partials at most once per second

    def copy(self) -> "GeminiHandler":
        return GeminiHandler(
            expected_layout="mono",
            output_sample_rate=self.output_sample_rate,
            output_frame_size=self.output_frame_size,
            system_prompt=self.system_prompt,
        )

    async def start_up(self):
        if not self.phone_mode:
            await self.wait_for_args()
            # Handle different argument lengths for backward compatibility
            if len(self.latest_args) >= 3:
                api_key, voice_name, system_prompt = self.latest_args[1:]
                self.system_prompt = system_prompt
            else:
                api_key, voice_name = self.latest_args[1:] if len(self.latest_args) >= 2 else (None, "Puck")
        else:
            api_key, voice_name = None, "Puck"

        # Start a new conversation log
        self.logger.start_new_conversation()
        self.logger.log_system_prompt(self.system_prompt)
        print(f"Starting new conversation: {self.logger.conversation_id}")
        print(f"Using system prompt: {self.system_prompt[:100]}...")
        print(f"Conversation logs will be saved to: {self.logger.current_log_file}")

        client = genai.Client(
            api_key=api_key or os.getenv("GEMINI_API_KEY"),
            http_options={"api_version": "v1alpha"},
        )

        # Wrap the system prompt in a Content object so that validation passes
        content_system_instruction = Content(parts=[Part.from_text(text=self.system_prompt)])

        config = LiveConnectConfig(
            response_modalities=["AUDIO"],  # type: ignore
            speech_config=SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                )
            ),
            system_instruction=content_system_instruction
        )

        try:
            # Use the async context manager correctly
            async with client.aio.live.connect(
                model="gemini-2.0-flash-exp",
                config=config
            ) as session:
                self.session = session
                print("Connected to Gemini Live API successfully")
                print("Waiting for user speech or sending initial response...")

                # Debugging flags
                print_fields = True
                debug_count = 0  # Limit the number of debug messages

                async for response in session.start_stream(
                    stream=self.stream(),
                    mime_type="audio/pcm"
                ):
                    # Debug the response object if needed
                    debug_count += 1
                    if print_fields and debug_count <= 3:
                        debug_response(response, print_all_fields=(debug_count == 1))

                    # Process audio data
                    if hasattr(response, 'data') and response.data:
                        array = np.frombuffer(response.data, dtype=np.int16)
                        self.output_queue.put_nowait((self.output_sample_rate, array))

        # Process user speech (if available)
                    if hasattr(response, 'recognized_speech') and response.recognized_speech:
                        # Handle recognized speech
                        recognized = response.recognized_speech
                        is_final = getattr(response, 'is_final', False)
                        print(f"User speech recognized: '{recognized}' (Final: {is_final})")

                        # Update our tracked user message
                        if not self.current_user_message:
                            self.current_user_message = recognized
                        else:
                            # Append to existing transcription
                            self.current_user_message += " " + recognized

                        # Log partial transcriptions with 'partial' flag for debugging
                        if not is_final and self.current_user_message and len(self.current_user_message) > 10:
                            print(f"Logging partial user speech: '{self.current_user_message}'")
                            self.logger.log_message("User (partial)", self.current_user_message,
                                                   timestamp=datetime.datetime.now())

                        # If this is the final transcription for this utterance, log it
                        if is_final and self.current_user_message:
                            print(f"Logging final user speech: '{self.current_user_message}'")
                            self.logger.log_message("User", self.current_user_message)
                            print(f"Successfully logged user message ({len(self.current_user_message)} chars)")

                            # Add to conversation history
                            self.conversation_history.append({"role": "user", "parts": [self.current_user_message]})

                            # Reset for next utterance
                            self.current_user_message = ""

                    # Process model text responses (combine all approaches)
                    if hasattr(response, 'text') and response.text:
                        # Accumulate the model's response
                        if not self.current_model_response:
                            print("Model starting to respond...")

                        # Track previous length for logging partial responses
                        prev_length = len(self.current_model_response)

                        # Add new text
                        self.current_model_response += response.text

                        # Log partial responses periodically for better tracking
                        current_length = len(self.current_model_response)
                        if current_length > prev_length + 50:  # Log after significant additions
                            print(f"Model partial response: {self.current_model_response[-100:]}...")
                            self.logger.log_message("Assistant (partial)",
                                                  f"[Partial response, {current_length} chars so far]:\n{self.current_model_response}",
                                                  timestamp=datetime.datetime.now())

                        # Check if this is the final chunk of the response
                        if getattr(response, 'is_final', False) and self.current_model_response:
                            print(f"Model response complete: {self.current_model_response[:100]}...")
                            self.logger.log_message("Assistant", self.current_model_response)
                            print(f"Logged assistant message ({len(self.current_model_response)} chars)")
                            self.conversation_history.append({"role": "model", "parts": [self.current_model_response]})
                            self.current_model_response = ""

                    # Check for server content format (newer API versions)
                    if hasattr(response, 'server_content') and response.server_content:
                        # Process server content for model responses
                        server_content = response.server_content

                        # Check for model turn data
                        if hasattr(server_content, 'model_turn') and server_content.model_turn:
                            model_turn = server_content.model_turn

                            # Track previous length for logging partial responses
                            prev_length = len(self.current_model_response)

                            # Extract text from parts if available
                            if hasattr(model_turn, 'parts') and model_turn.parts:
                                for part in model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        if not self.current_model_response:
                                            print("Model starting to respond (server_content)...")
                                        self.current_model_response += part.text

                            # Log significant additions to the response
                            current_length = len(self.current_model_response)
                            if current_length > prev_length + 50:
                                print(f"Model partial response (server_content): {self.current_model_response[-100:]}...")
                                self.logger.log_message("Assistant (server_content partial)",
                                                      f"[Partial response, {current_length} chars so far]:\n{self.current_model_response}",
                                                      timestamp=datetime.datetime.now())

                        # Check if this is the end of the model's turn
                        if hasattr(server_content, 'turn_complete') and server_content.turn_complete and self.current_model_response:
                            print(f"Model response complete (server_content): {self.current_model_response[:100]}...")
                            self.logger.log_message("Assistant", self.current_model_response)
                            print(f"Logged assistant message ({len(self.current_model_response)} chars)")
                            self.conversation_history.append({"role": "model", "parts": [self.current_model_response]})
                            self.current_model_response = ""

                        # Check for audio/speech transcriptions
                        if hasattr(server_content, 'input_transcription') and server_content.input_transcription:
                            transcription = server_content.input_transcription
                            if hasattr(transcription, 'text') and transcription.text:
                                recognized = transcription.text
                                print(f"User speech recognized (server_content): '{recognized}'")

                                # Update our tracked user message
                                if not self.current_user_message:
                                    self.current_user_message = recognized
                                else:
                                    self.current_user_message += " " + recognized

                        # Check if this is the end of user's utterance
                        if hasattr(server_content, 'activity_end') and server_content.activity_end and self.current_user_message:
                            print(f"Logging final user speech (server_content): '{self.current_user_message}'")
                            self.logger.log_message("User", self.current_user_message)
                            print(f"Successfully logged user message ({len(self.current_user_message)} chars)")
                            self.conversation_history.append({"role": "user", "parts": [self.current_user_message]})
                            self.current_user_message = ""

                    # Process JSON format responses (fall back for compatibility)
                    if isinstance(response, dict):
                        # Handle server content in JSON form
                        if "serverContent" in response:
                            server_content = response["serverContent"]

                            # Get model turn text
                            if "modelTurn" in server_content and "parts" in server_content["modelTurn"]:
                                for part in server_content["modelTurn"]["parts"]:
                                    if "text" in part:
                                        if not self.current_model_response:
                                            print("Model starting to respond (JSON)...")
                                        self.current_model_response += part["text"]

                            # Check for end of turn
                            if server_content.get("turnComplete", False) and self.current_model_response:
                                print(f"Model response complete (JSON): {self.current_model_response[:100]}...")
                                self.logger.log_message("Assistant", self.current_model_response)
                                print(f"Logged assistant message ({len(self.current_model_response)} chars)")
                                self.conversation_history.append({"role": "model", "parts": [self.current_model_response]})
                                self.current_model_response = ""

                            # Get transcribed speech
                            if "inputTranscription" in server_content and "text" in server_content["inputTranscription"]:
                                recognized = server_content["inputTranscription"]["text"]
                                print(f"User speech recognized (JSON): '{recognized}'")

                                if not self.current_user_message:
                                    self.current_user_message = recognized
                                else:
                                    self.current_user_message += " " + recognized

                            # Check for end of user's speech
                            if server_content.get("activityEnd", False) and self.current_user_message:
                                print(f"Logging final user speech (JSON): '{self.current_user_message}'")
                                self.logger.log_message("User", self.current_user_message)
                                print(f"Successfully logged user message ({len(self.current_user_message)} chars)")
                                self.conversation_history.append({"role": "user", "parts": [self.current_user_message]})
                                self.current_user_message = ""
        except Exception as e:
            print(f"Error in GeminiHandler.start_up: {e}")
            import traceback
            traceback.print_exc()
            self.logger.log_message("System", f"Error: {str(e)}")

    async def stream(self) -> AsyncGenerator[bytes, None]:
        while not self.quit.is_set():
            try:
                audio = await asyncio.wait_for(self.input_queue.get(), 0.1)
                yield audio
            except (asyncio.TimeoutError, TimeoutError):
                pass

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        _, array = frame
        array = array.squeeze()
        audio_message = encode_audio(array)
        self.input_queue.put_nowait(audio_message)

    async def emit(self) -> tuple[int, np.ndarray] | None:
        return await wait_for_item(self.output_queue)

    def shutdown(self) -> None:
        """Shut down the handler and clean up resources."""
        self.quit.set()

        # Log end of conversation
        if self.logger and self.logger.current_log_file:
            try:
                # Also log any partial messages that weren't finalized
                if self.current_user_message:
                    self.logger.log_message("User (partial)", self.current_user_message)
                if self.current_model_response:
                    self.logger.log_message("Assistant (partial)", self.current_model_response)

                # End the conversation properly
                self.logger.end_conversation()

            except Exception as e:
                print(f"Error closing conversation log: {e}")
                import traceback
                traceback.print_exc()

        # The session is now managed by the context manager in start_up
        # No need to explicitly close it here
        def log_partial_response(self, role: str, message: str) -> None:
            """Log partial responses with rate limiting to avoid excessive logging"""
            if not self.log_partial_responses:
                return

            now = datetime.datetime.now()
            # Only log if enough time has passed since the last partial log
            if now - self.last_partial_log_time >= self.partial_log_interval:
                self.logger.log_message(f"{role} (partial)", message, timestamp=now, is_partial=True)
                self.last_partial_log_time = now
                print(f"Logged partial {role.lower()} response: {message[:50]}... ({len(message)} chars)")

        def log_final_response(self, role: str, message: str) -> None:
            """Log final (complete) responses"""
            self.logger.log_message(role, message)
            print(f"Logged final {role.lower()} response: {message[:50]}... ({len(message)} chars)")

            # Add a debug log with more details
            if self.debug_logging:
                debug_info = f"FINAL {role.upper()} RESPONSE STATS:\n"
                debug_info += f"- Length: {len(message)} characters\n"
                debug_info += f"- Word count: ~{len(message.split())} words\n"
                debug_info += f"- Timestamp: {datetime.datetime.now().isoformat()}\n"

                self.logger.log_system_message(debug_info)


# Extending the Stream class with a get_handler method
def get_handler_by_id(self, webrtc_id):
    """Get the handler instance associated with a specific webrtc_id"""
    if hasattr(self, "_streams") and webrtc_id in self._streams:
        return self._streams[webrtc_id].handler
    return None

# Add the method to the Stream class
Stream.get_handler = get_handler_by_id

# Configure the stream with free ICE servers instead of Twilio
stream = Stream(
    modality="audio",
    mode="send-receive",
    handler=GeminiHandler(),
    rtc_configuration=get_free_ice_servers(),  # Using free STUN servers instead of Twilio
    concurrency_limit=5 if get_space() else None,
    time_limit=90 if get_space() else None,
    additional_inputs=[
        gr.Textbox(
            label="API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY") if not get_space() else "",
        ),
        gr.Dropdown(
            label="Voice",
            choices=[
                "Puck",
                "Charon",
                "Kore",
                "Fenrir",
                "Aoede",
            ],
            value="Puck",
        ),
        gr.Textbox(
            label="System Prompt",
            placeholder="Enter system prompt here",
            value=DEFAULT_SYSTEM_PROMPT,
            lines=3,
            visible=False,
            interactive=False,
        ),
    ],
)


class InputData(BaseModel):
    webrtc_id: str
    voice_name: str
    api_key: str
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


app = FastAPI()

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a static directory for favicon and other assets if it doesn't exist
static_dir = current_dir / "static"
static_dir.mkdir(exist_ok=True)

# Create a simple favicon file
favicon_path = static_dir / "favicon.ico"
if not favicon_path.exists():
    # Write a minimal 1x1 pixel ICO file
    with open(favicon_path, "wb") as f:
        f.write(b"\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x0C\x00\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")

# Mount the static files directory
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

stream.mount(app)


@app.post("/input_hook")
async def _(body: InputData):
    try:
        print(f"Received system prompt for {body.webrtc_id}")
        if body.system_prompt:
            print(f"System prompt length: {len(body.system_prompt)} chars")
            print(f"First 100 chars: {body.system_prompt[:100]}")

        # Set all inputs including system prompt
        stream.set_input(body.webrtc_id, body.api_key, body.voice_name, body.system_prompt)
        print(f"Input set successfully for {body.webrtc_id}")

        return {"status": "ok"}
    except Exception as e:
        print(f"Error in input_hook: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.get("/favicon.ico")
async def favicon():
    # Redirect to the static favicon
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/static/favicon.ico">')

@app.get("/")
async def index():
    # Use free ICE servers instead of Twilio
    rtc_config = get_free_ice_servers()

    # Get the default system prompt for the form
    system_prompt_for_form = DEFAULT_SYSTEM_PROMPT.strip()

    # If index.html doesn't exist, create a minimal version
    index_path = current_dir / "index.html"
    if not index_path.exists():
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>WebRTC Audio Chat</title>
            <link rel="icon" href="/static/favicson.ico">
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                button { padding: 10px 20px; margin: 10px 0; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { margin: 10px 0; padding: 10px; border-radius: 5px; }
                .connected { background-color: #dff0d8; color: #3c763d; }
                .disconnected { background-color: #f2dede; color: #a94442; }
                .connecting { background-color: #fcf8e3; color: #8a6d3b; }
                textarea { width: 100%; height: 200px; margin: 10px 0; font-family: monospace; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>WebRTC Audio Chat</h1>
                <div id="status" class="status disconnected">Status: Disconnected</div>
                <div>
                    <label for="api-key">Gemini API Key:</label>
                    <input type="password" id="api-key" placeholder="Enter your API key">
                </div>
                <div>
                    <label for="voice-select">Voice:</label>
                    <select id="voice-select">
                        <option value="Puck">Puck</option>
                        <option value="Charon">Charon</option>
                        <option value="Kore">Kore</option>
                        <option value="Fenrir">Fenrir</option>
                        <option value="Aoede">Aoede</option>
                    </select>
                </div>
                <div>
                    <label for="system-prompt">System Prompt:</label>
                    <textarea id="system-prompt" rows="10" placeholder="Enter system prompt here">__SYSTEM_PROMPT__</textarea>
                </div>
                <button id="connect">Connect</button>
                <button id="disconnect" disabled>Disconnect</button>
                <div id="log"></div>
            </div>

            <script>
                // Store the RTC configuration
                const rtcConfiguration = __RTC_CONFIGURATION__;

                // DOM elements
                const connectBtn = document.getElementById('connect');
                const disconnectBtn = document.getElementById('disconnect');
                const statusDiv = document.getElementById('status');
                const apiKeyInput = document.getElementById('api-key');
                const voiceSelect = document.getElementById('voice-select');
                const systemPromptInput = document.getElementById('system-prompt');
                const logDiv = document.getElementById('log');

                // WebRTC variables
                let pc;
                let stream;
                let webrtcId;

                // Update status display
                function updateStatus(state, message) {
                    statusDiv.className = `status ${state}`;
                    statusDiv.textContent = `Status: ${message}`;
                }

                // Log messages
                function log(message) {
                    const p = document.createElement('p');
                    p.textContent = message;
                    logDiv.appendChild(p);
                    console.log(message);
                }

                // Connect button click handler
                connectBtn.addEventListener('click', async () => {
                    try {
                        // Check for API key
                        const apiKey = apiKeyInput.value.trim();
                        if (!apiKey) {
                            alert('Please enter your Gemini API key');
                            return;
                        }

                        // Get voice selection and system prompt
                        const voiceName = voiceSelect.value;
                        const systemPrompt = systemPromptInput.value.trim() || "__DEFAULT_SYSTEM_PROMPT__";

                        log(`Using voice: ${voiceName}`);
                        log(`System prompt length: ${systemPrompt.length} characters`);

                        updateStatus('connecting', 'Connecting...');

                        // Request microphone access
                        stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                        // Create peer connection
                        pc = new RTCPeerConnection(rtcConfiguration);

                        // Add local audio track
                        stream.getAudioTracks().forEach(track => {
                            pc.addTrack(track, stream);
                        });

                        // Handle remote audio
                        pc.ontrack = (event) => {
                            const audioEl = new Audio();
                            audioEl.srcObject = event.streams[0];
                            audioEl.play();
                            log('Received remote audio stream');
                        };

                        // Handle ice candidates
                        pc.onicecandidate = (event) => {
                            if (event.candidate) {
                                fetch(`/rtc/candidate/${webrtcId}`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ candidate: event.candidate })
                                });
                            }
                        };

                        // Connection state changes
                        pc.onconnectionstatechange = () => {
                            log(`Connection state: ${pc.connectionState}`);
                            if (pc.connectionState === 'connected') {
                                updateStatus('connected', 'Connected');
                                connectBtn.disabled = true;
                                disconnectBtn.disabled = false;
                            } else if (pc.connectionState === 'disconnected' ||
                                      pc.connectionState === 'failed' ||
                                      pc.connectionState === 'closed') {
                                updateStatus('disconnected', 'Disconnected');
                                connectBtn.disabled = false;
                                disconnectBtn.disabled = true;
                            }
                        };

                        // Create WebRTC session
                        const response = await fetch('/rtc/session', { method: 'POST' });
                        const data = await response.json();
                        webrtcId = data.webrtc_id;

                        // Create offer
                        const offer = await pc.createOffer();
                        await pc.setLocalDescription(offer);

                        // Send offer to server
                        await fetch(`/rtc/offer/${webrtcId}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ sdp: pc.localDescription })
                        });

                        // Send API key, voice name, and system prompt
                        log('Sending configuration to server...');
                        const inputResponse = await fetch('/input_hook', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                webrtc_id: webrtcId,
                                api_key: apiKey,
                                voice_name: voiceName,
                                system_prompt: systemPrompt
                            })
                        });
                        const inputData = await inputResponse.json();
                        log(`Server response: ${JSON.stringify(inputData)}`);

                        // Get answer from server
                        const answerResponse = await fetch(`/rtc/answer/${webrtcId}`);
                        const answerData = await answerResponse.json();
                        await pc.setRemoteDescription(new RTCSessionDescription(answerData.sdp));

                        // Set up event polling for candidates
                        const pollCandidates = async () => {
                            try {
                                const response = await fetch(`/rtc/candidates/${webrtcId}`);
                                const data = await response.json();
                                for (const candidate of data.candidates) {
                                    await pc.addIceCandidate(new RTCIceCandidate(candidate));
                                }
                                if (pc.connectionState !== 'closed') {
                                    setTimeout(pollCandidates, 500);
                                }
                            } catch (err) {
                                console.error('Error polling candidates:', err);
                                if (pc.connectionState !== 'closed') {
                                    setTimeout(pollCandidates, 1000);
                                }
                            }
                        };

                        pollCandidates();

                    } catch (err) {
                        console.error('Connection error:', err);
                        log(`Error: ${err.message}`);
                        updateStatus('disconnected', 'Connection failed');
                    }
                });

                // Disconnect button click handler
                disconnectBtn.addEventListener('click', () => {
                    if (pc) {
                        pc.close();
                    }
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }
                    updateStatus('disconnected', 'Disconnected');
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                });
            </script>
        </body>
        </html>
        """

        # Replace placeholders with actual content
        html_content = html_content.replace("__SYSTEM_PROMPT__", system_prompt_for_form)
        html_content = html_content.replace("__DEFAULT_SYSTEM_PROMPT__", DEFAULT_SYSTEM_PROMPT)
    else:
        html_content = index_path.read_text()
        # Replace placeholders if they exist
        html_content = html_content.replace("__SYSTEM_PROMPT__", system_prompt_for_form)
        html_content = html_content.replace("__DEFAULT_SYSTEM_PROMPT__", DEFAULT_SYSTEM_PROMPT)

    html_content = html_content.replace("__RTC_CONFIGURATION__", json.dumps(rtc_config))
    return HTMLResponse(content=html_content)


@app.get("/conversations")
async def list_conversations():
    """List all available conversation logs"""
    log_dir = pathlib.Path("conversation_logs")
    if not log_dir.exists():
        return {"conversations": []}

    conversations = []
    for log_file in log_dir.glob("*.txt"):
        try:
            with open(log_file, "r") as f:
                # Read the first few lines to get the conversation ID and start time
                lines = [next(f) for _ in range(3) if f]
                conv_id = log_file.stem
                started = "Unknown"

                for line in lines:
                    if line.startswith("Started:"):
                        started = line.replace("Started:", "").strip()

                # Get file stats
                stats = log_file.stat()
                size_kb = stats.st_size / 1024
                last_modified = datetime.datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                conversations.append({
                    "id": conv_id,
                    "started": started,
                    "last_modified": last_modified,
                    "size_kb": round(size_kb, 2),
                    "filename": log_file.name
                })
        except Exception as e:
            print(f"Error reading log file {log_file}: {e}")

    # Sort by most recent first
    conversations.sort(key=lambda x: x["last_modified"], reverse=True)
    return {"conversations": conversations}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get the content of a specific conversation log"""
    log_file = pathlib.Path(f"conversation_logs/{conversation_id}.txt")
    if not log_file.exists():
        return {"error": "Conversation not found"}

    try:
        content = log_file.read_text()
        return {"id": conversation_id, "content": content}
    except Exception as e:
        return {"error": f"Could not read conversation: {str(e)}"}


@app.get("/download/conversations")
async def download_conversations():
    """Download all conversation logs as a ZIP file"""
    import io
    import zipfile

    log_dir = pathlib.Path("conversation_logs")
    if not log_dir.exists() or not any(log_dir.iterdir()):
        return {"error": "No conversation logs found"}

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add all conversation log files to the ZIP
        for file_path in log_dir.glob("*.*"):
            # Only include .txt and .json files
            if file_path.suffix.lower() in ['.txt', '.json']:
                zip_file.write(
                    file_path,
                    arcname=file_path.name
                )

    # Reset the buffer position
    zip_buffer.seek(0)

    # Create filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_logs_{timestamp}.zip"

    # Return the ZIP file as a streaming response
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a specific conversation log"""
    txt_file = pathlib.Path(f"conversation_logs/{conversation_id}.txt")
    json_file = pathlib.Path(f"conversation_logs/{conversation_id}.json")

    if not txt_file.exists() and not json_file.exists():
        return {"error": "Conversation not found"}

    try:
        # Delete both txt and json files if they exist
        if txt_file.exists():
            txt_file.unlink()
        if json_file.exists():
            json_file.unlink()
        return {"status": "success", "message": f"Conversation {conversation_id} deleted"}
    except Exception as e:
        return {"error": f"Could not delete conversation: {str(e)}"}


@app.get("/conversations/stats")
async def get_conversation_stats():
    """Get statistics about all conversations"""
    log_dir = pathlib.Path("conversation_logs")
    if not log_dir.exists():
        return {"stats": {
            "total_conversations": 0,
            "total_messages": 0,
            "avg_messages_per_conversation": 0,
            "total_user_messages": 0,
            "total_assistant_messages": 0
        }}

    stats = {
        "total_conversations": 0,
        "total_messages": 0,
        "total_user_messages": 0,
        "total_assistant_messages": 0,
        "avg_duration_seconds": 0,
        "conversations_by_date": {},
        "conversation_details": []
    }

    # Get all JSON log files
    json_files = list(log_dir.glob("*.json"))
    stats["total_conversations"] = len(json_files)

    total_duration_seconds = 0
    conversations_with_duration = 0

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            # Get basic message counts
            message_count = data.get("message_count", 0)
            user_messages = data.get("user_message_count", 0)
            assistant_messages = data.get("assistant_message_count", 0)

            stats["total_messages"] += message_count
            stats["total_user_messages"] += user_messages
            stats["total_assistant_messages"] += assistant_messages

            # Process conversation date
            start_date = "Unknown"
            if "started" in data:
                try:
                    start_date = data["started"].split()[0]  # Get just the date part
                    if start_date not in stats["conversations_by_date"]:
                        stats["conversations_by_date"][start_date] = 0
                    stats["conversations_by_date"][start_date] += 1
                except:
                    pass

            # Calculate duration if available
            if "started" in data and "ended" in data:
                try:
                    start_time = datetime.datetime.strptime(data["started"], "%Y-%m-%d %H:%M:%S")
                    end_time = datetime.datetime.strptime(data["ended"], "%Y-%m-%d %H:%M:%S")
                    duration = (end_time - start_time).total_seconds()
                    total_duration_seconds += duration
                    conversations_with_duration += 1
                except:
                    pass

            # Add conversation details
            stats["conversation_details"].append({
                "id": data.get("conversation_id", json_file.stem),
                "date": start_date,
                "messages": message_count,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages
            })

        except Exception as e:
            print(f"Error processing {json_file}: {e}")

    # Calculate averages
    if stats["total_conversations"] > 0:
        stats["avg_messages_per_conversation"] = stats["total_messages"] / stats["total_conversations"]

    if conversations_with_duration > 0:
        stats["avg_duration_seconds"] = total_duration_seconds / conversations_with_duration
        stats["avg_duration_formatted"] = str(datetime.timedelta(seconds=int(stats["avg_duration_seconds"])))

    # Sort conversation details by date (most recent first)
    stats["conversation_details"].sort(key=lambda x: x["date"], reverse=True)

    return {"stats": stats}


@app.get("/view")
async def view_conversations():
    """Simple web page to view conversation logs"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Conversation Logs Viewer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .card { border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; }
            .conversation-list { margin-bottom: 30px; }
            .conversation-content { white-space: pre-wrap; background: #f9f9f9; padding: 15px; border-radius: 5px; max-height: 600px; overflow-y: auto; }
            .message { margin-bottom: 15px; padding: 10px; border-radius: 5px; }
            .user-message { background-color: #e6f7ff; border-left: 4px solid #1890ff; }
            .assistant-message { background-color: #f6ffed; border-left: 4px solid #52c41a; }
            .system-message { background-color: #fff7e6; border-left: 4px solid #faad14; }
            .actions { margin-top: 10px; }
            button { padding: 8px 16px; margin-right: 10px; cursor: pointer; }
            .stats { background-color: #f0f2f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .loading { text-align: center; padding: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Conversation Logs Viewer</h1>
                <div>
                    <button id="refreshBtn">Refresh</button>
                    <button id="downloadBtn">Download All Logs</button>
                </div>
            </div>

            <div id="stats" class="stats">
                <h2>Statistics</h2>
                <div id="statsContent">Loading statistics...</div>
            </div>

            <h2>Conversations</h2>
            <div id="conversationList" class="conversation-list">
                <div class="loading">Loading conversations...</div>
            </div>

            <div id="conversationView" style="display: none;">
                <h2>Conversation: <span id="conversationId"></span></h2>
                <div id="conversationContent" class="conversation-content"></div>
                <div class="actions">
                    <button id="backBtn">Back to List</button>
                    <button id="deleteBtn" class="delete">Delete Conversation</button>
                </div>
            </div>
        </div>

        <script>
            // DOM elements
            const refreshBtn = document.getElementById('refreshBtn');
            const downloadBtn = document.getElementById('downloadBtn');
            const conversationList = document.getElementById('conversationList');
            const conversationView = document.getElementById('conversationView');
            const conversationId = document.getElementById('conversationId');
            const conversationContent = document.getElementById('conversationContent');
            const backBtn = document.getElementById('backBtn');
            const deleteBtn = document.getElementById('deleteBtn');
            const statsContent = document.getElementById('statsContent');

            // Fetch and display all conversations
            async function loadConversations() {
                conversationList.innerHTML = '<div class="loading">Loading conversations...</div>';
                try {
                    const response = await fetch('/conversations');
                    const data = await response.json();

                    if (data.conversations && data.conversations.length > 0) {
                        let html = '';
                        for (const conv of data.conversations) {
                            html += `
                                <div class="card">
                                    <h3>${conv.id}</h3>
                                    <p>Started: ${conv.started}</p>
                                    <p>Last Modified: ${conv.last_modified}</p>
                                    <p>Size: ${conv.size_kb.toFixed(2)} KB</p>
                                    <button onclick="viewConversation('${conv.id}')">View</button>
                                </div>
                            `;
                        }
                        conversationList.innerHTML = html;
                    } else {
                        conversationList.innerHTML = '<p>No conversations found.</p>';
                    }
                } catch (error) {
                    conversationList.innerHTML = `<p>Error loading conversations: ${error.message}</p>`;
                }
            }

            // Load statistics
            async function loadStats() {
                statsContent.innerHTML = 'Loading statistics...';
                try {
                    const response = await fetch('/conversations/stats');
                    const data = await response.json();
                    const stats = data.stats;

                    let html = `
                        <p>Total Conversations: ${stats.total_conversations}</p>
                        <p>Total Messages: ${stats.total_messages}</p>
                        <p>User Messages: ${stats.total_user_messages}</p>
                        <p>Assistant Messages: ${stats.total_assistant_messages}</p>
                    `;

                    if (stats.avg_duration_formatted) {
                        html += `<p>Average Duration: ${stats.avg_duration_formatted}</p>`;
                    }

                    if (stats.avg_messages_per_conversation) {
                        html += `<p>Average Messages Per Conversation: ${stats.avg_messages_per_conversation.toFixed(2)}</p>`;
                    }

                    statsContent.innerHTML = html;
                } catch (error) {
                    statsContent.innerHTML = `<p>Error loading statistics: ${error.message}</p>`;
                }
            }

            // View a specific conversation
            async function viewConversation(id) {
                try {
                    const response = await fetch(`/conversations/${id}`);
                    const data = await response.json();

                    if (data.content) {
                        conversationId.textContent = id;

                        // Format the conversation content with styling
                        let formattedContent = '';
                        const lines = data.content.split('\n');
                        let inSystemPrompt = false;

                        for (const line of lines) {
                            if (line.startsWith('SYSTEM PROMPT:')) {
                                inSystemPrompt = true;
                                formattedContent += `<div class="system-message"><strong>${line}</strong><br>`;
                                continue;
                            }

                            if (inSystemPrompt && line.startsWith('-'.repeat(60))) {
                                if (formattedContent.endsWith('<br>')) {
                                    formattedContent += '</div>';
                                    inSystemPrompt = false;
                                }
                                continue;
                            }

                            if (line.match(/^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] (User|Assistant|System)/)) {
                                const type = line.includes('User') ? 'user-message' :
                                           line.includes('Assistant') ? 'assistant-message' : 'system-message';

                                formattedContent += `<div class="${type}">${line}<br>`;
                            } else if (line.trim() === '') {
                                if (formattedContent.endsWith('<br>')) {
                                    formattedContent += '</div>';
                                }
                            } else {
                                formattedContent += `${line}<br>`;
                            }
                        }

                        conversationContent.innerHTML = formattedContent;
                        conversationList.style.display = 'none';
                        conversationView.style.display = 'block';
                        deleteBtn.onclick = () => deleteConversation(id);
                    } else {
                        alert('Could not load conversation: ' + (data.error || 'Unknown error'));
                    }
                } catch (error) {
                    alert('Error viewing conversation: ' + error.message);
                }
            }

            // Delete a conversation
            async function deleteConversation(id) {
                if (!confirm(`Are you sure you want to delete conversation ${id}?`)) {
                    return;
                }

                try {
                    const response = await fetch(`/conversations/${id}`, { method: 'DELETE' });
                    const data = await response.json();

                    if (data.status === 'success') {
                        alert('Conversation deleted successfully');
                        backToList();
                        loadConversations();
                        loadStats();
                    } else {
                        alert('Could not delete conversation: ' + (data.error || 'Unknown error'));
                    }
                } catch (error) {
                    alert('Error deleting conversation: ' + error.message);
                }
            }

            // Go back to the conversation list
            function backToList() {
                conversationView.style.display = 'none';
                conversationList.style.display = 'block';
            }

            // Initial load
            loadConversations();
            loadStats();

            // Event listeners
            refreshBtn.addEventListener('click', () => {
                loadConversations();
                loadStats();
            });

            downloadBtn.addEventListener('click', () => {
                window.location.href = '/download/conversations';
            });

            backBtn.addEventListener('click', backToList);

            // Make viewConversation available globally
            window.viewConversation = viewConversation;
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def debug_response(response, print_all_fields=False):
    """Debug helper to print details about a Gemini API response"""
    print("-" * 60)
    print("Response debug info:")

    # Handle dictionary-like responses (JSON parsed)
    if isinstance(response, dict):
        print("Response type: Dictionary (JSON)")

        if print_all_fields:
            print(f"Top-level keys: {', '.join(response.keys())}")

        # Check for serverContent
        if "serverContent" in response:
            server_content = response["serverContent"]
            print(f"Server content keys: {', '.join(server_content.keys())}")

            # Check for model turn
            if "modelTurn" in server_content:
                model_turn = server_content["modelTurn"]
                print(f"Model turn keys: {', '.join(model_turn.keys())}")

                if "parts" in model_turn and model_turn["parts"]:
                    print(f"Number of parts: {len(model_turn['parts'])}")
                    for i, part in enumerate(model_turn["parts"]):
                        print(f"Part {i} keys: {', '.join(part.keys())}")
                        if "text" in part:
                            print(f"Part {i} text: '{part['text'][:50]}...' ({len(part['text'])} chars)")

            # Check for input transcription
            if "inputTranscription" in server_content:
                transcription = server_content["inputTranscription"]
                print(f"Input transcription keys: {', '.join(transcription.keys())}")
                if "text" in transcription:
                    print(f"Transcribed text: '{transcription['text']}'")

            # Check for turnComplete
            if "turnComplete" in server_content:
                print(f"Turn complete: {server_content['turnComplete']}")

        # Check for streaming updates
        if "inputTranscription" in response:
            print(f"Direct input transcription: '{response['inputTranscription']}'")

        if "outputTranscription" in response:
            print(f"Output transcription: '{response['outputTranscription']}'")

    # Handle object-like responses
    elif hasattr(response, '__dict__'):
        print("Response type: Object")

        if print_all_fields:
            fields = list(response.__dict__.keys())
            print(f"All fields: {', '.join(fields)}")

        # Check for standard attributes
        if hasattr(response, 'text') and response.text:
            print(f"Text: '{response.text}'")

        if hasattr(response, 'recognized_speech') and response.recognized_speech:
            print(f"Recognized speech: '{response.recognized_speech}'")

        if hasattr(response, 'is_final'):
            print(f"Is final: {response.is_final}")

        if hasattr(response, 'data') and response.data:
            print(f"Has audio data: Yes ({len(response.data)} bytes)")

        # Check for server_content attribute
        if hasattr(response, 'server_content') and response.server_content:
            server_content = response.server_content
            print("Server content found")

            # Try to access common attributes of server_content
            if hasattr(server_content, '__dict__'):
                sc_attrs = list(server_content.__dict__.keys())
                print(f"Server content attributes: {', '.join(sc_attrs)}")

            # Check for model_turn
            if hasattr(server_content, 'model_turn') and server_content.model_turn:
                print("Model turn found")
                model_turn = server_content.model_turn

                if hasattr(model_turn, 'parts') and model_turn.parts:
                    parts = model_turn.parts
                    print(f"Number of parts: {len(parts)}")
                    for i, part in enumerate(parts):
                        if hasattr(part, 'text') and part.text:
                            print(f"Part {i} text: '{part.text[:50]}...' ({len(part.text)} chars)")

            # Check for input transcription
            if hasattr(server_content, 'input_transcription') and server_content.input_transcription:
                transcription = server_content.input_transcription
                if hasattr(transcription, 'text'):
                    print(f"Input transcription: '{transcription.text}'")

            # Check if turn is complete
            if hasattr(server_content, 'turn_complete'):
                print(f"Turn complete: {server_content.turn_complete}")

        # Check for response metadata
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            print("Usage metadata found")
            if hasattr(usage, 'total_token_count'):
                print(f"Total token count: {usage.total_token_count}")
    else:
        print(f"Response is type: {type(response)}")
        print("Cannot extract structured information from this type")

    print("-" * 60)


if __name__ == "__main__":
    import os
    import sys
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Cold caller application with conversation logging")
    parser.add_argument('--mode', choices=['UI', 'PHONE', 'SERVER', 'LOGS'],
                       default=os.getenv("MODE", "UI"),
                       help="Mode to run the application in (default: UI)")
    parser.add_argument('--list-logs', action='store_true',
                       help="List all conversation logs and exit")
    parser.add_argument('--view-log', type=str,
                       help="View a specific conversation log by ID and exit")
    parser.add_argument('--port', type=int, default=7860,
                       help="Port to run the server on (default: 7860)")

    args = parser.parse_args()

    # Handle log viewing options
    if args.list_logs:
        log_dir = pathlib.Path("conversation_logs")
        if not log_dir.exists() or not any(log_dir.glob("*.txt")):
            print("No conversation logs found.")
            sys.exit(0)

        print("\nAvailable conversation logs:")
        print("-" * 80)
        for log_file in sorted(log_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            mtime = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
            size_kb = log_file.stat().st_size / 1024
            print(f"{log_file.stem} - {mtime.strftime('%Y-%m-%d %H:%M:%S')} - {size_kb:.1f} KB")
        print("-" * 80)
        sys.exit(0)

    if args.view_log:
        log_path = pathlib.Path(f"conversation_logs/{args.view_log}.txt")
        if not log_path.exists():
            print(f"Error: Log file for conversation {args.view_log} not found.")
            sys.exit(1)

        print(f"\nViewing conversation: {args.view_log}")
        print("=" * 80)
        print(log_path.read_text())
        print("=" * 80)
        sys.exit(0)

    # Run the application in the specified mode
    if args.mode == "UI":
        stream.ui.launch(server_port=args.port)
    elif args.mode == "PHONE":
        stream.fastphone(host="0.0.0.0", port=args.port)
    elif args.mode == "LOGS":
        # Special mode to enter an interactive log browser
        log_dir = pathlib.Path("conversation_logs")
        if not log_dir.exists():
            print("No conversation logs directory found.")
            sys.exit(1)

        logs = sorted(log_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not logs:
            print("No conversation logs found.")
            sys.exit(1)

        print("\nConversation Log Browser\n")
        for i, log_file in enumerate(logs, 1):
            mtime = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
            size_kb = log_file.stat().st_size / 1024
            print(f"{i}. {log_file.stem} - {mtime.strftime('%Y-%m-%d %H:%M:%S')} - {size_kb:.1f} KB")

        try:
            choice = int(input("\nEnter the number of the log to view (or 0 to exit): "))
            if choice == 0:
                sys.exit(0)
            elif 1 <= choice <= len(logs):
                log_path = logs[choice-1]
                print(f"\nViewing: {log_path.stem}\n")
                print("=" * 80)
                print(log_path.read_text())
                print("=" * 80)
            else:
                print("Invalid choice.")
        except (ValueError, IndexError):
            print("Invalid input.")
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=args.port)
