# TARS: Real-Time Voice Assistant System

## Overview

TARS is a real-time voice assistant that streams microphone input to a model over WebSocket and plays back generated audio responses with minimal latency.

The system is designed to handle continuous audio input, concurrent processing, and low-latency playback, forming the foundation for an embedded robotic assistant.

## System Architecture


## The pipeline consists of four main components:
- Microphone Input: Captured using PyAudio
- Streaming Layer: Audio is sent in real-time via WebSocket
- Response Handling: Incoming audio responses are processed asynchronously
- Speaker Output: Audio is buffered and played back smoothly

The system runs using multi-threading and queues to ensure non-blocking operation across all components.

## Key Features
Real-time audio streaming over WebSocket
Low-latency response playback
Concurrent processing using threads
Audio buffering for stable playback
Basic echo mitigation through input delay
Technical Challenges
Real-Time Streaming & Latency

## Maintaining smooth audio required careful tuning of:

- chunk sizes
- buffering strategy
- timing synchronization

Incorrect timing caused stuttering and lag.

## Multithreading Architecture

The system separates:

- microphone input (producer)
- WebSocket transmission
- response reception
- speaker playback

Using threads and queues allowed each component to run independently without blocking.

## Audio Buffer Management
## To ensure stable playback, a buffer system was implemented that:

accumulates incoming audio chunks
ensures sufficient data before playback
fills gaps with silence when needed
Echo Handling

## To prevent feedback from speaker to microphone, a delay mechanism was introduced:

if current_buffer_size >= bytes_needed:
    audio_chunk = bytes(audio_buffer[:bytes_needed])
    audio_buffer = audio_buffer[bytes_needed:]
    mic_on_at = time.time() + REENGAGE_DELAY_MS / 1000

This temporarily disables microphone input after playback to reduce echo loops.

## What This Project Demonstrates
- Real-time systems engineering
- Concurrency and thread management
- Audio signal handling and buffering
- Integration of streaming APIs with hardware I/O

## Current Limitations
- Echo handling is delay-based (not true cancellation)
- Latency can still vary depending on network conditions
- System is not yet integrated into a full physical robot

## Future Work
- Implement real echo cancellation
- Optimize latency and buffer efficiency
- Integrate with embedded hardware / robotic platform
- Add wake-word detection and continuous interaction

## Context
This project is part of a broader effort to build intelligent, embedded robotic systems capable of real-time interaction with the physical world.
