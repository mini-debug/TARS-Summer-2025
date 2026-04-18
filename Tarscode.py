import struct  # For unpacking binary audio data
import numpy as np  # For audio signal processing
import base64  # For Base64 encoding/decoding and audio data encoding transmission
import json  # Handling JSON format data exchange
import queue  # Thread-safe queue for microphone data buffering
import socket  # Network socket operations
import ssl  # SSL/TLS encryption support
import threading  # Multithreading support
import time  # Time-related operations
import azure.cognitiveservices.speech as speechsdk # Speech Services Azure

import pyaudio  # Audio input/output processing
import socks  # SOCKS proxy support
import websocket  # WebSocket client
from websocket import create_connection 

# Set SOCKS5 proxy (globally replaces socket implementation)
socket.socket = socks.socksocket

# OpenAI API
API_KEY = "This is where it goes as it runs, for saftey not in this repo" 

# WebSocket server URL (real-time speech conversion interface)
WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17'

# Audio stream parameter configuration
CHUNK_SIZE = 2048  # Size of each processed audio data chunk (bytes)
RATE = 24000  # Audio sampling rate (Hz)
FORMAT = pyaudio.paInt16  # Audio format (16-bit integer PCM)

# Global variable definitions

is_speaking = False  # Flag to indicate when assistant is speaking
VOLUME_THRESHOLD_DB = -35  # Minimum volume in dB to consider as speech
audio_buffer = bytearray()  # Stores received audio data (for speaker playback)
mic_queue = queue.Queue()  # Thread-safe queue for microphone data collection

stop_event = threading.Event()  # Thread stop event flag

mic_on_at = 0  # Microphone activation timestamp (for echo cancellation)
mic_active = None  # Current microphone status record
REENGAGE_DELAY_MS = 500  # Microphone re-engagement delay time (milliseconds)


def read_txt_file(file_path):
    """
    Read txt file content and return
    Parameters: file_path (str): txt file path

    Returns:
        str: File content
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None


def clear_audio_buffer():
    """Clear audio playback buffer"""
    global audio_buffer
    audio_buffer = bytearray()  # Reset to empty byte array
    print('* Audio buffer cleared')


def stop_audio_playback():
    """Stop audio playback (set playback status flag)"""
    global is_playing
    is_playing = False
    print('* Audio playback stopped')


def mic_callback(in_data, frame_count, time_info, status):
    """
    Microphone data collection callback function
    Parameters:
        in_data: Input audio data (binary)
        frame_count: Frame count (number of audio frames in this callback)
        time_info: Time information dictionary
        status: Status flags (normal/error)
    Returns:
        (None, pyaudio.paContinue) indicates to continue collection
    """
    global mic_on_at, mic_active

    # Detect and update microphone status
    if mic_active != True:
        print(':) Microphone activated')
        mic_active = True

    # Put audio data into queue (thread-safe)
    mic_queue.put(in_data)

   # Commented-out echo cancellation logic (can be enabled when we need it) 
    if time.time() > mic_on_at:
        if mic_active != True:
            print(':) Microphone activated')
            mic_active = True
        mic_queue.put(in_data)
    else:
        if mic_active != False:
            print('Womp, Womp Microphone muted')
            mic_active = False

    return (None, pyaudio.paContinue)  # Return empty data and continue flag


def send_mic_audio_to_websocket(ws):
    """
    Send microphone audio data to WebSocket server
    Parameters:
        ws: Established WebSocket connection object
    """
    try:
        while not stop_event.is_set():  # Run continuously until stop signal received
            if not mic_queue.empty():  # Check if queue has data
                # Get one audio data chunk from queue
                mic_chunk = mic_queue.get()

                # Base64 encode audio data (suitable for JSON transmission)
                encoded_chunk = base64.b64encode(mic_chunk).decode('utf-8')

                # Construct WebSocket message (JSON format)
                message = json.dumps({
                    'type': 'input_audio_buffer.append',  # Message type
                    'audio': encoded_chunk  # Encoded audio data
                })

                try:
                    ws.send(message)  # Send message
                except Exception as e:
                    print(f'Error sending microphone audio: {e}')
    except Exception as e:
        print(f'Microphone data sending thread exception: {e}')
    finally:
        print('Microphone data sending thread exited')

def speaker_callback(in_data, frame_count, time_info, status):
    """
    Speaker playback callback function
    Parameters:
        in_data: Input data (unused)
        frame_count: Required number of audio frames
        time_info: Time information dictionary
        status: Status flags :) 
    Returns:
        (audio_chunk, pyaudio.paContinue) audio data and continue playback flag
    """
    global audio_buffer, mic_on_at, is_speaking

    bytes_needed = frame_count * 2
    current_buffer_size = len(audio_buffer)

    if current_buffer_size >= bytes_needed:
        # Buffer has enough data: take the needed data
        audio_chunk = bytes(audio_buffer[:bytes_needed])
        audio_buffer = audio_buffer[bytes_needed:]  # Update buffer by removing the chunk

        # Set microphone activation time (current time + delay) to avoid echo
        mic_on_at = time.time() + REENGAGE_DELAY_MS / 1000
        is_speaking = True
    else:
        # Insufficient buffer: take what's left and fill remaining with silence
        audio_chunk = bytes(audio_buffer) + b'\x00' * (bytes_needed - current_buffer_size)
        audio_buffer.clear()  # Clear the now-empty buffer
        is_speaking = False

    return (audio_chunk, pyaudio.paContinue)

# ***old code from the original Tars file but we just changed it due to a couple of problems but didn't want to get fully rid of it***

# def speaker_callback(in_data, frame_count, time_info, status):
#     """
#     Speaker playback callback function
#     Parameters:
#         in_data: Input data (unused)
#         frame_count: Required number of audio frames
#         time_info: Time information dictionary
#         status: Status flags
#     Returns:
#         (audio_chunk, pyaudio.paContinue) audio data and continue playback flag
#     """
#     global audio_buffer, mic_on_at

