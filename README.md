# Camera-Based Smart Attendance System

## 1. Introduction
This project is an AI-powered **Camera-Based Smart Attendance System** that automatically marks attendance using face detection and recognition. A camera is placed at the entrance, and whenever a student or teacher enters or exits, the system identifies them and records their entry/exit times.

## 2. Objectives
* **Automation:** To automate attendance recording using smart technologies.
* **Accuracy:** To ensure precision and prevent proxy attendance.
* **Efficiency:** To generate real-time attendance reports and improve management.
* **Security:** To provide a secure and reliable data storage system.

## 3. Functional Requirements (FRs)
* **FR1. Face Detection:** Detects faces in real-time via camera.
* **FR2. Face Recognition:** Matches detected faces with the registered database.
* **FR3. Automatic Marking:** Marks attendance as "Present" upon entry.
* **FR4. Entry/Exit Recording:** Saves the exact timestamps of entry and exit.
* **FR5. Duration Calculation:** Calculates total stay duration in class.
* **FR6. Database Management:** Stores student/teacher profiles and photos.
* **FR7. Real-Time Logs:** Displays live logs to the administrator.

## 4. Non-Functional Requirements (NFRs)
* **Accuracy:** Target 85–90% face recognition accuracy.
* **Performance:** Recognition response time within 1–2 seconds.
* **Usability:** Simple and user-friendly interface for teachers.
* **Scalability:** Capable of adding more students in the future.
* **Low Cost:** Built using open-source libraries like **OpenCV** and **face_recognition**.

## 5. How to Run (Local Setup)
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install opencv-python cmake face-recognition numpy
