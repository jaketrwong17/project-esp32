Here is a structured prompt you can copy and paste directly into your gemini.md or chat window. It is designed to force the AI to look for logical errors (like checking if a face exists vs. checking if it matches) and threshold calibration issues.

The Prompt to Copy
System Context: I am building a face recognition security system (e.g., using Python/OpenCV or ESP32).

The Bug: I have a critical False Acceptance issue. The system is currently scanning faces, but it malfunctions by unlocking for everyone. If it detects any face, it grants access, regardless of who it is.

My Goal: I need the code to only unlock when the detected face specifically matches the enrolled/authorized user's face data.

The Code:

Python

# [PASTE YOUR CURRENT CODE HERE]
Request:

Analyze the logic inside my main recognition loop.

Check if I am confusing "face detection" (finding a face) with "face recognition" (verifying identity).

Check my confidence/tolerance thresholds (e.g., is the Euclidean distance threshold too high?).

Provide the corrected code snippet that fixes this logic.