#     # Calculate required bytes (16-bit audio = 2 bytes/sample)
#     bytes_needed = frame_count * 2
#     current_buffer_size = len(audio_buffer)

#     if current_buffer_size >= bytes_needed:
#         # Buffer has enough data: take needed data
#         audio_chunk = bytes(audio_buffer[:bytes_needed])
#         audio_buffer = audio_buffer[bytes_needed:]  # Update buffer

#         # Set microphone activation time (current time + delay) to avoid echo
#         mic_on_at = time.time() + REENGAGE_DELAY_MS / 1000
#     is_speaking = True
    
#     else:
#         # Insufficient buffer: fill remaining with silence
#     audio_chunk = bytes(audio_buffer) + b'\x00' * (bytes_needed - current_buffer_size)
#     audio_buffer.clear()  # Clear buffer

#     return (audio_chunk, pyaudio.paContinue)
    
    
# ... inside speaker_callback function


def receive_audio_from_websocket(ws):
    """
    Receive audio data from WebSocket and handle server events
    Parameters:
        ws: Established WebSocket connection object
    """
    global audio_buffer

    try:
        while not stop_event.is_set():  # Run continuously until stop signal received
            info = None
            try:
                info = None
                # Receive WebSocket message
                message = ws.recv()

                # Handle empty message (connection closed or EOF)
                if not message:
                    print('⚙️ Received empty message (connection may be closed)')
                    # break # End loop
                    continue  # End current iteration

                # Parse JSON message
                message = json.loads(message)
                info = message
                event_type = message['type']  # Extract event type
                print(f'⚡️ Received WebSocket event: {event_type}')

                # Handle based on event type
                if event_type == 'session.created':
                    # Session creation event: send session configuration
                    send_fc_session_update(ws)

                elif event_type == 'response.audio.delta':
                    # Audio chunk event: decode and store in playback buffer
                    audio_content = base64.b64decode(message['delta'])
                    audio_buffer.extend(audio_content)
                    print(f' Received {len(audio_content)} bytes audio, total buffer size: {len(audio_buffer)}')

                elif event_type == 'input_audio_buffer.speech_started':
                    # Speech start event: clear buffer and stop playback
                    print(' Speech start detected, clearing buffer and stopping playback')
                    clear_audio_buffer()
                    stop_audio_playback()

                elif event_type == 'response.audio.done':
                    
                    is_speaking = False# Audio end event
                    print(' AI speech ended')

                elif event_type == 'response.audio_transcript.delta':
                    delta = message['delta']  # Extract text content
                    print(f' Received text: {delta}')
                elif event_type == 'response.audio_transcript.done':
                    transcript = message['transcript']  # Extract text content
                    print(f' Received text: {transcript}')
                elif event_type == 'conversation.item.input_audio_transcription.delta':
                    delta = message['delta']  # Extract text content
                    print(f' Input content: {delta}')
                else:
                    # Print info for other types
                    print(f'⚡️ Received WebSocket message: {message}')


            except Exception as e:
                print(f'Error receiving audio data: {e}')
                print(f'Error receiving audio data: {info}')
    except Exception as e:
        print(f'Audio receiving thread exception: {e}')
    finally:
        print('Audio receiving thread exited')


def send_fc_session_update(ws):
    """
    Send session configuration information to server
    Parameters:
        ws: WebSocket connection object
    """

    # Complete session configuration definition
    session_config = {
        "type": "session.update",
        "session": {
            "instructions": (
                "You are a friendly AI assistant."
                "You will provide patient and professional answers to users' questions."
            ),
            # Voice activity detection configuration
            "turn_detection": {
                "type": "server_vad",  # Use server-side VAD
                "threshold": 0.5,  # Voice detection threshold
                "prefix_padding_ms": 300,  # Prefix silence duration
                "silence_duration_ms": 500  # Silence determination duration
            },
            "voice": "alloy",  # Voice type
            "temperature": 1,  # Response randomness
            "max_response_output_tokens": 4096,  # Maximum output tokens
            "modalities": ["text", "audio"],  # Interaction modes
            "input_audio_format": "pcm16",  # Input audio format
            "output_audio_format": "pcm16",  # Output audio format
            # Speech recognition configuration
            "input_audio_transcription": {
                "model": "whisper-1"  # Use Whisper model
            }
        }
    }

    try:
        # Send session configuration
        ws.send(json.dumps(session_config))
        print("Session configuration update sent")
    except Exception as e:
        print(f"Failed to send session configuration: {e}")


def create_connection_with_ipv4(*args, **kwargs):
    """
    Create WebSocket connection forcing IPv4 usage
    Parameters:
        *args: Variable positional arguments (passed to websocket.create_connection)
        **kwargs: Variable keyword arguments (passed to websocket.create_connection)
    Returns:
        WebSocket connection object
    """
    # Save original getaddrinfo function
    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo_ipv4(host, port, family=socket.AF_INET, *args):
        """
        Overridden getaddrinfo function forcing IPv4 usage
        Parameters:
            host: Target host
            port: Target port
            family: Forced to AF_INET (IPv4)
        """
        return original_getaddrinfo(host, port, socket.AF_INET, *args)

    # Temporarily replace system getaddrinfo implementation
    socket.getaddrinfo = getaddrinfo_ipv4
    try:
        # Create WebSocket connection
        return websocket.create_connection(*args, **kwargs)
    finally:
        # Restore original getaddrinfo function
        socket.getaddrinfo = original_getaddrinfo


def connect_to_openai():
    """
    Establish connection to OpenAI WebSocket API and manage communication threads
    """
    ws = None
    try:
        # Create WebSocket connection with authentication headers

        ws = create_connection_with_ipv4(
            WS_URL,  # WebSocket server URL
            header=[
                f'Authorization: Bearer {API_KEY}',  # API key authentication
                'OpenAI-Beta: realtime=v1'  # Protocol version identifier
            ],
            sslopt={"cert_reqs": ssl.CERT_NONE}  # Disable certificate verification
        )

        print('Successfully connected to OpenAI WebSocket, Yipee!')

        # Start receive thread (handles server responses)
        receive_thread = threading.Thread(
            target=receive_audio_from_websocket,
            args=(ws,)
        )
        receive_thread.start()

        # Start send thread (sends microphone data)
        mic_thread = threading.Thread(
            target=send_mic_audio_to_websocket,
            args=(ws,)
        )
        mic_thread.start()

        # Main loop: wait for stop event trigger
        while not stop_event.is_set():
            time.sleep(0.1)  # Reduce CPU usage

        # Graceful shutdown: send close frame
        print('Sending WebSocket close frame...')
        ws.send_close()

        # Wait for threads to finish
        receive_thread.join()
        mic_thread.join()

        print('WebSocket connection closed, threads terminated')
    except Exception as e:
        print(f'Failed to connect to OpenAI: {e}')
    finally:
        if ws is not None:
            try:
                ws.close()
                print('WebSocket connection closed')
            except Exception as e:
                print(f'Error closing WebSocket connection: {e}')


def main():
    """
    Main function: Initialize audio streams and start core logic
    """

    # Initialize PyAudio instance
    p = pyaudio.PyAudio()

    # Configure microphone input stream
    mic_stream = p.open(
        format=FORMAT,  # Audio format (16-bit integer)
        channels=1,  # Mono channel
        rate=RATE,  # 24kHz sample rate
        input=True,  # Input device
        stream_callback=mic_callback,  # Real-time callback function
        frames_per_buffer=int(CHUNK_SIZE)  # 2048 bytes per chunk
    )

    # Configure speaker output stream
    speaker_stream = p.open(
        format=FORMAT,
        channels=1,
        rate=RATE,
        output=True,  # Output device
        stream_callback=speaker_callback,
        frames_per_buffer=CHUNK_SIZE*4
    )

    try:
        # Start audio streams
        mic_stream.start_stream()
        speaker_stream.start_stream()

        # Connect to OpenAI service
        connect_to_openai()

        # Keep main thread running (monitor audio stream status)
        while mic_stream.is_active() and speaker_stream.is_active():
            time.sleep(0.1)

    except KeyboardInterrupt:
        # Handle Ctrl+C interrupt
        print('Gracefully shutting down...')
        stop_event.set()  # Notify all threads to stop

    finally:
        # Clean up audio resources
        mic_stream.stop_stream()
        mic_stream.close()
        speaker_stream.stop_stream()
        speaker_stream.close()

        p.terminate()  # Release PyAudio resources
        print('Audio streams stopped, resources released. Program exiting')


if __name__ == '__main__':
    """Program entry point"""
    main()
